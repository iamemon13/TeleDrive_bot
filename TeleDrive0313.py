"""
Telegram Drive Organizer Bot
------------------------------
Developer: iamemon13
Bot Name: TeleDrive0313
"""

import asyncio
import logging
import os
from datetime import datetime
from pymongo import MongoClient

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ============ CONFIG ============

BOT_TOKEN = "8958248933:AAELn0ciXF0j72D_rpcHcAqA7pb4zgYBkes"
MONGO_URI = "mongodb+srv://TeleDrive0313_bot:<yoyoji..>@cluster0.xvifgpb.mongodb.net/?appName=Cluster0"

GROUP_ID = -1004449101180

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

def save_file_record(file_type, file_name, caption, thread_id, message_id):
    record = {
        "file_type": file_type,
        "file_name": file_name or "",
        "caption": caption or "",
        "thread_id": thread_id,
        "message_id": message_id,
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

# ============ HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "TeleDrive Bot (Developed by @iamemon13) চালু আছে ✅\n"
        "গ্রুপে ফাইল পাঠালে অটো সঠিক Topic এ চলে যাবে।\n"
        "খুঁজতে চাইলে: /search কিওয়ার্ড"
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        lines.append(f"• [{item.get('file_type')}] {item.get('file_name')} — {date_str}")
        if item.get("caption"):
            lines.append(f"   caption: {item.get('caption')[:60]}")

    await update.message.reply_text("\n".join(lines))

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

    target_thread = TOPIC_IDS.get(file_type)
    if target_thread is None:
        logger.warning("No topic configured for file_type=%s", file_type)
        return

    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
    )

    save_file_record(
        file_type=file_type,
        file_name=file_name,
        caption=message.caption,
        thread_id=target_thread,
        message_id=copied.message_id,
    )

    logger.info("Organized %s -> topic %s", file_name, target_thread)
# ============ MAIN ============

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file
        )
    )

    logger.info("TeleDrive Bot by iamemon13 starting...")
    
    # run_polling ব্যবহার করলে রেন্ডারে Timed Out সমস্যা হবে না
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    

