# 🤖 TeleDrive Auto-Forward & Storage Bot

একটি স্বয়ংক্রিয় টেলিগ্রাম বট যা গ্রুপ বা চ্যানেল থেকে বিভিন্ন মিডিয়া ফাইল (ছবি, ভিডিও, ডকুমেন্ট) ফিল্টার করে নির্দিষ্ট টপিকে ফরোয়ার্ড করে এবং তাদের রেকর্ড **MongoDB Atlas** ক্লাউড ডাটাবেজে সংরক্ষণ করে।

---

## ✨ ফিচারসমূহ

* 📁 **স্বয়ংক্রিয় ফাইল সোর্টিং:** মেসেজ বা ফাইলের ধরন অনুযায়ী নির্ধারিত টপিক/থ্রেডে ফাইল ফরোয়ার্ড করা।
* ☁️ **ক্লাউড ডাটাবেজ ইন্টিগ্রেশন:** ফাইল নাম, ক্যাপশন, ফাইল আইডি ও থ্রেড তথ্য MongoDB Atlas-এ সেভ থাকে।
* 🔍 **সার্চ অপশন:** `/search <keyword>` দিয়ে ডাটাবেজ থেকে যেকোনো সেভ হওয়া ডাটা খোঁজার সুযোগ।
* ⚡ **২৪/৭ ব্যাকগ্রাউন্ড সার্ভিস:** Render-এর মাধ্যমে সার্ভারে বিরামহীনভাবে চালুর সুযোগ।

---

## 🛠️ প্রয়োজনীয় উপকরণ (Prerequisites)

১. **Python 3.10+**
২. **Telegram Bot Token** (@BotFather থেকে নেওয়া)
৩. **MongoDB Atlas Account** (Free Cluster)
৪. **Render Account** (Background Service ডিপ্লয় করার জন্য)

---

## 📁 ফাইল স্ট্রাকচার

GitHub রিপোজিটরিতে ফাইলগুলো নিচের কাঠামো অনুযায়ী রাখুন:

```text
.
├── TeleDrive0313.py    # বটের মূল পাইথন কোড
├── requirements.txt   # প্রজেক্ট ডিপেন্ডেন্সি ফাইল
└── README.md          # প্রজেক্ট ডকুমেন্টেশন
```

### `requirements.txt` ফাইলের তথ্য:
```text
python-telegram-bot==21.4
pymongo[srv]==4.8.0
httpx
dnspython
```

---

## ⚙️ কনফিগারেশন ও এনভায়রনমেন্ট ফাইল (.env)

লোকাল টেস্টিং বা সিকিউরিটির জন্য আপনার এনভায়রনমেন্ট ভ্যারিয়েবলসমূহ নিচের নিয়মে সেট করুন:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
MONGO_URI=mongodb+srv://<YOUR_DATABASE_USERNAME>:<YOUR_DATABASE_PASSWORD>@cluster0.xxxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

## 🚀 ক্লাউড ডিপ্লয়মেন্ট (MongoDB & Render)

### ১. MongoDB Atlas সেটআপ
1. [MongoDB Atlas](https://cloud.mongodb.com)-এ সাইন ইন করে **M0 Free Cluster** তৈরি করুন।
2. **Database Access**-এ গিয়ে একজন নতুন Database User তৈরি করুন এবং **`Read and write to any database`** পারমিশন দিন।
3. **Network Access**-এ গিয়ে IP Address **`0.0.0.0/0`** (Allow Access from Anywhere) যোগ করুন।
4. **Database > Connect > Drivers** থেকে আপনার Connection String কপি করে টোকেন ও পাসওয়ার্ডের জায়গায় সঠিক তথ্য বসান।

### ২. Render-এ প্রজেক্ট ডিপ্লয়মেন্ট
1. [Render Dashboard](https://dashboard.render.com)-এ সাইন ইন করে **New + > Background Service** নির্বাচন করুন।
2. আপনার GitHub অ্যাকাউন্ট কানেক্ট করে এই রিপোজিটরিটি সিলেক্ট করুন।
3. ডিপ্লয়মেন্ট কনফিগারেশন সেট করুন:
   * **Name:** `teledrive-bot`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python TeleDrive0313.py`
4. **Environment Variables** অপশনে গিয়ে দুটো ভ্যারিয়েবল যোগ করুন:
   * **Key:** `BOT_TOKEN` | **Value:** `YOUR_TELEGRAM_BOT_TOKEN`
   * **Key:** `MONGO_URI` | **Value:** `mongodb+srv://<YOUR_DATABASE_USERNAME>:<YOUR_DATABASE_PASSWORD>@cluster0.xxxxxx.mongodb.net/`
5. **Create Background Service**-এ ক্লিক করে ডিপ্লয় শেষ করুন।

---

## 📖 ব্যবহার বিধি (Usage)

1. বটটি টেলিগ্রাম গ্রুপে যুক্ত করে **Admin Privilege** দিন।
2. গ্রুপে ফাইল বা মেসেজ পাঠালে বটটি তা প্রসেস করে নির্দিষ্ট টপিকে রিডাইরেক্ট করবে এবং তথ্য ডাটাবেজে সেভ করবে।
3. পূর্বে সেভ হওয়া ডাটা খুঁজতে টাইপ করুন:
   ```text
   /search YOUR_KEYWORD
   ```

---

## 🔒 সিকিউরিটি সতর্কতা

* আপনার **BOT_TOKEN**, **MONGO_URI** বা **DATABASE_PASSWORD** কখনো সরাসরি কোনো পাবলিক কোড বা GitHub রিপোজিটরিতে শেয়ার করবেন না।
* সিকিউরিটির জন্য সবসময় Render-এর **Environment Variables** ব্যবহার করুন।
