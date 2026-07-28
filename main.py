import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request
from pymongo import MongoClient
import datetime

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML', threaded=False)
app = Flask(__name__)

# --- إعداد قاعدة البيانات MongoDB ---
MONGO_URI = "mongodb+srv://hanytgribi_db_user:KA1999KA@cluster0.kez5fjj.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['MyBotDB']
users_collection = db['users']

# --- نصوص الأزرار ---
BTN_YT = "📺 يوتيوب بريميوم"
BTN_SPOTIFY = "🎵 سبوتيفاي بريميوم"
BTN_GEMINI = "✨ جيميناي"
BTN_DAILY = "🎁 الهدية اليومية"
BTN_DEPOSIT = "💳 شحن البوت عن طريق الإيداع"
BTN_CONTACT = "💬 تواصل مع الإدارة"
BTN_ACCOUNT = "👤 حسابي"
BTN_INVITE = "🤝 دعوة الأصدقاء"
BTN_HELP = "❓ المساعدة"
BTN_GUIDE = "📖 التعليمات"
BTN_MAIN = "🏠 الرئيسية"

# --- لوحة المفاتيح الرئيسية ---
def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton(BTN_YT), KeyboardButton(BTN_SPOTIFY))
    markup.add(KeyboardButton(BTN_GEMINI), KeyboardButton(BTN_DAILY))
    markup.add(KeyboardButton(BTN_DEPOSIT), KeyboardButton(BTN_CONTACT))
    markup.add(KeyboardButton(BTN_ACCOUNT), KeyboardButton(BTN_INVITE))
    markup.add(KeyboardButton(BTN_HELP), KeyboardButton(BTN_GUIDE))
    markup.add(KeyboardButton(BTN_MAIN))
    return markup

# --- رسالة الترحيب ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    args = message.text.split()
    
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "points": 0,
            "invites": 0,
            "last_collected_date": None,
            "streak": 0
        })
        if len(args) > 1 and args[1].isdigit():
            referrer_id = int(args[1])
            if referrer_id != user_id:
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"points": 2, "invites": 1}}
                )
                try:
                    bot.send_message(referrer_id, "🎉 ياي! قام صديق بالتسجيل عبر رابطك! تمت إضافة (2) نقطتين لرصيدك بنجاح.")
                except:
                    pass

    welcome_text = f"أهلاً بك يا <b>{first_name}</b> في متجرنا الإلكتروني! 🤖✨\n\nتفضل باختيار ما تريد من القائمة التفاعلية بالأسفل 👇"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# --- أمر الإدارة (شحن الرصيد) ---
@bot.message_handler(commands=['addpoints'])
def add_points(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        try:
            args = message.text.split()
            if len(args) == 3:
                target_user_id = int(args[1])
                points_to_add = int(args[2])
                
                result = users_collection.update_one(
                    {"user_id": target_user_id},
                    {"$inc": {"points": points_to_add}}
                )
                
                if result.modified_count > 0:
                    bot.send_message(message.chat.id, f"✅ تمت إضافة <b>{points_to_add}</b> نقطة بنجاح للمستخدم <code>{target_user_id}</code>.", parse_mode="HTML")
                    try:
                        bot.send_message(target_user_id, f"🎉 <b>تم شحن حسابك!</b>\n\nلقد قامت الإدارة بإضافة <b>{points_to_add}</b> نقطة إلى رصيدك.\nاستمتع بخدماتنا! ✨", parse_mode="HTML")
                    except:
                        pass
                else:
                    bot.send_message(message.chat.id, "❌ لم يتم العثور على هذا المستخدم.")
            else:
                bot.send_message(message.chat.id, "⚠️ الاستخدام: /addpoints [رقم_العميل] [النقاط]")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {e}")
    else:
        bot.send_message(message.chat.id, "⛔️ عذراً، هذا الأمر للإدارة فقط.")

# --- التفاعل مع الأزرار ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        bot.send_message(user_id, "⚠️ الرجاء إرسال أمر /start أولاً لتسجيل حسابك.")
        return

    if text == BTN_DAILY:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        last_date = user.get("last_collected_date")
        streak = user.get("streak", 0)

        if last_date == today_str:
            bot.send_message(user_id, "⏳ لقد قمت بجمع هديتك اليوم! ننتظرك غداً بشوق.")
            return
        if last_date == yesterday_str:
            streak += 1
        else:
            streak = 1
            
        points_to_add = 2 if streak % 7 == 0 else 1
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": points_to_add}, "$set": {"last_collected_date": today_str, "streak": streak}})
        bot.send_message(user_id, f"🎉 مبارك! تمت إضافة <b>{points_to_add}</b> نقطة إلى رصيدك!\n🔥 سلسلة الدخول: {streak} أيام متتالية.")

    elif text == BTN_ACCOUNT:
        points = user.get("points", 0)
        invites = user.get("invites", 0)
        name = user.get("first_name", "غير معروف")
        info = (f"👤 <b>الاسم:</b> {name}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {points} نقطة\n🤝 <b>المدعوين:</b> {invites}")
        bot.send_message(user_id, info)

    elif text == BTN_INVITE:
        bot_info = bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.send_message(user_id, f"🎁 <b>دعوة الأصدقاء</b>\n\nشارك الرابط واحصل على (2) نقطتين عن كل تسجيل:\n\n{invite_link}")

    elif text == BTN_CONTACT:
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    elif text == BTN_YT:
        points = user.get("points", 0)
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/youtube.html")))
            bot.send_message(user_id, "📺 <b>يوتيوب بريميوم</b>\nاستمتع بمشاهدة بدون إعلانات.\n\n💎 <b>التكلفة:</b> 15 نقطة.", reply_markup=markup)
        else:
            bot.send_message(user_id, f"📺 <b>يوتيوب بريميوم</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.")

    elif text == BTN_SPOTIFY:
        points = user.get("points", 0)
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/spotify.html")))
            bot.send_message(user_id, "🎵 <b>سبوتيفاي بريميوم</b>\nاستمع للموسيقى بأعلى جودة.\n\n💎 <b>التكلفة:</b> 15 نقطة.", reply_markup=markup)
        else:
            bot.send_message(user_id, f"🎵 <b>سبوتيفاي بريميوم</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.")

    elif text == BTN_GEMINI:
        points = user.get("points", 0)
        if points >= 15:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url="https://mybot-1-d6wr.onrender.com/gemini.html")))
            bot.send_message(user_id, "✨ <b>جيميناي برو</b>\nالذكاء الاصطناعي الأقوى.\n\n💎 <b>التكلفة:</b> 15 نقطة.", reply_markup=markup)
        else:
            bot.send_message(user_id, f"✨ <b>جيميناي برو</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.")

    elif text in [BTN_MAIN, BTN_HELP, BTN_GUIDE, BTN_DEPOSIT]:
        bot.send_message(user_id, "⏳ سيتم إضافة المحتوى قريباً...")

