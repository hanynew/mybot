import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
from pymongo import MongoClient
from datetime import datetime, timedelta

# --- الإعدادات الأساسية ---
# توكن البوت (تأكد أنك أضفت BOT_TOKEN في متغيرات البيئة Environment Variables في منصة Render)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# تفعيل تنسيق HTML في رسائل البوت
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

app = Flask(__name__)

# --- إعداد قاعدة البيانات MongoDB ---
# هذا هو الرابط الخاص بك الجاهز والذي تم ربطه بنجاح
MONGO_URI = 'mongodb+srv://hanytgribi_db_user:KA1999KA@cluster0.kwz5flj.mongodb.net/?retryWrites=true&w=majority'
client = MongoClient(MONGO_URI)
db = client['MyBotDB']
users_collection = db['users']

# --- أزرار القائمة الرئيسية ---
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎁 جمع نقطة اليوم", callback_data="daily_point"))
    markup.row(InlineKeyboardButton("⭐ رصيدي والنقاط", callback_data="my_balance"))
    return markup

# --- أوامر البوت (رسالة الترحيب) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name

    # تسجيل المستخدم في قاعدة البيانات إذا كان يتحدث مع البوت لأول مرة
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "points": 0,
            "last_collected": None
        })

    welcome_text = f"أهلاً بك يا <b>{first_name}</b> في البوت الخاص بنا! 🤖\n\nتفضل باختيار ما تريد من القائمة بالأسفل:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# --- التعامل مع أزرار النقاط ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if call.data == "daily_point":
        now = datetime.now()
        # التحقق مما إذا كان المستخدم قد جمع النقطة خلال 24 ساعة
        if user.get("last_collected"):
            last_time = user["last_collected"]
            if (now - last_time) < timedelta(days=1):
                # لم يمر 24 ساعة، نحسب الوقت المتبقي
                time_left = timedelta(days=1) - (now - last_time)
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                bot.answer_callback_query(call.id, f"❌ لقد جمعت نقطتك مسبقاً! \nالرجاء الانتظار {hours} ساعة و {minutes} دقيقة.", show_alert=True)
                return

        # إضافة النقطة وتحديث وقت الجمع في قاعدة البيانات
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"points": 1}, "$set": {"last_collected": now}}
        )
        bot.answer_callback_query(call.id, "✅ مبروك! تمت إضافة نقطة إلى رصيدك بنجاح.", show_alert=True)

    elif call.data == "my_balance":
        points = user.get("points", 0)
        bot.answer_callback_query(call.id, f"⭐ رصيدك الحالي هو: {points} نقطة.", show_alert=True)

# --- إعدادات Webhook لسيرفر Render ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/setup')
def setup_webhook():
    bot.remove_webhook()
    # يقوم بجلب رابط Render تلقائياً ويربطه بالبوت
    webhook_url = request.host_url + BOT_TOKEN
    bot.set_webhook(url=webhook_url)
    return f"✅ تم تشغيل البوت وربطه بنجاح!<br>الرابط المستخدم: {webhook_url}", 200

@app.route('/')
def index():
    return "البوت يعمل بنجاح 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
