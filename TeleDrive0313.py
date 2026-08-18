"""
TeleDrive & WhatsApp Bridge Organizer Bot
------------------------------------------
Developer: iamemon13
Bot Name: TeleDrive0313
Features: Multi-topic, MongoDB, Inline Search, Duplicate Check, Direct Link, Encryption, Weekly Auto-Forward Backup & WhatsApp Bridge
"""

import asyncio
import io
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import quote_plus
from flask import Flask, request, jsonify
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
BACKUP_CHANNEL_ID = -1004304201011  

# WhatsApp Config (আপনার দেওয়া পুরনো টোকেন ও আইডি থেকে প্রাপ্ত)
WHATSAPP_TOKEN = 'EAAWeZAG4KXLEBSXmlJ0b0iyKtZAuljh0kXjKyoJuQlF5icofobM6ZAwGlZAhclcOKsoVPtZA7ZBYvJZB2WraVVnFI67oxWWTIpK39YRMlmn6Ej63gvaxBKR9NuogTZBs0edbyzq8Mu2TpNKr10CGnM1TCvFTVnGrPLZCHB0oa48j1VPqKK2WkwZA0H8UeoDZCguXwZDZD'
PHONE_NUMBER_ID = '1355197357667326'
VERIFY_TOKEN = 'yoyoji..'

TOPIC_IDS = {
    "photo": 6,      # 📷 Photos topic id
    "video": 7,      # 🎥 Videos topic id
    "document": 12,  # 📄 Documents topic id
}

IGNORE_THREAD_IDS = set(TOPIC_IDS.values())

# ============ FLASK & WHATSAPP WEBHOOK SERVER ============

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "TeleDrive & WhatsApp Bridge Bot is running alive!"

@app_flask.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if token == VERIFY_TOKEN:
            return challenge, 200
        return 'Invalid token', 403

    elif request.method == 'POST':
        data = request.get_json()
        logger.info(f"Incoming WhatsApp Data: {json.dumps(data)}")
        
        try:
            entries = data.get('entry', [])
            for entry in entries:
                changes = entry.get('changes', [])
                for change in changes:
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    
                    for message in messages:
                        sender_phone = message.get('from')
                        msg_type = message.get('type')
                        
                        # ১. যদি টেক্সট মেসেজ হয়
                        if msg_type == 'text':
                            message_body = message.get('text', {}).get('body')
                            if sender_phone and message_body:
                                # হোয়াটসঅ্যাপে অটো-রিপ্লাই পাঠানো
                                send_whatsapp_message(sender_phone, f"Hello! Received your text: {message_body}")
                                # টেলিগ্রাম গ্রুপেও ফরোয়ার্ড করা
                                send_to_telegram_group(f"📱 WhatsApp থেকে প্রাপ্ত টেক্সট:\n{message_body}")
                        
                        # ২. যদি ডকুমেন্ট বা মিডিয়া ফাইল হয়
                        elif msg_type in ['document', 'image', 'video']:
                            send_whatsapp_message(sender_phone, "ফাইলটি পাওয়া গেছে! টেলিগ্রাম ড্রাইভে ফরোয়ার্ড করা হচ্ছে...")
                            send_to_telegram_group(f"📱 WhatsApp থেকে একটি নতুন {msg_type} ফাইল আপলোড করা হয়েছে। (নম্বর: {sender_phone})")

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}")

        return jsonify({"status": "success"}), 200

def send_whatsapp_message(recipient_phone, text_message):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text_message}
    }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")

def send_to_telegram_group(text):
    """হোয়াটসঅ্যাপের ডেটা সরাসরি টেলিগ্রাম গ্রুপে পাঠানোর ফাংশন"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Failed to send to Telegram group: {e}")

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
        logger.info("No new files found in the last 7 days for backup.")
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
    logger.info("Starting scheduled weekly auto-forward backup...")
    count = await perform_weekly_forward_backup(context.bot)
    logger.info(f"Weekly Auto-Forward Backup Completed. Total forwarded: {count} files.")

# ============ TELEGRAM HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "TeleDrive & WhatsApp Bridge Bot (Developed by @iamemon13) চালু আছে ✅\n\n"
            "📌 টেলিগ্রাম কমান্ডসমূহ:\n"
            "• /search কিওয়ার্ড - ফাইল খুঁজুন\n"
            "• /stats - ড্রাইভের মোট ফাইলের হিসেব দেখুন\n"
            "• /backup_now - বিগত ৭ দিনের নতুন ফাইলগুলো ব্যাকআপ চ্যানেলে ফরোয়ার্ড করুন\n"
            "• /encrypt পাসওয়ার্ড টেক্সট - টেক্সট লক করুন\n"
            "• /decrypt পাসওয়ার্ড টেক্সট - টেক্সট আনলক করুন"
        )

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

async def backup_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text("🔄 বিগত ৭ দিনের নতুন ফাইলগুলো ব্যাকআপ চ্যানেলে ফরোয়ার্ড করা শুরু হচ্ছে...")
    count = await perform_weekly_forward_backup(context.bot)
    
    if count > 0:
        await update.message.reply_text(f"✅ ব্যাকআপ সফল! বিগত ৭ দিনের মোট {count} টি নতুন ফাইল ব্যাকআপ চ্যানেলে ফরোয়ার্ড করা হয়েছে।")
    else:
        await update.message.reply_text("ℹ️ বিগত ৭ দিনের মধ্যে ড্রাইভ বা গ্রুপে নতুন কোনো ফাইল আপলোড হয়নি।")

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
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        link = f"https://t.me/c/{clean_channel_id}/{item.get('channel_msg_id')}" if item.get('channel_msg_id') else "#"
        
        lines.append(f"• [{item.get('file_type')}] [{item.get('file_name')}]({link}) — {date_str}")
        if item.get("caption"):
            lines.append(f"   caption: {item.get('caption')[:60]}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

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

    if is_duplicate(file_name, message.caption):
        logger.info("Duplicate file skipped: %s", file_name)
        return

    target_thread = TOPIC_IDS.get(file_type)
    if target_thread is None:
        logger.warning("No topic configured for file_type=%s", file_type)
        return

    hashtags = f"\n\n#{file_type} #TeleDrive"
    new_caption = (message.caption or "") + hashtags

    copied = await context.bot.copy_message(
        chat_id=GROUP_ID,
        from_chat_id=GROUP_ID,
        message_id=message.message_id,
        message_thread_id=target_thread,
        caption=new_caption
    )

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
    app.add_handler(CommandHandler("backup_now", backup_now_command))
    app.add_handler(CommandHandler("encrypt", encrypt_command))
    app.add_handler(CommandHandler("decrypt", decrypt_command))
    app.add_handler(InlineQueryHandler(inline_search))
    
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_file
        )
    )

    if app.job_queue:
        app.job_queue.run_repeating(
            weekly_backup_job,
            interval=604800,
            first=15
        )

    logger.info("TeleDrive & WhatsApp Bridge Bot by iamemon13 starting...")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    keep_alive()  # ফ্লাস্ক সার্ভার, ওয়েব হুক এবং টেলিগ্রাম বট একসঙ্গে চালু রাখবে
    asyncio.run(main_async())
        
