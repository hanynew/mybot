import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify
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
settings_collection = db['settings'] # قاعدة بيانات جديدة للإعدادات المرنة

# --- جلب إعدادات المتجر ---
def get_settings():
    s = settings_collection.find_one({"_id": "bot_settings"})
    if not s:
        s = {"_id": "bot_settings", "service_price": 15, "referral_bonus": 2}
        settings_collection.insert_one(s)
    return s

admin_states = {}

# --- نصوص أزرار المستخدمين ---
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

# --- لوحة المفاتيح الرئيسية للعملاء ---
def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton(BTN_YT), KeyboardButton(BTN_SPOTIFY))
    markup.add(KeyboardButton(BTN_GEMINI), KeyboardButton(BTN_DAILY))
    markup.add(KeyboardButton(BTN_DEPOSIT), KeyboardButton(BTN_CONTACT))
    markup.add(KeyboardButton(BTN_ACCOUNT), KeyboardButton(BTN_INVITE))
    markup.add(KeyboardButton(BTN_HELP), KeyboardButton(BTN_GUIDE))
    markup.add(KeyboardButton(BTN_MAIN))
    return markup

# --- لوحة تحكم الإدارة (تظهر لك فقط) ---
def admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🚫 حظر مستخدم"), KeyboardButton("✅ فك حظر"))
    markup.add(KeyboardButton("➕ إضافة نقاط"), KeyboardButton("➖ سحب نقاط"))
    markup.add(KeyboardButton("📩 رد/رسالة لمستخدم"), KeyboardButton("📢 إذاعة للجميع"))
    markup.add(KeyboardButton("💰 تعديل سعر الخدمات"), KeyboardButton("🎁 تعديل مكافأة الدعوة"))
    markup.add(KeyboardButton(BTN_MAIN)) # للعودة كعميل
    return markup

# --- أمر فتح لوحة الإدارة ---
@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        bot.send_message(message.chat.id, "🛠️ <b>مرحباً بك في لوحة تحكم الإدارة:</b>\nاختر الإجراء الذي تريده من الأزرار بالأسفل 👇", reply_markup=admin_keyboard())
    else:
        bot.send_message(message.chat.id, "⛔️ عذراً، لا تملك صلاحية الدخول.")

# --- رسالة الترحيب ونظام الدعوات ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    args = message.text.split()
    
    user = users_collection.find_one({"user_id": user_id})

    if user and user.get("is_banned", False):
        bot.send_message(user_id, "⛔️ <b>عذراً، تم حظر حسابك من استخدام هذا البوت.</b>", parse_mode="HTML")
        return

    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "points": 0,
            "invites": 0,
            "last_collected_date": None,
            "streak": 0,
            "is_banned": False
        })
        if len(args) > 1 and args[1].isdigit():
            referrer_id = int(args[1])
            if referrer_id != user_id:
                ref_bonus = get_settings().get("referral_bonus", 2)
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"points": ref_bonus, "invites": 1}}
                )
                try:
                    bot.send_message(referrer_id, f"🎉 ياي! قام صديق بالتسجيل عبر رابطك! تمت إضافة ({ref_bonus}) نقطة لرصيدك بنجاح.")
                except:
                    pass

    welcome_text = f"أهلاً بك يا <b>{first_name}</b> في متجرنا الإلكتروني! 🤖✨\n\nتفضل باختيار ما تريد من القائمة التفاعلية بالأسفل 👇"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

# --- زر الرد من تحت الطلب مباشرة (كما هو) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_button(call):
    if str(call.from_user.id) == str(ADMIN_ID):
        target_id = call.data.split('_')[1]
        admin_states[call.from_user.id] = {'action': 'reply_user', 'target': target_id}
        bot.send_message(ADMIN_ID, f"✍️ <b>وضع الرد مفعل:</b>\nاكتب رسالتك الآن للعميل: <code>{target_id}</code>\n\n(لإلغاء الأمر أرسل /cancel)")
        bot.answer_callback_query(call.id)

