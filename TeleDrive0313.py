"""
Telegram Drive Organizer Bot
------------------------------
Developer: iamemon13
Bot Name: TeleDrive0313
"""

import logging
import os
import sqlite3
from datetime import datetime

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
GROUP_ID = -1004449101180

TOPIC_IDS = {
    "photo": 6,      # 📷 Photos topic id
    "video": 7,      # 🎥 Videos topic id
    "document": 12,  # 📄 Documents topic id
}

IGNORE_THREAD_IDS = set(TOPIC_IDS.values())
DB_PATH = "files.db"

# ============ LOGGING ============

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ DATABASE ============

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type TEXT,
            file_name TEXT,
            caption TEXT,
            thread_id INTEGER,
            message_id INTEGER,
            date TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def save_file_record(file_type, file_name, caption, thread_id, message_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO files (file_type, file_name, caption, thread_id, message_id, date) VALUES (?, ?, ?, ?, ?, ?)",
        (
            file_type,
            file_name or "",
            caption or "",
            thread_id,
            message_id,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

def search_files(keyword):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT file_type, file_name, caption, message_id, date FROM files "
        "WHERE file_name LIKE ? OR caption LIKE ? ORDER BY id DESC LIMIT 20",
        (f"%{keyword}%", f"%{keyword}%"),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

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
    for file_type, file_name, caption, message_id, date in results:
        date_str = date.split("T")[0]
        lines.append(f"• [{file_type}] {file_name} — {date_str}")
        if caption:
            lines.append(f"   caption: {caption[:60]}")

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
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file
        )
    )

    logger.info("TeleDrive Bot by iamemon13 starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
