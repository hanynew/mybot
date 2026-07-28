import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request
from pymongo import MongoClient
import datetime

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
ADMIN_ID = os.environ.get('ADMIN_ID') # يقوم بسحب رقمك التعريفي من منصة ريندر

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML', threaded=False)
app = Flask(__name__)

# --- إعداد قاعدة البيانات MongoDB ---
MONGO_URI = "mongodb+srv://hanytgribi_db_user:KA1999KA@cluster0.kez5fjj.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['MyBotDB']
users_collection = db['users']

# --- لوحة المفاتيح الرئيسية (UI الجديدة) ---
def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("يوتيوب بريميوم"), KeyboardButton("سبوتيفاي بريميوم"))
    markup.add(KeyboardButton("جيميناي"), KeyboardButton("الهدية اليومية"))
    markup.add(KeyboardButton("شحن البوت عن طريق الإيداع"), KeyboardButton("تواصل مع الإدارة لشحن البوت"))
    markup.add(KeyboardButton("حسابي"), KeyboardButton("دعوة الأصدقاء"))
    markup.add(KeyboardButton("المساعدة"), KeyboardButton("التعليمات"))
    markup.add(KeyboardButton("الرئيسية"))
    return markup

# --- رسالة الترحيب ونظام الدعوات العميق ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    args = message.text.split()
    
    user = users_collection.find_one({"user_id": user_id})

    # تسجيل مستخدم جديد
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "points": 0,
            "invites": 0,
            "last_collected_date": None,
            "streak": 0
        })
        # التحقق من نظام الدعوات (إضافة نقطتين للداعي)
        if len(args) > 1 and args[1].isdigit():
            referrer_id = int(args[1])
            if referrer_id != user_id:
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"points": 2, "invites": 1}}
                )
                try:
                    bot.send_message(referrer_id, "🎉 قام صديق بالتسجيل عبر رابطك! تمت إضافة نقطتين (2) لرصيدك.")
                except:
                    pass

    welcome_text = f"أهلاً بك يا <b>{first_name}</b> في متجرنا الإلكتروني! 🤖\n\nتفضل باختيار ما تريد من القائمة بالأسفل:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# --- الاستجابة لأزرار القائمة السفلية ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        bot.send_message(user_id, "❌ الرجاء إرسال أمر /start أولاً لتسجيل حسابك.")
        return

    # 1. نظام الهدية اليومية (السلسلة التقويمية)
    if text == "الهدية اليومية":
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        last_date = user.get("last_collected_date")
        streak = user.get("streak", 0)

        if last_date == today_str:
            bot.send_message(user_id, "❌ لقد قمت بجمع هديتك اليوم! عد غداً.")
            return
        
        if last_date == yesterday_str:
            streak += 1
        else:
            streak = 1 # تصفير السلسلة وبدء العد من جديد
            
        points_to_add = 2 if streak % 7 == 0 else 1
        
        users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"points": points_to_add}, "$set": {"last_collected_date": today_str, "streak": streak}}
        )
        
        msg = f"✅ تمت إضافة <b>{points_to_add}</b> نقطة إلى رصيدك!\n🔥 سلسلة الدخول: {streak} أيام متتالية."
        bot.send_message(user_id, msg)

    # 2. حسابي
    elif text == "حسابي":
        points = user.get("points", 0)
        invites = user.get("invites", 0)
        name = user.get("first_name", "غير معروف")
        info = f"👤 <b>الاسم:</b> {name}\n⭐ <b>الرصيد:</b> {points} نقطة\n🤝 <b>عدد المدعوين:</b> {invites}"
        bot.send_message(user_id, info)

    # 3. دعوة الأصدقاء
    elif text == "دعوة الأصدقاء":
        bot_info = bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = f"🎁 <b>دعوة الأصدقاء</b>\n\nشارك هذا الرابط مع أصدقائك، وستحصل على نقطتين (2) عن كل شخص يسجل من خلالك:\n\n{invite_link}"
        bot.send_message(user_id, msg)

    # 4. تواصل مع الإدارة
    elif text == "تواصل مع الإدارة لشحن البوت":
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة لشحن رصيدك:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    # 5. يوتيوب بريميوم (قفل الرصيد)
    elif text == "يوتيوب بريميوم":
        points = user.get("points", 0)
        details = "📺 <b>يوتيوب بريميوم</b>\nاستمتع بمشاهدة الفيديوهات بدون إعلانات مع تشغيل في الخلفية.\n\nالتكلفة: 15 نقطة."
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/youtube.html")))
            bot.send_message(user_id, details, reply_markup=markup)
        else:
            bot.send_message(user_id, f"{details}\n\n❌ <b>رصيدك غير كافٍ.</b> رصيدك الحالي {points} نقطة.")

    # 6. سبوتيفاي بريميوم
    elif text == "سبوتيفاي بريميوم":
        points = user.get("points", 0)
        details = "🎵 <b>سبوتيفاي بريميوم</b>\nاستمع للموسيقى بدون إعلانات وبأعلى جودة.\n\nالتكلفة: 15 نقطة."
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/spotify.html")))
            bot.send_message(user_id, details, reply_markup=markup)
        else:
            bot.send_message(user_id, f"{details}\n\n❌ <b>رصيدك غير كافٍ.</b> رصيدك الحالي {points} نقطة.")

    # 7. جيميناي
    elif text == "جيميناي":
        points = user.get("points", 0)
        details = "✨ <b>جيميناي برو</b>\nاحصل على اشتراك الذكاء الاصطناعي الأقوى.\n\nالتكلفة: 15 نقطة."
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/gemini.html")))
            bot.send_message(user_id, details, reply_markup=markup)
        else:
            bot.send_message(user_id, f"{details}\n\n❌ <b>رصيدك غير كافٍ.</b> رصيدك الحالي {points} نقطة.")

    # 8. الأزرار الأخرى
    elif text in ["الرئيسية", "المساعدة", "التعليمات", "شحن البوت عن طريق الإيداع"]:
        bot.send_message(user_id, "سيتم إضافة المحتوى قريباً...")

# --- استقبال بيانات النماذج (التوجيه والخصم) ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
    data = message.web_app_data.data # البيانات القادمة من نموذج HTML

    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("points", 0) >= 15:
        # 1. خصم 15 نقطة
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -15}})
        
        # 2. إرسال الطلب لحساب الأدمن
        if ADMIN_ID:
            admin_msg = f"🔔 <b>طلب جديد!</b>\n\nالعميل: {user_name} ({username})\nرقم العميل: <code>{user_id}</code>\n\nالبيانات المرسلة:\n{data}"
            bot.send_message(ADMIN_ID, admin_msg)
        else:
            print("❌ تحذير: المتغير ADMIN_ID غير موجود، لم يتم إرسال الطلب للإدارة.", flush=True)
        
        # 3. رسالة التأكيد للعميل باللون الأزرق
        success_msg = "طلبك قيد التنفيذ الرجاء الانتظار\n\n<a href='https://t.me/bdallhshay7'>للتواصل والاستفسار</a>"
        
        # 4. إخفاء رسالة النموذج السابقة
        try:
            bot.delete_message(message.chat.id, message.message_id - 1) 
        except:
            pass
            
        bot.send_message(user_id, success_msg, reply_markup=main_keyboard())

# --- إعدادات Webhook ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return "!", 500

@app.route('/setup')
def setup_webhook():
    bot.remove_webhook()
    webhook_url = f"https://{request.host}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    return f"✅ تم تشغيل البوت وربطه بنجاح!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