# --- التفاعل مع كل النصوص (العملاء والإدارة) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    is_admin = (str(user_id) == str(ADMIN_ID))

    # === 1. معالجة حالات الإدارة (لوحة التحكم) ===
    if is_admin and user_id in admin_states:
        if text == '/cancel':
            del admin_states[user_id]
            bot.send_message(user_id, "🚫 تم إلغاء الأمر.", reply_markup=admin_keyboard())
            return
        
        state = admin_states[user_id]
        action = state['action']
        
        try:
            if action == 'ban_user':
                target_id = int(text)
                users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": True}})
                bot.send_message(user_id, f"✅ تم حظر المستخدم {target_id}", reply_markup=admin_keyboard())
            
            elif action == 'unban_user':
                target_id = int(text)
                users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": False}})
                bot.send_message(user_id, f"✅ تم فك الحظر عن {target_id}", reply_markup=admin_keyboard())
                
            elif action == 'add_points':
                parts = text.split()
                target_id = int(parts[0])
                pts = int(parts[1])
                users_collection.update_one({"user_id": target_id}, {"$inc": {"points": pts}})
                bot.send_message(user_id, f"✅ تمت إضافة {pts} نقطة للعميل {target_id}")
                try: bot.send_message(target_id, f"🎉 <b>تم شحن حسابك بـ {pts} نقطة!</b>")
                except: pass

            elif action == 'remove_points':
                parts = text.split()
                target_id = int(parts[0])
                pts = int(parts[1])
                users_collection.update_one({"user_id": target_id}, {"$inc": {"points": -pts}})
                bot.send_message(user_id, f"✅ تم سحب {pts} نقطة من العميل {target_id}")
                
            elif action == 'reply_user_step1':
                admin_states[user_id] = {'action': 'reply_user', 'target': text}
                bot.send_message(user_id, "✍️ اكتب رسالتك الآن التي تريد إرسالها له:")
                return # ننتظر الرسالة
                
            elif action == 'reply_user':
                target_id = int(state['target'])
                bot.send_message(target_id, f"📩 <b>رسالة من الإدارة:</b>\n\n{text}")
                bot.send_message(user_id, "✅ تم إرسال رسالتك للعميل بنجاح.", reply_markup=admin_keyboard())
                
            elif action == 'broadcast':
                users = users_collection.find({})
                count = 0
                for u in users:
                    try:
                        bot.send_message(u['user_id'], f"📢 <b>إعلان من الإدارة:</b>\n\n{text}")
                        count += 1
                    except: pass
                bot.send_message(user_id, f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.", reply_markup=admin_keyboard())

            elif action == 'change_price':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"service_price": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر جميع الخدمات إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                # إشعار جميع المستخدمين بتغيير السعر
                users = users_collection.find({})
                for u in users:
                    try: bot.send_message(u['user_id'], f"📣 <b>تحديث في المتجر:</b>\n\nتم تعديل سعر طلب الخدمات ليصبح <b>{new_price}</b> نقطة. سارع بالطلب الآن!")
                    except: pass

            elif action == 'change_referral':
                new_ref = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"referral_bonus": new_ref}})
                bot.send_message(user_id, f"✅ تم تغيير مكافأة الدعوة إلى {new_ref} نقطة.", reply_markup=admin_keyboard())
        
        except Exception as e:
            bot.send_message(user_id, f"❌ حدث خطأ، يرجى كتابة البيانات بشكل صحيح.\nالخطأ: {e}")
        
        del admin_states[user_id]
        return

    # === 2. معالجة أزرار لوحة الإدارة ===
    if is_admin:
        if text == "🚫 حظر مستخدم":
            admin_states[user_id] = {'action': 'ban_user'}
            bot.send_message(user_id, "أرسل الآن ID المستخدم ليتم حظره:\n(أرسل /cancel للإلغاء)")
            return
        elif text == "✅ فك حظر":
            admin_states[user_id] = {'action': 'unban_user'}
            bot.send_message(user_id, "أرسل الآن ID المستخدم لفك حظره:\n(أرسل /cancel للإلغاء)")
            return
        elif text == "➕ إضافة نقاط":
            admin_states[user_id] = {'action': 'add_points'}
            bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم عدد النقاط.\nمثال: <code>123456789 50</code>", parse_mode="HTML")
            return
        elif text == "➖ سحب نقاط":
            admin_states[user_id] = {'action': 'remove_points'}
            bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم النقاط المسحوبة.\nمثال: <code>123456789 15</code>", parse_mode="HTML")
            return
        elif text == "📩 رد/رسالة لمستخدم":
            admin_states[user_id] = {'action': 'reply_user_step1'}
            bot.send_message(user_id, "أرسل أولاً ID العميل الذي تريد مراسلته:")
            return
        elif text == "📢 إذاعة للجميع":
            admin_states[user_id] = {'action': 'broadcast'}
            bot.send_message(user_id, "أرسل الإعلان الآن وسيتم توزيعه لجميع المستخدمين:")
            return
        elif text == "💰 تعديل سعر الخدمات":
            admin_states[user_id] = {'action': 'change_price'}
            bot.send_message(user_id, "أرسل السعر الجديد للخدمات (رقم فقط، مثلاً 10 أو 25):")
            return
        elif text == "🎁 تعديل مكافأة الدعوة":
            admin_states[user_id] = {'action': 'change_referral'}
            bot.send_message(user_id, "أرسل نقاط المكافأة الجديدة لدعوة الأصدقاء (رقم فقط):")
            return

    # === 3. معالجة العملاء (النظام العادي) ===
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        bot.send_message(user_id, "⚠️ الرجاء إرسال أمر /start أولاً لتسجيل حسابك.")
        return

    if user.get("is_banned", False):
        bot.send_message(user_id, "⛔️ <b>عذراً، حسابك محظور من استخدام الخدمات.</b>", parse_mode="HTML")
        return

    # استدعاء الإعدادات الحالية المرنة
    bot_settings = get_settings()
    service_price = bot_settings.get("service_price", 15)
    ref_bonus = bot_settings.get("referral_bonus", 2)

    if text == BTN_MAIN:
        bot.send_message(user_id, "🏠 مرحباً بك في الرئيسية.", reply_markup=main_keyboard())

    elif text == BTN_DAILY:
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
            
        pts_added = 2 if streak % 7 == 0 else 1
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": pts_added}, "$set": {"last_collected_date": today_str, "streak": streak}})
        bot.send_message(user_id, f"🎉 مبارك! تمت إضافة <b>{pts_added}</b> نقطة إلى رصيدك!\n🔥 سلسلة الدخول: {streak} أيام متتالية.")

    elif text == BTN_ACCOUNT:
        points = user.get("points", 0)
        invites = user.get("invites", 0)
        name = user.get("first_name", "غير معروف")
        bot.send_message(user_id, f"👤 <b>الاسم:</b> {name}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {points} نقطة\n🤝 <b>المدعوين:</b> {invites}")

    elif text == BTN_INVITE:
        bot_info = bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.send_message(user_id, f"🎁 <b>دعوة الأصدقاء</b>\n\nشارك الرابط واحصل على ({ref_bonus}) نقطة عن كل تسجيل:\n\n{invite_link}")

    elif text == BTN_CONTACT:
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    elif text == BTN_YT:
        points = user.get("points", 0)
        if points >= service_price:
            msg = bot.send_message(user_id, f"📺 <b>يوتيوب بريميوم</b>\nاستمتع بمشاهدة بدون إعلانات.\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/youtube.html?uid={user_id}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"📺 <b>يوتيوب بريميوم</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

    elif text == BTN_SPOTIFY:
        points = user.get("points", 0)
        if points >= service_price:
            msg = bot.send_message(user_id, f"🎵 <b>سبوتيفاي بريميوم</b>\nاستمع للموسيقى بأعلى جودة.\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/spotify.html?uid={user_id}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"🎵 <b>سبوتيفاي بريميوم</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

    elif text == BTN_GEMINI:
        points = user.get("points", 0)
        if points >= service_price:
            msg = bot.send_message(user_id, f"✨ <b>جيميناي برو</b>\nالذكاء الاصطناعي الأقوى.\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/gemini.html?uid={user_id}&pts={points}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"✨ <b>جيميناي برو</b>\n\n😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

    elif text in [BTN_HELP, BTN_GUIDE, BTN_DEPOSIT]:
        bot.send_message(user_id, "⏳ سيتم إضافة المحتوى قريباً...")

# ==========================================
# --- نظام API لاستقبال بيانات النماذج ---
# ==========================================
@app.route('/submit_form', methods=['POST'])
def submit_form():
    data = request.json
    user_id = int(data.get('uid'))
    msg_id = int(data.get('msg_id'))
    form_data = data.get('dataString')

    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("is_banned", False):
        return jsonify({"status": "banned"}), 403

    bot_settings = get_settings()
    service_price = bot_settings.get("service_price", 15)

    if user and user.get("points", 0) >= service_price:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -service_price}})
        new_points = user.get("points", 0) - service_price
        
        if ADMIN_ID:
            admin_msg = f"🔔 <b>طلب جديد استلمناه للتو!</b>\n\n👤 العميل: {user.get('first_name', 'عميل')}\n🆔 رقم العميل: <code>{user_id}</code>\n\n📋 <b>البيانات المرسلة:</b>\n{form_data}"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{user_id}"))
            try: bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup)
            except: pass
        
        try: bot.delete_message(user_id, msg_id) 
        except: pass
            
        bot.send_message(user_id, f"🎉 <b>طلبك قيد التنفيذ، الرجاء الانتظار!</b>\n\n⭐ <b>رصيدك المتبقي:</b> {new_points} نقطة.\n\n<a href='https://t.me/bdallhshay7'>💬 للتواصل والاستفسار اضغط هنا</a>")
        return jsonify({"status": "success"}), 200
    
    return jsonify({"status": "error"}), 400

