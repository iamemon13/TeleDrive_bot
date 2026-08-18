"""
TeleDrive Organizer Bot (Telegram Only)
----------------------------------------
Developer: iamemon13
Features: Multi-topic, MongoDB, Inline Search, Duplicate Check, Encryption & Weekly Auto-Forward Backup
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import quote_plus
from flask import Flask
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

# ============ CONFIG (শুধুমাত্র Env Var থেকে রিড করবে) ============

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PASSWORD = quote_plus(os.environ["DB_PASSWORD"]) 
MONGO_URI = os.environ["MONGO_URI"]

GROUP_ID = int(os.environ["GROUP_ID"])
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
BACKUP_CHANNEL_ID = int(os.environ["BACKUP_CHANNEL_ID"])

TOPIC_IDS = {
    "photo": 6,      # 📷 Photos topic id
    "video": 7,      # 🎥 Videos topic id
    "document": 12,  # 📄 Documents topic id
}

IGNORE_THREAD_IDS = set(TOPIC_IDS.values())

# ============ RENDER KEEP ALIVE SERVER ============

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "TeleDrive Bot is running alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

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

def is_duplicate(file_name, caption):
    query = {"file_name": file_name}
    if caption:
        query["caption"] = caption
    return files_col.find_one(query) is not None

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
                logger.error(f"Failed to forward message id {msg_id}: {e}")
    return count

async def weekly_backup_job(context: ContextTypes.DEFAULT_TYPE):
    await perform_weekly_forward_backup(context.bot)

# ============ TELEGRAM HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("TeleDrive Bot (Developed by @iamemon13) সফলভাবে চালু আছে ✅")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    total_files = files_col.count_documents({})
    await update.message.reply_text(f"📊 Total Files in TeleDrive: {total_files}")

async def backup_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    count = await perform_weekly_forward_backup(context.bot)
    await update.message.reply_text(f"✅ ব্যাকআপ সফল! মোট {count} টি ফাইল ফরোয়ার্ড করা হয়েছে।")

async def encrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2: return
    key, raw_text = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔐 `{cipher_text(raw_text, key)}`", parse_mode="Markdown")

async def decrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2: return
    key, ciphered_text = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔓 {cipher_text(ciphered_text, key, decrypt=True)}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not context.args: return
    results = search_files(" ".join(context.args))
    if not results:
        await update.message.reply_text("কিছু পাওয়া যায়নি।")
        return
    lines = [f"🔍 রেজাল্ট:\n"]
    for item in results:
        lines.append(f"• [{item.get('file_type')}] {item.get('file_name')}")
    await update.message.reply_text("\n".join(lines))

async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query: return
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
    if message is None or message.chat_id != GROUP_ID or message.message_thread_id in IGNORE_THREAD_IDS: return

    file_type = "photo" if message.photo else "video" if message.video else "document"
    
    # কপি করার লজিক
    target_thread = TOPIC_IDS.get(file_type, 12)
    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
        caption=(message.caption or "") + f"\n\n#{file_type} #TeleDrive"
    )
    
    # চ্যানেল কপি ও ডাটাবেস সেভ
    try:
        c_copied = await context.bot.copy_message(chat_id=CHANNEL_ID, from_chat_id=GROUP_ID, message_id=message.message_id)
        save_file_record(file_type, f"{file_type}_{message.message_id}", message.caption, target_thread, copied.message_id, c_copied.message_id)
    except:
        save_file_record(file_type, f"{file_type}_{message.message_id}", message.caption, target_thread, copied.message_id)

# ============ MAIN ============

async def main_async():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # হ্যান্ডলার যোগ করা
    app.add_handlers([
        CommandHandler("start", start_command),
        CommandHandler("search", search_command),
        CommandHandler("stats", stats_command),
        CommandHandler("backup_now", backup_now_command),
        CommandHandler("encrypt", encrypt_command),
        CommandHandler("decrypt", decrypt_command),
        InlineQueryHandler(inline_search),
        MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file)
    ])
    
    if app.job_queue:
        app.job_queue.run_repeating(weekly_backup_job, interval=604800, first=15)

    print("TeleDrive Bot is running strictly on Env Vars...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())
    
