"""
Telegram Drive Organizer Bot
------------------------------
Developer: iamemon13
Bot Name: TeleDrive0313
Features: Multi-topic, MongoDB, Inline Search, Duplicate Check, Direct Link, Encryption & Backup
"""

import asyncio
import io
import json
import logging
import os
from datetime import datetime
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

# ============ CONFIG ============

BOT_TOKEN = "8958248933:AAE03gFkatEPQPzGf2l5nGiylU1AEKIczX0"

DB_PASSWORD = quote_plus("yoyoji..") 
MONGO_URI = f"mongodb+srv://TeleDrive0313_bot:{DB_PASSWORD}@cluster0.xvifgpb.mongodb.net/?appName=Cluster0"

GROUP_ID = -1004449101180
CHANNEL_ID = -1004304201011

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

# Duplicate Checker
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

# Feature 2: Simple Security Cipher for Sensitive Text
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

# ============ HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "TeleDrive Bot (Developed by @iamemon13) চালু আছে ✅\n\n"
            "📌 কমান্ডসমূহ:\n"
            "• /search কিওয়ার্ড - ফাইল খুঁজুন\n"
            "• /stats - ড্রাইভের মোট ফাইলের হিসেব দেখুন\n"
            "• /encrypt পাসওয়ার্ড টেক্সট - টেক্সট লক করুন\n"
            "• /decrypt পাসওয়ার্ড টেক্সট - টেক্সট আনলক করুন\n"
            "• /backup - ডাটাবেজের ব্যাকআপ ফাইল নিন\n"
            "• Inline Search: অন্য কোনো চ্যাটে `@TeleDrive0313_bot keyword` টাইপ করে ফাইল শেয়ার করুন।"
        )

# Phase 1: Statistics Command
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    total_files = files_col.count_documents({})
    photos = files_col.count_documents({"file_type": "photo"})
    videos = files_col.count_documents({"file_type": "video"})
    documents = files_col.count_documents({"file_type": "document"})

    msg = (
        "📊 **TeleDrive Storage Statistics**\n\n"
        f"📷 Photos: {photos}\n"
        f"🎥 Videos: {videos}\n"
        f"📄 Documents: {documents}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📁 Total Files: {total_files}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# Feature 3: Database Backup Handler
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    records = list(files_col.find({}, {"_id": 0}))
    json_data = json.dumps(records, indent=4)
    
    file_bytes = io.BytesIO(json_data.encode("utf-8"))
    file_bytes.name = f"teledrive_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    await update.message.reply_document(
        document=file_bytes,
        caption="🔒 **TeleDrive DB Auto-Backup Complete!**\nসব ফাইল তথ্যের ব্যাকআপ ফাইল সংযুক্ত করা হলো।",
        parse_mode="Markdown"
    )

# Feature 2: Encryption/Decryption Commands
async def encrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /encrypt <পাসওয়ার্ড> <আপনার গোপন তথ্য>")
        return
    
    key = context.args[0]
    raw_text = " ".join(context.args[1:])
    encrypted = cipher_text(raw_text, key)
    
    await update.message.reply_text(f"🔐 **Encrypted Data:**\n`{encrypted}`", parse_mode="Markdown")