# ==========================================
# --- أكواد ونماذج HTML المدمجة ---
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
            button:disabled { background-color: #ccc; cursor: not-allowed; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>يوتيوب بريميوم 📺</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://..." required>
            <button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            const urlParams = new URLSearchParams(window.location.search);
            const uid = urlParams.get('uid');
            const msg_id = urlParams.get('msg_id');

            function sendData() {
                let link = document.getElementById('link').value;
                if(!link) { alert("⚠️ الرجاء إدخال الرابط أولاً!"); return; }
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerText = "جاري الإرسال...";

                let dataString = "الخدمة: يوتيوب بريميوم \\nالرابط: " + link;
                
                fetch('/submit_form', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, dataString: dataString})
                }).then(response => {
                    tg.close();
                }).catch(err => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";
                });
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
            button:disabled { background-color: #ccc; cursor: not-allowed; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>سبوتيفاي بريميوم 🎵</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://..." required>
            <button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            const urlParams = new URLSearchParams(window.location.search);
            const uid = urlParams.get('uid');
            const msg_id = urlParams.get('msg_id');

            function sendData() {
                let link = document.getElementById('link').value;
                if(!link) { alert("⚠️ الرجاء إدخال الرابط أولاً!"); return; }
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerText = "جاري الإرسال...";

                let dataString = "الخدمة: سبوتيفاي بريميوم \\nالرابط: " + link;
                
                fetch('/submit_form', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, dataString: dataString})
                }).then(response => {
                    tg.close();
                }).catch(err => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";
                });
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
            .submit-btn:disabled { background-color: #ccc; cursor: not-allowed; }
            .footer-note { text-align: center; font-size: 11px; color: #aaa; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2>أتمتة الباقات</h2>
            <p>لتفعيل Google One - Gemini Pro املأ المعلومات</p>
            <div class="badge">⭐ <span id="userPoints">0</span></div>
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
            
            <button id="submitBtn" class="submit-btn" onclick="sendData()">تأكيد وتفعيل ⚡</button>
            <div class="footer-note">يتم استخدام المعلومات فقط لهذا التنشيط ولا يتم حفظها.</div>
        </div>
        
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            
            const urlParams = new URLSearchParams(window.location.search);
            const uid = urlParams.get('uid');
            const msg_id = urlParams.get('msg_id');
            const points = urlParams.get('pts');
            
            if(points) {
                document.getElementById('userPoints').innerText = points;
            }
            
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
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerHTML = "جاري الإرسال... ⏳";

                let dataString = "الخدمة: جيميناي برو (أتمتة الباقات)\\n" + 
                                 "الإيميل: " + email + "\\n" +
                                 "كلمة المرور: " + pwd + "\\n" +
                                 "TOTP: " + totp + "\\n" +
                                 "رموز الاحتياط: " + backup;
                
                fetch('/submit_form', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, dataString: dataString})
                }).then(response => {
                    tg.close();
                }).catch(err => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerHTML = "تأكيد وتفعيل ⚡";
                });
            }
        </script>
    </body>
    </html>
    ''', 200

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
