"""
TeleDrive Organizer Bot (Telegram Only)
----------------------------------------
Developer: iamemon13
Features: Multi-topic, MongoDB, Inline Search, Duplicate Check, Encryption, Delete Command & Weekly Auto-Forward Backup
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

# ইগনোর লিস্ট খালি রাখা হয়েছে, যাতে যেকোনো টপিক বা জেনারেল থেকে ফাইল দিলে কাজ করে
IGNORE_THREAD_IDS = set()

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
        "backed_up": False,
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
    recent_files = list(files_col.find({
        "date": {"$gte": one_week_ago},
        "$or": [{"backed_up": {"$exists": False}}, {"backed_up": False}]
    }))
    
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
                files_col.update_one({"_id": item["_id"]}, {"$set": {"backed_up": True}})
                count += 1
                await asyncio.sleep(1)
            except Exception as e:
                files_col.update_one({"_id": item["_id"]}, {"$set": {"backed_up": True}})
                logger.error(f"Failed to forward message id {msg_id}: {e}")
    return count

async def weekly_backup_job(context: ContextTypes.DEFAULT_TYPE):
    await perform_weekly_forward_backup(context.bot)

# ============ TELEGRAM HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "TeleDrive Bot (Developed by @iamemon13) চালু আছে ✅\n\n"
            "📌 কমান্ডসমূহ:\n"
            "• /search কিওয়ার্ড - ফাইল খুঁজুন\n"
            "• /stats - ড্রাইভের মোট ফাইলের হিসেব দেখুন\n"
            "• /backup_now - বিগত ৭ দিনের নতুন ফাইলগুলো ব্যাকআপ চ্যানেলে ফরোয়ার্ড করুন\n"
            "• /delete - গ্রুপে ফাইলের মেসেজে রিপ্লাই দিয়ে এই কমান্ড দিলে ডাটাবেস থেকে রিমুভ হবে\n"
            "• /encrypt পাসওয়ার্ড টেক্সট - টেক্সট লক করুন\n"
            "• /decrypt পাসওয়ার্ড টেক্সট - টেক্সট আনলক করুন\n"
            "• Inline Search: অন্য কোনো চ্যাটে `@TeleDrive0313_bot keyword` টাইপ করে ফাইল শেয়ার করুন।"
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    total_files = files_col.count_documents({})
    photos = files_col.count_documents({"file_type": "photo"})
    videos = files_col.count_documents({"file_type": "video"})
    documents = files_col.count_documents({"file_type": "document"})
    await update.message.reply_text(
        f"📊 **TeleDrive Storage Statistics**\n\n"
        f"📷 Photos: {photos}\n"
        f"🎥 Videos: {videos}\n"
        f"📄 Documents: {documents}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📁 Total Files: {total_files}",
        parse_mode="Markdown"
    )

async def backup_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    await update.message.reply_text("🔄 ব্যাকআপ প্রক্রিয়া শুরু হচ্ছে...")
    count = await perform_weekly_forward_backup(context.bot)
    await update.message.reply_text(f"✅ ব্যাকআপ সফল! মোট {count} টি নতুন ফাইল ফরোয়ার্ড করা হয়েছে।")

async def delete_record_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("⚠️ যে ফাইলটি ডাটাবেস থেকে মুছতে চান, সেই মেসেজটিতে রিপ্লাই দিয়ে `/delete` লিখুন।")
        return
    
    replied_msg_id = update.message.reply_to_message.message_id
    result = files_col.delete_one({"message_id": replied_msg_id})
    
    if result.deleted_count > 0:
        await update.message.reply_text("✅ ফাইলটি ডাটাবেস থেকে সফলভাবে মুছে ফেলা হয়েছে!")
    else:
        await update.message.reply_text("⚠️ এই ফাইলটির কোনো রেকর্ড ডাটাবেসে পাওয়া যায়নি।")

async def encrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /encrypt <পাসওয়ার্ড> <আপনার টেক্সট>")
        return
    key, raw_text = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔐 **Encrypted:**\n`{cipher_text(raw_text, key)}`", parse_mode="Markdown")

async def decrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /decrypt <পাসওয়ার্ড> <লক করা টেক্সট>")
        return
    key, ciphered_text = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔓 **Decrypted:**\n{cipher_text(ciphered_text, key, decrypt=True)}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    if not context.args:
        await update.message.reply_text("ব্যবহার: /search <কিওয়ার্ড>")
        return
    keyword = " ".join(context.args)
    results = search_files(keyword)
    if not results:
        await update.message.reply_text(f"'{keyword}' দিয়ে কিছু পাওয়া যায়নি।")
        return
    lines = [f"🔍 '{keyword}' এর জন্য রেজাল্ট:\n"]
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
    if message is None or message.chat_id != GROUP_ID: 
        return

    # বট নিজের তৈরি করা মেসেজ রিপ্রসেস করবে না (লুপ এড়াতে)
    if message.from_user and message.from_user.is_bot:
        return

    file_type = "photo" if message.photo else "video" if message.video else "document"
    target_thread = TOPIC_IDS.get(file_type, 12)
    
    # যদি মেসেজটি ইতিমধ্যে সঠিক টার্গেট থ্রেডে বা টপিকে থাকে, তবে সেটি পুনরায় কপি করার দরকার নেই
    if message.message_thread_id == target_thread:
        return

    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
        caption=(message.caption or "") + f"\n\n#{file_type} #TeleDrive"
    )
    
    try:
        c_copied = await context.bot.copy_message(chat_id=CHANNEL_ID, from_chat_id=GROUP_ID, message_id=message.message_id)
        save_file_record(file_type, f"{file_type}_{message.message_id}", message.caption, target_thread, copied.message_id, c_copied.message_id)
    except:
        save_file_record(file_type, f"{file_type}_{message.message_id}", message.caption, target_thread, copied.message_id)

# ============ MAIN ============

async def main_async():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("backup_now", backup_now_command))
    app.add_handler(CommandHandler("delete", delete_record_command))
    app.add_handler(CommandHandler("encrypt", encrypt_command))
    app.add_handler(CommandHandler("decrypt", decrypt_command))
    app.add_handler(InlineQueryHandler(inline_search))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file))
    
    if app.job_queue:
        app.job_queue.run_repeating(weekly_backup_job, interval=604800, first=15)

    print("TeleDrive Bot with multi-topic file routing is running...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())
    