async def decrypt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or len(context.args) < 2:
        await update.message.reply_text("ব্যবহার: /decrypt <পাসওয়ার্ড> <লক করা টেক্সট>")
        return
    
    key = context.args[0]
    ciphered_text = " ".join(context.args[1:])
    decrypted = cipher_text(ciphered_text, key, decrypt=True)
    
    await update.message.reply_text(f"🔓 **Decrypted Data:**\n{decrypted}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("ব্যবহার: /search কিওয়ার্ড\nযেমন: /search cv")
        return

    keyword = " ".join(context.args)
    results = search_files(keyword)

    if not results:
        await update.message.reply_text(f"'{keyword}' দিয়ে কিছু পাওয়া যায়নি।")
        return

    lines = [f"🔍 '{keyword}' এর জন্য {len(results)}টা রেজাল্ট:\n"]
    for item in results:
        date_str = item.get("date", "").split("T")[0]
        # Phase 3: Channel Link Generation
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        link = f"https://t.me/c/{clean_channel_id}/{item.get('channel_msg_id')}" if item.get('channel_msg_id') else "#"
        
        lines.append(f"• [{item.get('file_type')}] [{item.get('file_name')}]({link}) — {date_str}")
        if item.get("caption"):
            lines.append(f"   caption: {item.get('caption')[:60]}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

# Phase 2: Inline Search Feature
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return

    results = search_files(query)
    inline_results = []

    for item in results:
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        link = f"https://t.me/c/{clean_channel_id}/{item.get('channel_msg_id')}" if item.get('channel_msg_id') else "#"
        
        content = (
            f"📁 **File:** {item.get('file_name')}\n"
            f"📌 **Type:** {item.get('file_type')}\n"
            f"🔗 **Link:** [Open in Channel]({link})"
        )
        
        inline_results.append(
            InlineQueryResultArticle(
                id=str(item.get("_id")),
                title=f"[{item.get('file_type').upper()}] {item.get('file_name')}",
                description=item.get("caption") or "TeleDrive File",
                input_message_content=InputTextMessageContent(content, parse_mode="Markdown", disable_web_page_preview=True)
            )
        )

    await update.inline_query.answer(inline_results[:10])

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or message.chat_id != GROUP_ID:
        return

    if message.message_thread_id in IGNORE_THREAD_IDS:
        return

    file_type = None
    file_name = None

    if message.photo:
        file_type = "photo"
        file_name = f"photo_{message.message_id}.jpg"
    elif message.video:
        file_type = "video"
        file_name = message.video.file_name or f"video_{message.message_id}.mp4"
    elif message.document:
        doc = message.document
        file_name = doc.file_name or f"doc_{message.message_id}"
        mime_type = doc.mime_type or ""
        ext = os.path.splitext(file_name)[1].lower()

        if mime_type.startswith("image/") or ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
            file_type = "photo"
        elif mime_type.startswith("video/") or ext in ['.mp4', '.mkv', '.mov', '.avi']:
            file_type = "video"
        else:
            file_type = "document"
    else:
        return

    # Phase 2: Duplicate Check Verification
    if is_duplicate(file_name, message.caption):
        logger.info("Duplicate file skipped: %s", file_name)
        return

    target_thread = TOPIC_IDS.get(file_type)
    if target_thread is None:
        logger.warning("No topic configured for file_type=%s", file_type)
        return

    # Phase 1: Category Hashtags Addition
    hashtags = f"\n\n#{file_type} #TeleDrive"
    new_caption = (message.caption or "") + hashtags

    # ১. নির্দিষ্ট Topic এ কপি করা
    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
        caption=new_caption
    )

    # ২. চ্যানেল এ কপি করা (Channel Upload)
    channel_msg_id = None
    try:
        channel_copied = await context.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=GROUP_ID,
            message_id=message.message_id,
            caption=new_caption
        )
        channel_msg_id = channel_copied.message_id
        logger.info("Uploaded %s to Channel", file_name)
    except Exception as e:
        logger.error("Failed to copy to channel: %s", e)

    # ৩. MongoDB এ সেভ করা (Phase 3 Link ID সহ)
    save_file_record(
        file_type=file_type,
        file_name=file_name,
        caption=message.caption,
        thread_id=target_thread,
        message_id=copied.message_id,
        channel_msg_id=channel_msg_id
    )

    logger.info("Organized %s -> topic %s", file_name, target_thread)

# ============ MAIN ============

async def main_async():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("encrypt", encrypt_command))
    app.add_handler(CommandHandler("decrypt", decrypt_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(InlineQueryHandler(inline_search))
    
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file
        )
    )

    logger.info("TeleDrive Bot with Encryption & Backup by iamemon13 starting...")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    keep_alive()  # Render Web Service-এর জন্য ব্যাকগ্রাউন্ড পোর্ট ওপেন থাকবে
    asyncio.run(main_async())
    