# --- استقبال البيانات من النماذج ---
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
    data = message.web_app_data.data 

    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("points", 0) >= 15:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -15}})
        
        if ADMIN_ID:
            admin_msg = f"🔔 <b>طلب جديد استلمناه للتو!</b>\n\n👤 العميل: {user_name} ({username})\n🆔 رقم العميل: <code>{user_id}</code>\n\n📋 <b>البيانات المرسلة:</b>\n{data}"
            try:
                bot.send_message(ADMIN_ID, admin_msg)
            except:
                pass
        
        success_msg = "✅ <b>طلبك قيد التنفيذ، الرجاء الانتظار!</b>\n\n<a href='https://t.me/bdallhshay7'>💬 للتواصل والاستفسار اضغط هنا</a>"
        try:
            bot.delete_message(message.chat.id, message.message_id - 1) 
        except:
            pass
            
        bot.send_message(user_id, success_msg, reply_markup=main_keyboard())


# ==========================================
# --- أكواد ونماذج HTML المدمجة (الواجهات) ---
# ==========================================

@app.route('/youtube.html')
def youtube_form():
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; text-align: center; background-color: #f9f9f9; color: #333;}
            input { width: 90%; padding: 12px; margin: 20px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px;}
            button { background-color: #FF0000; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 90%; font-weight: bold;}
        </style>
    </head>
    <body>
        <h2>📺 يوتيوب بريميوم</h2>
        <p>يرجى كتابة الإيميل المراد تفعيل الاشتراك عليه:</p>
        <input type="email" id="email" placeholder="example@gmail.com" required>
        <button onclick="sendData()">تأكيد وطلب التفعيل</button>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function sendData() {
                let email = document.getElementById('email').value;
                if(!email) { alert("⚠️ الرجاء إدخال الإيميل أولاً!"); return; }
                tg.sendData("الخدمة: يوتيوب بريميوم \\nالإيميل: " + email);
            }
        </script>
    </body>
    </html>
    ''', 200

@app.route('/spotify.html')
def spotify_form():
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; text-align: center; background-color: #f9f9f9; color: #333;}
            input { width: 90%; padding: 12px; margin: 20px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px;}
            button { background-color: #1DB954; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 90%; font-weight: bold;}
        </style>
    </head>
    <body>
        <h2>🎵 سبوتيفاي بريميوم</h2>
        <p>يرجى كتابة الإيميل المراد تفعيل الاشتراك عليه:</p>
        <input type="email" id="email" placeholder="example@gmail.com" required>
        <button onclick="sendData()">تأكيد وطلب التفعيل</button>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function sendData() {
                let email = document.getElementById('email').value;
                if(!email) { alert("⚠️ الرجاء إدخال الإيميل أولاً!"); return; }
                tg.sendData("الخدمة: سبوتيفاي بريميوم \\nالإيميل: " + email);
            }
        </script>
    </body>
    </html>
    ''', 200

@app.route('/gemini.html')
def gemini_form():
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; text-align: center; background-color: #f9f9f9; color: #333;}
            input { width: 90%; padding: 12px; margin: 20px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px;}
            button { background-color: #1a73e8; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 90%; font-weight: bold;}
        </style>
    </head>
    <body>
        <h2>✨ جيميناي برو</h2>
        <p>يرجى كتابة الإيميل المراد تفعيل الاشتراك عليه:</p>
        <input type="email" id="email" placeholder="example@gmail.com" required>
        <button onclick="sendData()">تأكيد وطلب التفعيل</button>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function sendData() {
                let email = document.getElementById('email').value;
                if(!email) { alert("⚠️ الرجاء إدخال الإيميل أولاً!"); return; }
                tg.sendData("الخدمة: جيميناي برو \\nالإيميل: " + email);
            }
        </script>
    </body>
    </html>
    ''', 200


# --- إعدادات Webhook لسيرفر Render ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    except:
        return "!", 500

@app.route('/setup')
def setup_webhook():
    bot.remove_webhook()
    webhook_url = f"https://{request.host}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    return f"✅ تم تشغيل البوت وربطه بنجاح!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
