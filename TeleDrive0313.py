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

# ============ CONFIG (Environment Variables থেকে লোড হবে) ============

BOT_TOKEN = os.environ.get("BOT_TOKEN")

db_password_raw = os.environ.get("DB_PASSWORD", "yoyoji..")
DB_PASSWORD = quote_plus(db_password_raw) 
MONGO_URI = os.environ.get("MONGO_URI") or f"mongodb+srv://TeleDrive0313_bot:{DB_PASSWORD}@cluster0.xvifgpb.mongodb.net/?appName=Cluster0"

GROUP_ID = -1004449101180
CHANNEL_ID = -1004304201011
BACKUP_CHANNEL_ID = -1004304201011  

# WhatsApp Config (Environment Variables থেকে লোড হবে)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "yoyoji..")

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
                                send_whatsapp_message(sender_phone, f"Hello! Received your text: {message_body}")
                                send_to_telegram_group(f"📱 WhatsApp থেকে প্রাপ্ত টেক্সট:\n{message_body}")
                        
                        # ২. যদি ছবি (image) বা ডকুমেন্ট/ভিডিও হয়
                        elif msg_type in ['image', 'document', 'video']:
                            media_data = message.get(msg_type, {})
                            media_id = media_data.get('id')
                            caption = media_data.get('caption', '')
                            if media_id:
                                file_url, mime_type = get_whatsapp_media_details(media_id)
                                if file_url:
                                    send_whatsapp_message(sender_phone, "ফাইলটি পাওয়া গেছে! টেলিগ্রাম ড্রাইভে পাঠানো হচ্ছে...")
                                    
                                    # ফাইল বাইট সরাসরি ডাউনলোড করে টেলিগ্রাম গ্রুপে পাঠানো
                                    file_bytes = download_bytes_from_url(file_url)
                                    if file_bytes:
                                        if msg_type == 'image':
                                            send_photo_bytes_to_telegram(file_bytes, f"📱 WhatsApp Photo ({sender_phone})\n{caption}")
                                        else:
                                            send_document_bytes_to_telegram(file_bytes, f"📱 WhatsApp {msg_type} ({sender_phone})\n{caption}", f"media_{media_id}.jpg" if msg_type=='image' else f"file_{media_id}")
                                    else:
                                        # ব্যাকআপ হিসেবে লিংক পাঠিয়ে দেওয়া যদি বাইট ডাউনলোড ফেইল করে
                                        send_to_telegram_group(f"📱 WhatsApp থেকে একটি {msg_type} এসেছে (নম্বর: {sender_phone})\nডাউনলোড লিংক: {file_url}\n{caption}")

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}")

        return jsonify({"status": "success"}), 200

def get_whatsapp_media_details(media_id):
    """মেটার সার্ভার থেকে মিডিয়ার ডাউনলোডেবল লিংক এবং মাইম টাইপ বের করার ফাংশন"""
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        res_json = response.json()
        return res_json.get("url"), res_json.get("mime_type")
    except Exception as e:
        logger.error(f"Failed to get media details: {e}")
        return None, None

def download_bytes_from_url(file_url):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        res = requests.get(file_url, headers=headers)
        if res.status_code == 200:
            return res.content
    except Exception as e:
        logger.error(f"Failed to download bytes from URL: {e}")
    return None

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
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Failed to send to Telegram group: {e}")

def send_photo_bytes_to_telegram(photo_bytes, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    photo_topic_id = TOPIC_IDS.get("photo", 6)
    files = {"photo": ("whatsapp_photo.jpg", io.BytesIO(photo_bytes))}
    data = {
        "chat_id": GROUP_ID,
        "message_thread_id": photo_topic_id,
        "caption": caption
    }
    try:
        requests.post(url, data=data, files=files)
    except Exception as e:
        logger.error(f"Failed to send photo bytes: {e}")

def send_document_bytes_to_telegram(doc_bytes, caption, filename):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    doc_topic_id = TOPIC_IDS.get("document", 12)
    files = {"document": (filename, io.BytesIO(doc_bytes))}
    data = {
        "chat_id": GROUP_ID,
        "message_thread_id": doc_topic_id,
        "caption": caption
    }
    try:
        requests.post(url, data=data, files=files)
    except Exception as e:
        logger.error(f"Failed to send document bytes: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port, use_reloader=False)

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
                logger.error(f"Failed to forward message: {e}")
    return count

async def weekly_backup_job(context: ContextTypes.DEFAULT_TYPE):
    await perform_weekly_forward_backup(context.bot)

# ============ TELEGRAM HANDLERS ============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("TeleDrive & WhatsApp Bridge Bot (Developed by @iamemon13) চালু আছে ✅")

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
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

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

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())
