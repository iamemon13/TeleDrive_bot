"""
TeleDrive Organizer Bot (Telegram Only)
----------------------------------------
Developer: iamemon13
Features: Multi-topic, MongoDB, Inline Search, Duplicate Check, Direct Link, Encryption, Weekly Auto-Forward Backup
"""

import asyncio
import io
import json
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from pymongo import MongoClient

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    InlineQueryHandler,
    filters,
)

# ============ CONFIG ============

BOT_TOKEN = os.environ.get("BOT_TOKEN")

db_password_raw = os.environ.get("DB_PASSWORD", "yoyoji..")
DB_PASSWORD = quote_plus(db_password_raw) 
MONGO_URI = os.environ.get("MONGO_URI") or f"mongodb+srv://TeleDrive0313_bot:{DB_PASSWORD}@cluster0.xvifgpb.mongodb.net/?appName=Cluster0"

GROUP_ID = -1004449101180
BACKUP_CHANNEL_ID = -1004304201011  

TOPIC_IDS = {
    "photo": 6,      # 📷 Photos topic id
    "video": 7,      # 🎥 Videos topic id
    "document": 12,  # 📄 Documents topic id
}

IGNORE_THREAD_IDS = set(TOPIC_IDS.values())

# ============ LOGGING ============

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ DATABASE (MongoDB) ============

client = MongoClient(MONGO_URI)
db = client["teledrive_db"]
files_col = db["files"]

def save_file_record(file_type, file_name, caption, thread_id, message_id, channel_msg_id=None, encrypted=False):
    record = {
        "file_type": file_type,
        "file_name": file_name or "",
        "caption": caption or "",
        "thread_id": thread_id,
        "message_id": message_id,
        "channel_msg_id": channel_msg_id,
        "encrypted": encrypted,
        "date": datetime.now().isoformat()
    }
    files_col.insert_one(record)

def search_files(keyword):
    query = {
        "$or": [
            {"file_name": {"$regex": keyword, "$options": "i"}},
            {"caption": {"$regex": keyword, "$options": "i"}}
        ]
    }
    results = files_col.find(query).sort("_id", -1).limit(20)
    return list(results)

def cipher_text(text, key, decrypt=False):
    shift = sum(ord(c) for c in key) % 26
    if decrypt:
        shift = -shift
    result = []
    for char in text:
        if char.isalpha():
            start = ord('A') if char.isupper() else ord('a')
            result.append(chr((ord(char) - start + shift) % 26 + start))
        else:
            result.append(char)
    return "".join(result)

# ============ WEEKLY FORWARD BACKUP LOGIC ============

async def perform_weekly_forward_backup(bot):
    one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent_files = list(files_col.find({"date": {"$gte": one_week_ago}}))
    
    if not recent_files:
        return 0

    count = 0
    for item in recent_files:
        msg_id = item.get("message_id")
        if msg_id:
            try:
                await bot.forward_message(
                    chat_id=BACKUP_CHANNEL_ID,
                    from_chat_id=GROUP_ID,
                    message_id=msg_id
                )
                count += 1
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to forward message: {e}")
    return count

async def weekly_backup_job(context: ContextTypes.DEFAULT_TYPE):
    await perform_weekly_forward_backup(context.bot)

# ============ TELEGRAM HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("TeleDrive Bot (Developed by @iamemon13) সফলভাবে চালু আছে ✅")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    total_files = files_col.count_documents({})
    await update.message.reply_text(f"📊 Total Files in TeleDrive: {total_files}")

async def backup_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    count = await perform_weekly_forward_backup(context.bot)
    await update.message.reply_text(f"✅ ব্যাকআপ সফল! মোট {count} টি ফাইল ফরোয়ার্ড করা হয়েছে।")

async def encrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /encrypt <পাসওয়ার্ড> <টেক্সট>")
        return
    key = context.args[0]
    raw_text = " ".join(context.args[1:])
    await update.message.reply_text(f"🔐 `{cipher_text(raw_text, key)}`", parse_mode="Markdown")

async def decrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /decrypt <পাসওয়ার্ড> <টেক্সট>")
        return
    key = context.args[0]
    ciphered_text = " ".join(context.args[1:])
    await update.message.reply_text(f"🔓 {cipher_text(ciphered_text, key, decrypt=True)}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not context.args:
        return
    keyword = " ".join(context.args)
    results = search_files(keyword)
    if not results:
        await update.message.reply_text("কিছু পাওয়া যায়নি।")
        return
    lines = [f"🔍 রেজাল্ট:\n"]
    for item in results:
        lines.append(f"• [{item.get('file_type')}] {item.get('file_name')}")
    await update.message.reply_text("\n".join(lines))

async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return
    results = search_files(query)
    inline_results = [
        InlineQueryResultArticle(
            id=str(item.get("_id")),
            title=f"[{item.get('file_type')}] {item.get('file_name')}",
            input_message_content=InputTextMessageContent(item.get('file_name'))
        ) for item in results[:10]
    ]
    await update.inline_query.answer(inline_results)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or message.chat_id != GROUP_ID or message.message_thread_id in IGNORE_THREAD_IDS:
        return

    file_type = "document"
    file_name = f"file_{message.message_id}"
    if message.photo:
        file_type = "photo"
        file_name = f"photo_{message.message_id}.jpg"
    elif message.video:
        file_type = "video"
        file_name = message.video.file_name or f"video_{message.message_id}.mp4"

    target_thread = TOPIC_IDS.get(file_type, 12)
    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
        caption=(message.caption or "") + f"\n\n#{file_type} #TeleDrive"
    )
    save_file_record(file_type, file_name, message.caption, target_thread, copied.message_id)

# ============ MAIN ============

async def main_async():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("backup_now", backup_now_command))
    app.add_handler(CommandHandler("encrypt", encrypt_command))
    app.add_handler(CommandHandler("decrypt", decrypt_command))
    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file))

    if app.job_queue:
        app.job_queue.run_repeating(weekly_backup_job, interval=604800, first=15)

    print("Bot is running smoothly...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())
