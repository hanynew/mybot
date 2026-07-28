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

# قاموس لتتبع حالة الأدمن أثناء الرد على العملاء
admin_states = {}

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

# --- التعامل مع أوامر الكول باك (زر الرد من الأدمن) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_button(call):
    if str(call.from_user.id) == str(ADMIN_ID):
        target_id = call.data.split('_')[1]
        admin_states[call.from_user.id] = {'action': 'replying', 'target_user': target_id}
        bot.send_message(ADMIN_ID, f"✍️ <b>وضع الرد مفعل:</b>\nاكتب رسالتك الآن ليتم إرسالها للعميل صاحب الـ ID: <code>{target_id}</code>\n\n(لإلغاء الرد أرسل /cancel)", parse_mode="HTML")
        bot.answer_callback_query(call.id)

# --- التفاعل مع النصوص والأزرار ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text

    # التحقق مما إذا كان الأدمن في وضع "الرد على العميل"
    if user_id in admin_states and admin_states[user_id].get('action') == 'replying':
        if text == '/cancel':
            del admin_states[user_id]
            bot.send_message(user_id, "🚫 تم إلغاء وضع الرد.")
            return
        
        target_user = admin_states[user_id]['target_user']
        try:
            bot.send_message(target_user, f"📩 <b>رسالة من الإدارة:</b>\n\n{text}", parse_mode="HTML")
            bot.send_message(user_id, f"✅ تم إرسال رسالتك للعميل بنجاح.")
        except:
            bot.send_message(user_id, "❌ فشل الإرسال، يبدو أن العميل قام بإيقاف البوت.")
        
        del admin_states[user_id] # إنهاء وضع الرد بعد الإرسال
        return

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
        # خصم النقاط تلقائياً
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -15}})
        
        # إرسال الطلب للأدمن مع زر الرد المباشر
        if ADMIN_ID:
            admin_msg = f"🔔 <b>طلب جديد استلمناه للتو!</b>\n\n👤 العميل: {user_name} ({username})\n🆔 رقم العميل: <code>{user_id}</code>\n\n📋 <b>البيانات المرسلة:</b>\n{data}"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{user_id}"))
            try:
                bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup)
            except:
                pass
        
        # إخفاء رسالة فتح النموذج السابقة من شات العميل
        try:
            bot.delete_message(message.chat.id, message.message_id - 1) 
        except:
            pass
            
        success_msg = "✅ <b>طلبك قيد التنفيذ، الرجاء الانتظار!</b>\n\n<a href='https://t.me/bdallhshay7'>💬 للتواصل والاستفسار اضغط هنا</a>"
        bot.send_message(user_id, success_msg, reply_markup=main_keyboard())


# ==========================================
# --- أكواد ونماذج HTML المدمجة (تصاميم جديدة) ---
# ==========================================

@app.route('/youtube.html')
def youtube_form():
    return '''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; text-align: center; padding: 20px; color: #333; margin: 0; }
            .card { background: white; padding: 30px 20px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-top: 20px; }
            h2 { color: #333; margin-top: 0; display: flex; align-items: center; justify-content: center; gap: 8px;}
            p { color: #666; font-size: 15px; margin-bottom: 25px; }
            input { width: 100%; padding: 15px; margin-bottom: 20px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }
            input:focus { border-color: #FF0000; outline: none; }
            button { background-color: #FF0000; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(255,0,0,0.2); }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>يوتيوب بريميوم 📺</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://..." required>
            <button onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function sendData() {
                let link = document.getElementById('link').value;
                if(!link) { alert("⚠️ الرجاء إدخال الرابط أولاً!"); return; }
                tg.sendData("الخدمة: يوتيوب بريميوم \\nالرابط: " + link);
                tg.close(); // الإغلاق التلقائي
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; text-align: center; padding: 20px; color: #333; margin: 0; }
            .card { background: white; padding: 30px 20px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-top: 20px; }
            h2 { color: #333; margin-top: 0; display: flex; align-items: center; justify-content: center; gap: 8px;}
            p { color: #666; font-size: 15px; margin-bottom: 25px; }
            input { width: 100%; padding: 15px; margin-bottom: 20px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }
            input:focus { border-color: #1DB954; outline: none; }
            button { background-color: #1DB954; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(29,185,84,0.2); }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>سبوتيفاي بريميوم 🎵</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://..." required>
            <button onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function sendData() {
                let link = document.getElementById('link').value;
                if(!link) { alert("⚠️ الرجاء إدخال الرابط أولاً!"); return; }
                tg.sendData("الخدمة: سبوتيفاي بريميوم \\nالرابط: " + link);
                tg.close(); // الإغلاق التلقائي
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f0f2f5; color: #333; }
            .header { background-color: #0f9d58; color: white; padding: 25px 20px; text-align: right; border-bottom-left-radius: 15px; border-bottom-right-radius: 15px;}
            .header h2 { margin: 0; font-size: 26px; display: flex; align-items: center; justify-content: flex-start; gap: 10px; }
            .header p { margin: 5px 0 0; font-size: 15px; opacity: 0.9; }
            .badge { display: inline-block; background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 15px; font-size: 13px; margin-top: 15px; }
            .form-container { background: white; margin: -15px 15px 20px; padding: 25px 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); position: relative; z-index: 1; }
            .form-group { margin-bottom: 22px; text-align: right; }
            .section-title { font-size: 14px; color: #0f9d58; margin-bottom: 15px; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 5px;}
            .form-group label { display: block; margin-bottom: 8px; font-weight: bold; font-size: 13px; color: #555; }
            .input-wrapper { position: relative; }
            input, textarea { width: 100%; padding: 14px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-size: 15px; box-sizing: border-box; font-family: inherit; transition: 0.3s; background-color: #fafafa;}
            input:focus, textarea:focus { outline: none; border-color: #0f9d58; background-color: white;}
            .toggle-password { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); cursor: pointer; color: #888; font-size: 18px;}
            .helper-text { font-size: 11px; color: #888; margin-top: 8px; display: block; line-height: 1.4;}
            .submit-btn { background-color: #0f9d58; color: white; border: none; padding: 16px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 10px;}
            .footer-note { text-align: center; font-size: 11px; color: #aaa; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2>أتمتة البكسل</h2>
            <p>لتفعيل Google One املأ معلومات</p>
            <div class="badge">🕒 عملة | $251.00</div>
        </div>
        <div class="form-container">
            <div class="section-title">👤 حساب جوجل</div>
            
            <div class="form-group">
                <label>Gmail عنوان</label>
                <input type="email" id="email" placeholder="example@gmail.com" required>
            </div>
            
            <div class="form-group">
                <label>كلمة مرور جيميل</label>
                <div class="input-wrapper">
                    <input type="password" id="password" placeholder="الخاصة بك Gmail أدخل كلمة مرور" required>
                    <span class="toggle-password" onclick="togglePwd()">👁️</span>
                </div>
            </div>
            
            <div class="section-title" style="margin-top: 30px;">🔓 المصادقة الثنائية</div>
            
            <div class="form-group">
                <label>سر المصادقة الثنائية (TOTP)</label>
                <input type="text" id="totp" placeholder="على سبيل المثال: JBSWY3DPEHPK3PXP">
                <span class="helper-text">ℹ️ Base32 حرفًا 32 :Google Authenticator المفتاح السري من (والأرقام من 2 إلى 7 Z إلى A الحروف من) بالضبط.</span>
            </div>
            
            <div class="form-group">
                <label>رموز النسخ الاحتياطي <span style="color:#aaa; font-weight:normal;">(خيار)</span></label>
                <textarea id="backup" rows="3" placeholder="سطر واحد من التعليمات البرمجية في كل سطر..."></textarea>
                <span class="helper-text">ℹ️ رمز واحد في كل سطر، 2-3 رموز مطلوبة؛ يتكون كل رمز من 8 أرقام بالضبط.</span>
            </div>
            
            <button class="submit-btn" onclick="sendData()">تأكيد وتفعيل ⚡</button>
            <div class="footer-note">يتم استخدام المعلومات فقط لهذا التنشيط ولا يتم حفظها.</div>
        </div>
        
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            
            function togglePwd() {
                let pwd = document.getElementById("password");
                if(pwd.type === "password") { pwd.type = "text"; } else { pwd.type = "password"; }
            }
            
            function sendData() {
                let email = document.getElementById('email').value;
                let pwd = document.getElementById('password').value;
                let totp = document.getElementById('totp').value;
                let backup = document.getElementById('backup').value;
                
                if(!email || !pwd) { alert("⚠️ الرجاء إدخال الإيميل وكلمة المرور الأساسية!"); return; }
                
                let dataString = "الخدمة: جيميناي برو (أتمتة البكسل)\\n" + 
                                 "الإيميل: " + email + "\\n" +
                                 "كلمة المرور: " + pwd + "\\n" +
                                 "TOTP: " + totp + "\\n" +
                                 "رموز الاحتياط: " + backup;
                
                tg.sendData(dataString);
                tg.close(); // الإغلاق التلقائي للنافذة
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
