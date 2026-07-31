import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify
from pymongo import MongoClient
import datetime
import threading
import time
import re

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
ADMIN_ID = os.environ.get('ADMIN_ID') 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML', threaded=False)
app = Flask(__name__)

# --- إعداد قاعدة البيانات ---
MONGO_URI = "mongodb+srv://hanytgribi_db_user:KA1999KA@cluster0.kez5fjj.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['MyBotDB']
users_collection = db['users']
settings_collection = db['settings']

# --- إعداد قناة ومجموعة المتجر ---
CHANNEL_USERNAME = "@SubGateSA"
GROUP_USERNAME = "@SubGateChat"

# --- دالة الوقت المحلي (توقيت السعودية UTC+3) ---
def get_ksa_time():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=3)

def get_settings():
    s = settings_collection.find_one({"_id": "bot_settings"})
    if not s:
        s = {
            "_id": "bot_settings", "price_yt": 15, "price_spotify": 15, "price_gemini": 15, 
            "referral_bonus": 2, "point_price_sar": 1.0, "point_price_yer": 100.0, "points_per_usdt": 15.0
        }
        settings_collection.insert_one(s)
    
    needs_update = False
    if "point_price_sar" not in s: s["point_price_sar"] = 1.0; needs_update = True
    if "point_price_yer" not in s: s["point_price_yer"] = 100.0; needs_update = True
    if "points_per_usdt" not in s: s["points_per_usdt"] = 15.0; needs_update = True
    if needs_update: settings_collection.update_one({"_id": "bot_settings"}, {"$set": s})
    return s

admin_states = {}
user_states = {} 
user_flood_tracker = {}
user_last_msg = {}

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

def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton(BTN_YT), KeyboardButton(BTN_SPOTIFY))
    markup.add(KeyboardButton(BTN_GEMINI), KeyboardButton(BTN_DAILY))
    markup.add(KeyboardButton(BTN_DEPOSIT), KeyboardButton(BTN_CONTACT))
    markup.add(KeyboardButton(BTN_ACCOUNT), KeyboardButton(BTN_INVITE))
    markup.add(KeyboardButton(BTN_HELP), KeyboardButton(BTN_GUIDE))
    markup.add(KeyboardButton(BTN_MAIN))
    return markup

def group_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton(BTN_DAILY), KeyboardButton(BTN_ACCOUNT))
    return markup

def admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🚫 حظر مستخدم"), KeyboardButton("✅ فك حظر"))
    markup.add(KeyboardButton("➕ إضافة نقاط"), KeyboardButton("➖ سحب نقاط"))
    markup.add(KeyboardButton("📩 رد/رسالة لمستخدم"), KeyboardButton("📢 إذاعة للجميع"))
    markup.add(KeyboardButton("📺 سعر يوتيوب"), KeyboardButton("🎵 سعر سبوتيفاي"))
    markup.add(KeyboardButton("✨ سعر جيميناي"), KeyboardButton("🎁 تعديل مكافأة الدعوة"))
    markup.add(KeyboardButton("⚙️ تعديل سعر النقطة (SAR)"), KeyboardButton("⚙️ تعديل سعر النقطة (YER)"))
    markup.add(KeyboardButton("⚙️ تعديل سعر النقطة (USDT)"), KeyboardButton("📊 إحصائيات المستخدمين"))
    markup.add(KeyboardButton("🔍 استعلام عن مستخدم"), KeyboardButton("🚫 قائمة المحظورين"))
    markup.add(KeyboardButton(BTN_MAIN))
    return markup

def check_user_subscription(user_id):
    if str(user_id) == str(ADMIN_ID): return True
    try:
        if bot.get_chat_member(CHANNEL_USERNAME, user_id).status in ['left', 'kicked']: return False
        if bot.get_chat_member(GROUP_USERNAME, user_id).status in ['left', 'kicked']: return False
        return True
    except: return True

def subscription_required_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    markup.add(InlineKeyboardButton("💬 انضم لمجموعة المناقشة", url=f"https://t.me/{GROUP_USERNAME[1:]}"))
    markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
    return markup

# وظيفة مسح الرسائل الذكية
def delayed_delete(chat_id, user_msg_id, bot_msg_id, delay=3.0):
    def delete_task():
        time.sleep(delay)
        try: bot.delete_message(chat_id, user_msg_id)
        except: pass
        try: bot.delete_message(chat_id, bot_msg_id)
        except: pass
    threading.Thread(target=delete_task).start()

def cleanup_deposit_messages(user_id):
    if user_id in user_states and 'dep_msgs' in user_states[user_id]:
        for msg_id in user_states[user_id]['dep_msgs']:
            try: bot.delete_message(user_id, msg_id)
            except: pass
        user_states[user_id]['dep_msgs'] = []

def track_msg(user_id, msg_id):
    if user_id not in user_states: user_states[user_id] = {}
    if 'dep_msgs' not in user_states[user_id]: user_states[user_id]['dep_msgs'] = []
    user_states[user_id]['dep_msgs'].append(msg_id)

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        bot.send_message(message.chat.id, "🛠️ <b>مرحباً بك في لوحة تحكم الإدارة:</b>\nاختر الإجراء الذي تريده من الأزرار بالأسفل 👇", reply_markup=admin_keyboard())
    else: bot.send_message(message.chat.id, "⛔️ عذراً، لا تملك صلاحية الدخول.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if user and user.get("is_banned", False):
        bot.send_message(user_id, "⛔️ <b>عذراً، تم حظر حسابك نهائياً من المتجر. للتواصل مع الإدارة:</b> @bdallhshay7", parse_mode="HTML")
        return

    if not check_user_subscription(user_id):
        bot.send_message(user_id, "⚠️ <b>عذراً، يجب عليك الانضمام لقناة ومجموعة المتجر أولاً لتتمكن من استخدام البوت!</b>", reply_markup=subscription_required_markup())
        return

    now_str = get_ksa_time().strftime("%Y-%m-%d %H:%M")
    if not user:
        users_collection.insert_one({
            "user_id": user_id, "first_name": message.from_user.first_name, "points": 0, "invites": 0,
            "last_collected_date": None, "streak": 0, "is_banned": False, "is_muted": False, "mute_until": None,
            "join_date": now_str, "last_active": get_ksa_time(), "warning_count": 0
        })
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != user_id:
                rb = get_settings().get("referral_bonus", 2)
                users_collection.update_one({"user_id": ref_id}, {"$inc": {"points": rb, "invites": 1}})
                try: bot.send_message(ref_id, f"🎉 ياي! قام صديق بالتسجيل عبر رابطك! تمت إضافة ({rb}) نقطة لرصيدك بنجاح.")
                except: pass
    else:
        users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": get_ksa_time()}})

    welcome_text = f"أهلاً بك يا <b>{message.from_user.first_name}</b> في متجرنا الإلكتروني <b>بوابة الاشتراكات</b>! 🤖✨\n\nتفضل باختيار ما تريد من القائمة التفاعلية بالأسفل 👇"
    kb = group_keyboard() if message.chat.type in ['group', 'supergroup'] else main_keyboard()
    bot.send_message(message.chat.id, welcome_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    if check_user_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح! أهلاً بك.")
        try: bot.delete_message(call.from_user.id, call.message.message_id)
        except: pass
        send_welcome(call.message)
    else: bot.answer_callback_query(call.id, "❌ لم تقم بالانضمام للقناة أو المجموعة بعد!", show_alert=True)

# ==========================================
# --- نظام أزرار الرد التفاعلية (بدون اختفاء) ---
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_button(call):
    if str(call.from_user.id) == str(ADMIN_ID):
        target_id = call.data.split('_')[1]
        admin_states[call.from_user.id] = {'action': 'reply_user', 'target': target_id}
        bot.send_message(ADMIN_ID, f"✍️ <b>وضع الرد مفعل:</b>\nاكتب رسالتك الآن للعميل: <code>{target_id}</code>\n\n(لإلغاء الأمر أرسل /cancel)", parse_mode="HTML")
        
        try:
            markup = call.message.reply_markup
            if markup:
                for row in markup.keyboard:
                    for btn in row:
                        if btn.callback_data == call.data:
                            btn.text = "✅ تم الرد"
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('srv_app_'))
def handle_service_approve(call):
    if str(call.from_user.id) != str(ADMIN_ID): return bot.answer_callback_query(call.id, "⛔️ للآدمن فقط!", show_alert=True)
    
    parts = call.data.split('_')
    target_id = int(parts[2])
    price = int(parts[3])
    
    user = users_collection.find_one({"user_id": target_id})
    rem_points = user.get("points", 0) if user else 0
    
    email = "غير متوفر"
    if call.message.text and "الإيميل:" in call.message.text:
        match = re.search(r"الإيميل:\s*([^\n]+)", call.message.text)
        if match: email = match.group(1).strip()
        
    msg_template = (
        f"🤖 أتمتة Gemini Pro Pixel\n\n"
        f"{{identifier}}\n\n"
        f"────────────────────────\n\n"
        f"✅ 1. بريد إلكتروني\n✅ 2. تحقق من البريد العشوائي\n✅ 3. كلمة المرور\n"
        f"✅ 4. المصادقة بخطوتين\n✅ 5. طريقة الدفع\n✅ 6. إضافة الدفع\n"
        f"✅ 7. تحقق من العرض\n✅ 8. احصل على العروض\n✅ 9. معالجة الدفع\n✅ 10. مكتمل\n\n"
        f"────────────────────────\n\n"
        f"🎉 تم تفعيل Google One بنجاح!\n\n"
        f"✅ لقد تم تفعيل حساب Google الخاص بك لـ Google One.\n\n"
        f"💰 العملات المتبقية:\n{rem_points} عملة\n\n"
        f"{{footer}}"
    )
    
    msg_user = msg_template.format(identifier=f"📧 البريد الإلكتروني:\n{email}", footer="⏱ شكرًا لانتظاركم.")
    msg_channel = msg_template.format(identifier=f"🆔 آيدي المستخدم:\n{target_id}", footer="🌟 عميل مميز. 👑")
    
    try: bot.send_message(target_id, msg_user)
    except: pass
    try: bot.send_message(CHANNEL_USERNAME, msg_channel)
    except: pass
    
    try:
        markup = call.message.reply_markup
        if markup:
            for row in markup.keyboard:
                for btn in row:
                    if btn.callback_data == call.data:
                        btn.text = "✅ تم التفعيل (مكتمل)"
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    except: pass
    
    bot.answer_callback_query(call.id, "تم التفعيل بنجاح وإرسال الإشعارات.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('srv_rej_'))
def handle_service_reject(call):
    if str(call.from_user.id) != str(ADMIN_ID): return
    parts = call.data.split('_'); target_id = parts[2]; price = parts[3]
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("البريد مشترك سابقًا", callback_data=f"srv_dorej_1_{target_id}_{price}"),
        InlineKeyboardButton("البيانات غير صحيحة", callback_data=f"srv_dorej_2_{target_id}_{price}"),
        InlineKeyboardButton("حذف بيانات الدفع", callback_data=f"srv_dorej_3_{target_id}_{price}"),
        InlineKeyboardButton("🔙 رجوع", callback_data=f"srv_back_{target_id}_{price}")
    )
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('srv_back_'))
def handle_service_back(call):
    parts = call.data.split('_'); target_id = parts[2]; price = parts[3]
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تم التفعيل", callback_data=f"srv_app_{target_id}_{price}"),
        InlineKeyboardButton("❌ رفض الخدمة", callback_data=f"srv_rej_{target_id}_{price}")
    )
    markup.add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{target_id}"))
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('srv_dorej_'))
def handle_service_do_reject(call):
    parts = call.data.split('_'); reason_id = parts[2]; target_id = int(parts[3]); price = int(parts[4])
    
    if reason_id == '1':
        reason = "البريد مشترك"
        msg = "⚠️ هذا البريد الإلكتروني مشترك حاليًا في Google One.\nيرجى إزالة الاشتراك الحالي ثم إعادة المحاولة."
    elif reason_id == '2':
        reason = "بيانات غير صحيحة"
        msg = "⚠️ يرجى التأكد من صحة البيانات المدخلة.\nلم يتم العثور على حساب Google بهذه البيانات."
    else:
        reason = "بيانات دفع موجودة"
        msg = "⚠️ يرجى حذف وسيلة الدفع الحالية من حساب Google ثم إعادة إرسال الطلب."
        
    users_collection.update_one({"user_id": target_id}, {"$inc": {"points": price}})
    markup_user = InlineKeyboardMarkup().add(InlineKeyboardButton("🛒 اشترِ حسابًا جاهزًا", callback_data="buy_ready_options"))
    
    try:
        bot.send_message(target_id, msg, reply_markup=markup_user)
        bot.send_message(target_id, f"🔄 تم استرداد {price} نقطة إلى رصيدك تلقائياً.")
    except: pass
    
    markup_admin = InlineKeyboardMarkup(row_width=2)
    markup_admin.add(
        InlineKeyboardButton("✅ تم التفعيل", callback_data=f"srv_app_{target_id}_{price}"),
        InlineKeyboardButton(f"❌ تم الرفض ({reason})", callback_data="none")
    )
    markup_admin.add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{target_id}"))
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup_admin)
    except: pass
    bot.answer_callback_query(call.id, "تم الرفض وإعادة النقاط للعميل.")

@bot.callback_query_handler(func=lambda call: call.data == "buy_ready_options")
def handle_buy_ready_options(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("1 حساب", callback_data="buy_acc_1"),
        InlineKeyboardButton("2 حساب", callback_data="buy_acc_2"),
        InlineKeyboardButton("اكثر من ٢", callback_data="buy_acc_more")
    )
    bot.edit_message_text("كمية الحسابات التي تود شرائها؟", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_acc_'))
def handle_buy_acc_confirm(call):
    qty = call.data.split('_')[2]
    if qty == '1': price_text = "١ حساب = ١٠ ريال سعودي أو ١٥٠٠ ريال يمني"
    elif qty == '2': price_text = "٢ حساب = ١٦ ريال سعودي أو ٢٥٠٠ ريال يمني"
    else: price_text = "اكثر من ٢ = حسب الاتفاق"

    msg = f"الأسعار:\n{price_text}\n\n⏳ بانتظار موافقة الإدارة، سيتم التواصل معك قريباً."
    bot.edit_message_text(msg, chat_id=call.message.chat.id, message_id=call.message.message_id)

    if ADMIN_ID:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{call.from_user.id}"))
        admin_msg = f"🛒 <b>طلب شراء حساب جاهز!</b>\n\n👤 العميل: {call.from_user.first_name}\n🆔 الآيدي: <code>{call.from_user.id}</code>\n📦 الكمية: {qty}\n\nيرجى التواصل مع العميل:"
        try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
        except: pass

# ==========================================
# --- نظام الإيداع والشحن الآلي المتقدم ---
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "dep_back_method")
def back_to_methods(call):
    user_id = call.from_user.id
    settings = get_settings()
    sar_price, yer_price, usdt_pts = settings.get("point_price_sar", 1.0), settings.get("point_price_yer", 100.0), settings.get("points_per_usdt", 15.0)
    msg = (f"💳 <b>تعليمات الإيداع</b>\n\n📊 <b>سعر الصرف:</b>\n▪️ 1 نقطة = {sar_price:g} SAR\n▪️ 1 نقطة = {yer_price:g} YER\n▪️ 1 USDT = {usdt_pts:g} نقطة\n\n"
           "⚠️ <b>ملاحظة:</b>\n• جميع عمليات الإيداع عبر Binance أو PayPal غير قابلة للاسترداد بعد تنفيذ عملية الدفع.")
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("💳 دفع سعودي", callback_data="dep_method_sar"),
        InlineKeyboardButton("💳 دفع يمني", callback_data="dep_method_yer"),
        InlineKeyboardButton("💳 PayPal", callback_data="dep_method_paypal"),
        InlineKeyboardButton("💳 Binance", callback_data="dep_method_binance")
    )
    bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_method_'))
def handle_deposit_method(call):
    user_id = call.from_user.id
    method = call.data.split('_')[2]
    settings = get_settings()
    sar_price, yer_price, usdt_pts = settings.get("point_price_sar", 1.0), settings.get("point_price_yer", 100.0), settings.get("points_per_usdt", 15.0)

    min_money, min_pts, currency = 0, 0, ""
    if method == "sar": min_money = 10.0; min_pts = int(10.0 / sar_price) if sar_price > 0 else 10; currency = "SAR"
    elif method == "yer": min_money = 2000.0; min_pts = int(2000.0 / yer_price) if yer_price > 0 else 2000; currency = "YER"
    elif method in ["paypal", "binance"]: min_money = 1.0; min_pts = int(usdt_pts); currency = "USDT"

    msg = (f"📌 <b>الحد الأدنى للإيداع:</b> {min_pts} نقطة (يُعادل {min_money:g} {currency})\n\n"
           "أرسل الآن <b>رقماً فقط</b> يمثل إما <b>عدد النقاط</b> التي تريد شراءها، أو <b>المبلغ</b> الذي تريد إيداعه، وسنقوم بحسابه تلقائياً.")
    
    if user_id not in user_states: user_states[user_id] = {}
    user_states[user_id].update({'state': 'waiting_deposit_amount', 'method': method, 'currency': currency, 'min_pts': min_pts, 'min_money': min_money})
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 رجوع", callback_data="dep_back_method"))
    bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_val_'))
def handle_deposit_value(call):
    user_id = call.from_user.id
    parts = call.data.split('_'); method = parts[2]; val_type = parts[3]; val = float(parts[4])
    settings = get_settings()
    sar_price, yer_price, usdt_pts = settings.get("point_price_sar", 1.0), settings.get("point_price_yer", 100.0), settings.get("points_per_usdt", 15.0)

    min_money, min_pts, currency, rate = 0, 0, "", 1
    if method == "sar": min_money, min_pts, currency, rate = 10, int(10/sar_price) if sar_price else 10, "SAR", sar_price
    elif method == "yer": min_money, min_pts, currency, rate = 2000, int(2000/yer_price) if yer_price else 2000, "YER", yer_price
    elif method in ["paypal", "binance"]: min_money, min_pts, currency, rate = 1, int(usdt_pts), "USDT", 1/usdt_pts if usdt_pts else 1

    if val_type == "pts": pts = int(val); money = pts * rate
    else: money = val; pts = int(money / rate) if rate else 0

    if money < min_money or pts < min_pts:
        return bot.answer_callback_query(call.id, f"⚠️ عذراً، الحد الأدنى هو {min_money:g} {currency} ({min_pts} نقطة).", show_alert=True)

    msg = (f"✅ <b>تم الحساب بنجاح:</b>\n▪️ عدد النقاط: <b>{pts}</b> نقطة\n▪️ إجمالي المبلغ المطلوب: <b>{money:g}</b> {currency}\n\n"
           "يرجى اتباع تعليمات التحويل الموجودة أسفل بيانات الدفع.")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ متابعة", callback_data=f"dep_cont_{method}_{pts}_{money}"), InlineKeyboardButton("🔙 رجوع", callback_data="dep_back_method"))
    bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_cont_'))
def handle_deposit_continue(call):
    user_id = call.from_user.id
    parts = call.data.split('_'); method = parts[2]; pts = parts[3]; money = parts[4]

    details = ""
    if method == "sar": details = "💳 <b>الدفع السعودي</b>\nأودع المبلغ إلى الحساب التالي:\n<code>SA123456789</code>"
    elif method == "yer": details = "💳 <b>الدفع اليمني</b>\nأودع المبلغ إلى الحساب التالي:\n<code>YE123456789</code>"
    elif method == "binance": details = "💳 <b>الدفع عبر Binance</b>\nأرسل المبلغ إلى المعرف التالي:\n<code>BE1234567</code>"
    elif method == "paypal": details = "💳 <b>الدفع عبر PayPal</b>\nأرسل المبلغ إلى الحساب التالي:\n<code>Bay123458</code>"

    msg = f"{details}\n\nيرجى تحويل المبلغ بدقة، ثم اختيار الإجراء المناسب أدناه:"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📤 رفع إثبات الدفع", callback_data=f"dep_proof_{method}_{pts}_{money}"), InlineKeyboardButton("⏩ بدون إثبات", callback_data=f"dep_noproof_{method}_{pts}_{money}"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="dep_back_method"))
    bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_proof_'))
def handle_deposit_proof(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    track_id = f"A{get_ksa_time().strftime('%Y%m%d%H%M%S')}"
    
    if user_id not in user_states: user_states[user_id] = {}
    user_states[user_id].update({'state': 'waiting_deposit_proof', 'method': parts[2], 'pts': parts[3], 'money': parts[4], 'track_id': track_id})
    
    msg = bot.send_message(user_id, "📸 <b>يرجى إرسال لقطة شاشة (صورة) لإثبات الدفع الآن:</b>", parse_mode="HTML")
    track_msg(user_id, msg.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_noproof_'))
def handle_deposit_no_proof(call):
    user_id = call.from_user.id
    parts = call.data.split('_'); method = parts[2]; pts = parts[3]; money = parts[4]
    
    track_id = f"A{get_ksa_time().strftime('%Y%m%d%H%M%S')}"
    now_time = get_ksa_time().strftime("%Y-%m-%d %H:%M:%S")
    
    msg = bot.send_message(user_id, f"⏳ <b>تم استلام طلبك وهو قيد المراجعة.</b>\n\nرقم الطلب: <code>{track_id}</code>\nسيتم شحن حسابك تلقائيًا فور اعتماد عملية الإيداع.\nيرجى الانتظار.", parse_mode="HTML")
    track_msg(user_id, msg.message_id)
    bot.answer_callback_query(call.id)

    if ADMIN_ID:
        admin_msg = (
            f"🔔 <b>طلب إيداع/شحن جديد! (بدون إثبات مرفق)</b>\n\n"
            f"👤 الاسم: {call.from_user.first_name}\n"
            f"🆔 الآيدي: <code>{user_id}</code>\n"
            f"💳 وسيلة الدفع: {method.upper()}\n"
            f"💵 المبلغ: {money}\n"
            f"🪙 النقاط: {pts}\n"
            f"⏰ الوقت: {now_time}\n"
            f"🏷️ رقم الطلب: <code>{track_id}</code>\n"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ تأكيد", callback_data=f"dep_admin_app_{user_id}_{pts}_{track_id}"), InlineKeyboardButton("❌ رفض", callback_data=f"dep_admin_rej_{user_id}_{track_id}"))
        markup.add(InlineKeyboardButton("⏳ انتظار", callback_data=f"dep_admin_wait_{user_id}_{track_id}"), InlineKeyboardButton("🔄 طلب إعادة رفع الإثبات", callback_data=f"dep_admin_reup_{user_id}_{track_id}_{method}_{pts}_{money}"))
        try:
            ad_msg = bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="HTML")
            user_states[user_id]['admin_msg_id'] = ad_msg.message_id
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_admin_'))
def handle_admin_deposit_action(call):
    if str(call.from_user.id) != str(ADMIN_ID): return bot.answer_callback_query(call.id, "⛔️ للآدمن فقط!", show_alert=True)
    
    parts = call.data.split('_'); action = parts[2]; target_id = int(parts[3])

    if action == 'app':
        pts = int(parts[4])
        users_collection.update_one({"user_id": target_id}, {"$inc": {"points": pts}})
        try: bot.send_message(target_id, f"🎉 <b>تم اعتماد عملية الدفع بنجاح!</b>\n\nتمت إضافة <b>{pts}</b> نقطة إلى رصيدك. نشكر لك ثقتك بنا! 🚀", parse_mode="HTML")
        except: pass
        if call.message.content_type == 'photo': bot.edit_message_caption(f"{call.message.caption}\n\n✅ <b>تم التأكيد وإضافة النقاط.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        else: bot.edit_message_text(f"{call.message.text}\n\n✅ <b>تم التأكيد وإضافة النقاط.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
    
    elif action == 'rej':
        try: bot.send_message(target_id, "⚠️ <b>تعذر اعتماد عملية الدفع.</b>\n\nتم رفض الطلب من قبل الإدارة لمشاكل في التحويل.", parse_mode="HTML")
        except: pass
        if call.message.content_type == 'photo': bot.edit_message_caption(f"{call.message.caption}\n\n❌ <b>تم رفض الطلب.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        else: bot.edit_message_text(f"{call.message.text}\n\n❌ <b>تم رفض الطلب.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")

    elif action == 'wait':
        try: bot.send_message(target_id, f"⏳ <b>تم استلام طلبك وهو قيد المراجعة.</b>\n\nنظرًا لوجود ضغط في الطلبات، يرجى الانتظار حتى يتم التحقق من عملية الدفع.", parse_mode="HTML")
        except: pass
        if call.message.content_type == 'photo': bot.edit_message_caption(f"{call.message.caption}\n\n⏳ <b>تم وضع الطلب في الانتظار.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        else: bot.edit_message_text(f"{call.message.text}\n\n⏳ <b>تم وضع الطلب في الانتظار.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
    
    elif action == 'reup':
        track_id = parts[4]; method = parts[5]; pts = parts[6]; money = parts[7]
        try:
            msg_to_user = "⚠️ <b>تعذر اعتماد عملية الدفع.</b>\n\nيرجى مراجعة بيانات التحويل والتأكد من صحة عملية الدفع، ثم إرسال إثبات جديد حتى نتمكن من مراجعة الطلب مرة أخرى."
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📤 إعادة رفع الإثبات", callback_data=f"dep_user_reup_{track_id}_{method}_{pts}_{money}"))
            markup.add(InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"dep_user_cancel_{track_id}"))
            bot.send_message(target_id, msg_to_user, reply_markup=markup, parse_mode="HTML")
        except: pass
        if call.message.content_type == 'photo': bot.edit_message_caption(f"{call.message.caption}\n\n🔄 <b>تم طلب إعادة رفع الإثبات من العميل.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        else: bot.edit_message_text(f"{call.message.text}\n\n🔄 <b>تم طلب إعادة رفع الإثبات من العميل.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")

    elif action == 'refund':
        try:
            bot.send_message(target_id, "💳 سيتم إعادة المبلغ إلى حسابكم تلقائيًا خلال مدة لا تتجاوز 24 ساعة.\n\n🤝 نشكركم على ثقتكم بنا.\nونسعد دائمًا بخدمتكم، ونتطلع لخدمتكم في أي وقت.", parse_mode="HTML")
            bot.edit_message_text(f"{call.message.text}\n\n✅ <b>تم إرسال رسالة الاسترجاع.</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        except: pass

    bot.answer_callback_query(call.id, "تم التنفيذ.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dep_user_'))
def handle_user_reup_cancel(call):
    user_id = call.from_user.id
    parts = call.data.split('_')
    action = parts[2]
    track_id = parts[3]

    if action == 'reup':
        method = parts[4]; pts = parts[5]; money = parts[6]
        if user_id not in user_states: user_states[user_id] = {}
        user_states[user_id].update({'state': 'waiting_deposit_proof', 'method': method, 'pts': pts, 'money': money, 'track_id': track_id})
        msg = bot.send_message(user_id, "📸 <b>يرجى إرسال لقطة شاشة (صورة) لإثبات الدفع الآن:</b>", parse_mode="HTML")
        track_msg(user_id, msg.message_id)
        bot.answer_callback_query(call.id)
    
    elif action == 'cancel':
        msg = bot.send_message(user_id, "✅ <b>تم إلغاء الطلب بنجاح.</b>\n\nشكرًا لك على استخدام خدماتنا.\n💙 نتمنى لك وقتًا سعيدًا، ويسعدنا دائمًا خدمتك في أي وقت.", parse_mode="HTML")
        track_msg(user_id, msg.message_id)
        bot.answer_callback_query(call.id)
        
        cleanup_deposit_messages(user_id)

        if ADMIN_ID and user_id in user_states and 'admin_msg_id' in user_states[user_id]:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📨 إرسال رسالة استرجاع المبلغ", callback_data=f"dep_admin_refund_{user_id}"))
            try: bot.send_message(ADMIN_ID, f"❌ <b>قام المستخدم بإلغاء هذا الطلب.</b>\nرقم الطلب: <code>{track_id}</code>", reply_to_message_id=user_states[user_id]['admin_msg_id'], reply_markup=markup, parse_mode="HTML")
            except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_temp_') or call.data.startswith('ban_perm_'))
def handle_moderation_actions(call):
    if str(call.from_user.id) != str(ADMIN_ID): return bot.answer_callback_query(call.id, "⛔️ للآدمن فقط!", show_alert=True)
    parts = call.data.split('_'); action = parts[0]; target_id = int(parts[2])
    
    if action == 'unban':
        try:
            bot.restrict_chat_member(GROUP_USERNAME, target_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            users_collection.update_one({"user_id": target_id}, {"$set": {"is_muted": False, "mute_until": None, "is_banned": False}})
            bot.send_message(target_id, "🌟 <b>تم العفو عنك وإلغاء الإيقاف المؤقت في المجموعة!</b>\n\nنرجو منك الالتزام بقوانين المجموعة وعدم تكرار المخالفة. نورتنا من جديد! 🤝")
            bot.answer_callback_query(call.id, "✅ تم رفع جميع القيود والكتم.")
        except Exception as e: bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)
            
    elif action == 'ban':
        target_id = int(parts[-1])
        users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": True}})
        try:
            bot.ban_chat_member(GROUP_USERNAME, target_id, revoke_messages=True)
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
            bot.send_message(target_id, f"🚫 <b>عذراً، تم حظر حسابك نهائياً من المتجر والمجموعة.</b>\n\nلقد تم اتخاذ هذا القرار الإداري بسبب مخالفة الشروط والتعليمات.\nللتواصل مع الإدارة لطلب رفع الحظر 👇", reply_markup=markup)
            bot.answer_callback_query(call.id, "✅ تم تأكيد الحظر ومسح رسائله.")
        except Exception as e: bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)

# --- استلام الصور (لإثبات الدفع) ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    is_admin = (str(user_id) == str(ADMIN_ID))

    if message.chat.type in ['group', 'supergroup']:
        advanced_group_moderation(message)
        return

    track_msg(user_id, message.message_id)

    if not is_admin and user_id in user_states and user_states[user_id].get('state') == 'waiting_deposit_proof':
        state_info = user_states[user_id]
        method = state_info['method']
        pts = state_info['pts']
        money = state_info['money']
        track_id = state_info.get('track_id', f"A{get_ksa_time().strftime('%Y%m%d%H%M%S')}")
        
        msg = bot.send_message(user_id, f"⏳ <b>جاري التحقق من عملية الدفع...</b>\n\nرقم الطلب: <code>{track_id}</code>\nسيتم شحن حسابك تلقائيًا فور اعتماد عملية الإيداع.\nيرجى الانتظار.", parse_mode="HTML")
        track_msg(user_id, msg.message_id)
        del user_states[user_id]['state'] 

        if ADMIN_ID:
            photo_file_id = message.photo[-1].file_id
            now_time = get_ksa_time().strftime("%Y-%m-%d %H:%M:%S")
            admin_msg = (
                f"🔔 <b>طلب إيداع/شحن جديد!</b>\n\n"
                f"👤 الاسم: {message.from_user.first_name}\n"
                f"🆔 الآيدي: <code>{user_id}</code>\n"
                f"💳 وسيلة الدفع: {method.upper()}\n"
                f"💵 المبلغ المدفوع: {money}\n"
                f"🪙 النقاط المطلوبة: {pts}\n"
                f"⏰ الوقت: {now_time}\n"
                f"🏷️ رقم الطلب: <code>{track_id}</code>\n"
            )
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("✅ تأكيد", callback_data=f"dep_admin_app_{user_id}_{pts}_{track_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"dep_admin_rej_{user_id}_{track_id}")
            )
            markup.add(
                InlineKeyboardButton("⏳ انتظار", callback_data=f"dep_admin_wait_{user_id}_{track_id}"),
                InlineKeyboardButton("🔄 طلب إعادة رفع الإثبات", callback_data=f"dep_admin_reup_{user_id}_{track_id}_{method}_{pts}_{money}")
            )
            try:
                ad_msg = bot.send_photo(ADMIN_ID, photo_file_id, caption=admin_msg, reply_markup=markup, parse_mode="HTML")
                user_states[user_id]['admin_msg_id'] = ad_msg.message_id
            except: pass

# ==========================================
# --- نظام الحماية المتقدم للمجموعات ---
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'], content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation'])
def advanced_group_moderation(message):
    user_id = message.from_user.id
    if str(user_id) == str(ADMIN_ID): return

    if message.content_type == 'text' and message.text in [BTN_DAILY, BTN_ACCOUNT]:
        process_group_buttons(message)
        return

    violation_type = None
    text = message.text or message.caption or ""
    text_lower = text.lower()

    if message.content_type != 'text': violation_type = f"إرسال وسائط ممنوعة ({message.content_type})"

    if not violation_type:
        now = time.time()
        if user_id not in user_flood_tracker: user_flood_tracker[user_id] = []
        user_flood_tracker[user_id] = [t for t in user_flood_tracker[user_id] if now - t < 5]
        user_flood_tracker[user_id].append(now)
        if len(user_flood_tracker[user_id]) >= 4: violation_type = "إرسال رسائل سريعة (فلود / Flood)"

    if not violation_type and text:
        if user_id in user_last_msg:
            if user_last_msg[user_id]['text'] == text_lower:
                user_last_msg[user_id]['count'] += 1
                if user_last_msg[user_id]['count'] >= 3: violation_type = "تكرار نفس الرسالة (سبام / Spam)"
            else: user_last_msg[user_id] = {'text': text_lower, 'count': 1}
        else: user_last_msg[user_id] = {'text': text_lower, 'count': 1}

    link_pattern = r'(http[s]?://|t\.me/|@\w+|\.com|\.net|\.org|\.vip|\.link|\.me)'
    if not violation_type and re.search(link_pattern, text_lower): violation_type = "إرسال روابط أو معرفات خارجية"

    if not violation_type and text:
        clean_text = re.sub(r'[^\w\s]', '', text_lower)
        clean_words = re.sub(r'(.)\1+', r'\1', clean_text).split()
        bad_words = ["سكس", "نيك", "قحب", "شرمط", "شرمو", "مخنث", "ديوث", "طيز", "زبي", "كسك", "سناب", "تعارف", "sex", "porn", "fuck", "nude", "ممحون", "شواذ", "كلب", "حيوان", "زبال", "كلاب", "قحاب", "ورع", "فحل", "موجب", "سالب", "زبك", "كسي"]
        for word in clean_words:
            if any(bad in word for bad in bad_words): violation_type = "ألفاظ مسيئة أو غير أخلاقية"; break
        if not violation_type:
            no_space_text = re.sub(r'[\W_0-9]+', '', text_lower)
            severe_bad = ["شرموط", "قحبه", "ديوث", "مخنث"]
            if any(bad in no_space_text for bad in severe_bad): violation_type = "ألفاظ مسيئة (متحايل عليها)"
            if re.search(r'س[\s\W_]*ك[\s\W_]*س', text_lower) or re.search(r'ن[\s\W_]*ي[\s\W_]*ك', text_lower): violation_type = "ألفاظ مسيئة (متحايل عليها)"

    if not violation_type and text:
        no_space = text.replace(" ", "")
        if re.search(r'(?![هخ])(.)\1{5,}', no_space): violation_type = "محتوى عشوائي (تكرار حروف عبثي)"
        elif any(len(word) > 15 for word in text.split()): violation_type = "رسالة عشوائية (أحرف متلاصقة بلا معنى)"
        elif re.search(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{6,}', text): violation_type = "رسالة عشوائية (أحرف إنجليزية مبهمة)"

    if violation_type:
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        user = users_collection.find_one({"user_id": user_id})
        warnings = user.get("warning_count", 0) if user else 0
        time_str = get_ksa_time().strftime("%Y-%m-%d %H:%M:%S")
        content_display = text if message.content_type == 'text' else f"[{message.content_type}]"
        
        if warnings >= 1:
            users_collection.update_one({"user_id": user_id}, {"$set": {"is_banned": True}})
            try: bot.ban_chat_member(message.chat.id, user_id, revoke_messages=True)
            except: pass
            if ADMIN_ID:
                try: bot.send_message(ADMIN_ID, f"🚨 <b>تم الحظر النهائي والطرد!</b>\n\n👤 الاسم: {message.from_user.first_name}\n🆔 الآيدي: <code>{user_id}</code>\n📌 نوع المخالفة: <b>{violation_type}</b>\n💬 المحتوى:\n<code>{content_display}</code>\n⏰ الوقت: {time_str}\n\n⚡️ <i>الإجراء: تم الحظر النهائي ومسح رسائله.</i>")
                except: pass
        else:
            until_date = int(time.time()) + 7200
            users_collection.update_one({"user_id": user_id}, {"$inc": {"warning_count": 1}, "$set": {"is_muted": True, "mute_until": until_date}})
            try: bot.restrict_chat_member(message.chat.id, user_id, until_date=until_date, can_send_messages=False)
            except: pass
            if ADMIN_ID:
                markup = InlineKeyboardMarkup().row(InlineKeyboardButton("🔓 رفع الكتم", callback_data=f"unban_temp_{user_id}"), InlineKeyboardButton("⛔ حظر نهائي وطرد", callback_data=f"ban_perm_{user_id}"))
                try: bot.send_message(ADMIN_ID, f"🚨 <b>اكتشاف مخالفة وتم الكتم!</b>\n\n👤 الاسم: {message.from_user.first_name}\n🆔 الآيدي: <code>{user_id}</code>\n📌 نوع المخالفة: <b>{violation_type}</b>\n💬 المحتوى:\n<code>{content_display}</code>\n⏰ الوقت: {time_str}\n\n⚡️ <i>الإجراء: تم الحذف والكتم لمدة ساعتين في المجموعة (دون حظره من البوت).</i>", reply_markup=markup)
                except: pass

def process_group_buttons(message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})
    text = message.text

    if not user:
        resp = bot.send_message(message.chat.id, f"⚠️ الرجاء التسجيل في البوت أولاً عبر الخاص يا {message.from_user.first_name}.")
        delayed_delete(message.chat.id, message.message_id, resp.message_id, 3.0)
        return

    if user.get("is_muted", False) and user.get("mute_until", 0) and user.get("mute_until", 0) > time.time():
        resp = bot.send_message(message.chat.id, f"⚠️ عذراً يا {message.from_user.first_name}، أنت معاقب ومكتوم مؤقتاً في المجموعة.")
        delayed_delete(message.chat.id, message.message_id, resp.message_id, 3.0)
        return

    if text == BTN_DAILY:
        today_str = get_ksa_time().strftime("%Y-%m-%d")
        yesterday_str = (get_ksa_time() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        last_date = user.get("last_collected_date")
        streak = user.get("streak", 0)

        if last_date == today_str:
            resp = bot.send_message(message.chat.id, f"⏳ يا {message.from_user.first_name}، لقد قمت بجمع هديتك اليوم! ننتظرك غداً.")
            delayed_delete(message.chat.id, message.message_id, resp.message_id, 3.0)
            return

        streak = streak + 1 if last_date == yesterday_str else 1
        is_seventh_day = (streak % 7 == 0)
        pts_added = 2 if is_seventh_day else 1
        
        new_points = user.get("points", 0) + pts_added
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": pts_added}, "$set": {"last_collected_date": today_str, "streak": streak}})
        
        daily_msg = f"🎉 <b>تسجيل حضور ناجح لـ {message.from_user.first_name}!</b>\n═══════════════════════\n\n💎 +{pts_added} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n💰 الرصيد: {new_points} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n📅 سلسلة الأيام: {streak} {'أيام' if is_seventh_day else 'يوم'}\n═══════════════════════"
        if is_seventh_day: daily_msg += "\n\n🔥 <b>سلسلة 7 أيام!</b>\n\nلقد حصلت على 2 عملة بدلاً من 1 عملة!"
        resp = bot.send_message(message.chat.id, daily_msg, parse_mode="HTML")
        delayed_delete(message.chat.id, message.message_id, resp.message_id, 3.0)

    elif text == BTN_ACCOUNT:
        resp = bot.send_message(message.chat.id, f"👤 <b>الاسم:</b> {user.get('first_name', 'غير معروف')}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {user.get('points', 0)} نقطة\n🤝 <b>المدعوين:</b> {user.get('invites', 0)}", parse_mode="HTML")
        delayed_delete(message.chat.id, message.message_id, resp.message_id, 3.0)

# --- معالجة النصوص (العملاء في الخاص والإدارة) ---
@bot.message_handler(func=lambda message: message.chat.type == 'private')
def handle_private_text(message):
    user_id = message.from_user.id
    text = message.text
    is_admin = (str(user_id) == str(ADMIN_ID))

    track_msg(user_id, message.message_id)

    if not is_admin and user_id in user_states and user_states[user_id].get('state') == 'waiting_deposit_amount':
        if text in [BTN_YT, BTN_SPOTIFY, BTN_GEMINI, BTN_DAILY, BTN_DEPOSIT, BTN_CONTACT, BTN_ACCOUNT, BTN_INVITE, BTN_HELP, BTN_GUIDE, BTN_MAIN]:
            del user_states[user_id]['state']
        else:
            try: val = float(text.replace(',', '.'))
            except:
                msg = bot.send_message(user_id, "⚠️ يرجى إرسال أرقام فقط للحساب.")
                track_msg(user_id, msg.message_id)
                return
            
            method = user_states[user_id]['method']
            currency = user_states[user_id]['currency']
            markup = InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton(f"🪙 {val:g} نقطة", callback_data=f"dep_val_{method}_pts_{val:g}"),
                InlineKeyboardButton(f"💵 {val:g} {currency}", callback_data=f"dep_val_{method}_mon_{val:g}")
            )
            msg = bot.send_message(user_id, f"الرقم المدخل: <b>{val:g}</b>\n\nهل هذا الرقم يمثل عدد النقاط المطلوبة أم المبلغ بـ {currency}؟", reply_markup=markup, parse_mode="HTML")
            track_msg(user_id, msg.message_id)
            del user_states[user_id]['state']
            return

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
                users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": False, "is_muted": False, "mute_until": None, "warning_count": 0}})
                bot.send_message(user_id, f"✅ تم فك الحظر عن {target_id}", reply_markup=admin_keyboard())
                try: bot.unban_chat_member(GROUP_USERNAME, target_id, only_if_banned=True)
                except: pass
                try: bot.send_message(target_id, "🎉 <b>أهلاً بعودتك!</b>\n\nيسعدنا إخبارك بأنه تم رفع الحظر والقيود عن حسابك بنجاح. يمكنك الآن العودة للاستمتاع بخدمات متجرنا والتفاعل في مجموعتنا. ✨\n\nنرجو منك الالتزام بالقوانين لضمان تجربة رائعة للجميع. نورتنا! 🤝", parse_mode="HTML")
                except: pass
            elif action == 'add_points':
                parts = text.split(); target_id = int(parts[0]); pts = int(parts[1])
                users_collection.update_one({"user_id": target_id}, {"$inc": {"points": pts}})
                bot.send_message(user_id, f"✅ تمت إضافة {pts} نقطة للعميل {target_id}")
                try: bot.send_message(target_id, f"🎉 <b>تم شحن حسابك بـ {pts} نقطة!</b>")
                except: pass
            elif action == 'remove_points':
                parts = text.split(); target_id = int(parts[0]); pts = int(parts[1])
                users_collection.update_one({"user_id": target_id}, {"$inc": {"points": -pts}})
                bot.send_message(user_id, f"✅ تم سحب {pts} نقطة من العميل {target_id}")
            elif action == 'reply_user_step1':
                admin_states[user_id] = {'action': 'reply_user', 'target': text}
                bot.send_message(user_id, "✍️ اكتب رسالتك الآن التي تريد إرسالها له:")
                return
            elif action == 'reply_user':
                target_id = int(state['target'])
                bot.send_message(target_id, text)
                bot.send_message(user_id, "✅ تم إرسال رسالتك للعميل بنجاح.", reply_markup=admin_keyboard())
            elif action == 'broadcast':
                for u in users_collection.find({}):
                    try: bot.send_message(u['user_id'], text)
                    except: pass
                bot.send_message(user_id, f"✅ تمت الإذاعة بنجاح.", reply_markup=admin_keyboard())
            
            # --- تعديل أسعار الشحن من لوحة الإدارة ---
            elif action == 'set_price_sar':
                new_val = float(text.replace(',', '.'))
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"point_price_sar": new_val}})
                bot.send_message(user_id, f"✅ تم التحديث. سعر النقطة الآن {new_val} SAR.", reply_markup=admin_keyboard())
            elif action == 'set_price_yer':
                new_val = float(text.replace(',', '.'))
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"point_price_yer": new_val}})
                bot.send_message(user_id, f"✅ تم التحديث. سعر النقطة الآن {new_val} YER.", reply_markup=admin_keyboard())
            elif action == 'set_price_usdt':
                new_val = float(text.replace(',', '.'))
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"points_per_usdt": new_val}})
                bot.send_message(user_id, f"✅ تم التحديث. 1 USDT يعادل الآن {new_val} نقطة.", reply_markup=admin_keyboard())

            elif action == 'change_price_yt':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_yt": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة يوتيوب إلى {new_price} نقطة.", reply_markup=admin_keyboard())
            elif action == 'change_price_spotify':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_spotify": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة سبوتيفاي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
            elif action == 'change_price_gemini':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_gemini": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة جيميناي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
            elif action == 'change_referral':
                new_ref = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"referral_bonus": new_ref}})
                bot.send_message(user_id, f"✅ تم تغيير مكافأة الدعوة إلى {new_ref} نقطة.", reply_markup=admin_keyboard())

            elif action == 'check_user':
                target_id = int(text)
                target_user = users_collection.find_one({"user_id": target_id})
                if target_user:
                    u_name = target_user.get("first_name", "غير معروف")
                    u_pts = target_user.get("points", 0)
                    u_invites = target_user.get("invites", 0)
                    status_str = []
                    if target_user.get("is_banned"): status_str.append("محظور 🚫")
                    elif target_user.get("is_muted"): status_str.append("مكتوم 🔇")
                    else: status_str.append("نشط ✅")
                    bot.send_message(user_id, f"🔍 <b>نتيجة الاستعلام:</b>\n\n👤 <b>الاسم:</b> {u_name}\n🆔 <b>الآيدي:</b> <code>{target_id}</code>\n⭐ <b>الرصيد:</b> {u_pts} نقطة\n🤝 <b>المدعوين:</b> {u_invites} أشخاص\nحالة الحساب: {', '.join(status_str)}", reply_markup=admin_keyboard())
                else: bot.send_message(user_id, "❌ لم يتم العثور على هذا المستخدم في قاعدة البيانات.", reply_markup=admin_keyboard())
        except Exception as e:
            bot.send_message(user_id, f"❌ حدث خطأ، يرجى التحقق من المدخلات.\nالخطأ: {e}")
        del admin_states[user_id]
        return

    if is_admin:
        if text == "🚫 حظر مستخدم": admin_states[user_id] = {'action': 'ban_user'}; bot.send_message(user_id, "أرسل الآن ID المستخدم ليتم حظره:\n(أرسل /cancel للإلغاء)"); return
        elif text == "✅ فك حظر": admin_states[user_id] = {'action': 'unban_user'}; bot.send_message(user_id, "أرسل الآن ID المستخدم لفك حظره ورفع الكتم:\n(أرسل /cancel للإلغاء)"); return
        elif text == "➕ إضافة نقاط": admin_states[user_id] = {'action': 'add_points'}; bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم عدد النقاط.\nمثال: <code>123456789 50</code>", parse_mode="HTML"); return
        elif text == "➖ سحب نقاط": admin_states[user_id] = {'action': 'remove_points'}; bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم النقاط المسحوبة.\nمثال: <code>123456789 15</code>", parse_mode="HTML"); return
        elif text == "📩 رد/رسالة لمستخدم": admin_states[user_id] = {'action': 'reply_user_step1'}; bot.send_message(user_id, "أرسل أولاً ID العميل الذي تريد مراسلته:"); return
        elif text == "📢 إذاعة للجميع": admin_states[user_id] = {'action': 'broadcast'}; bot.send_message(user_id, "أرسل الإعلان الآن وسيتم توزيعه لجميع المستخدمين:"); return
        elif text == "📺 سعر يوتيوب": admin_states[user_id] = {'action': 'change_price_yt'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة يوتيوب (رقم فقط):"); return
        elif text == "🎵 سعر سبوتيفاي": admin_states[user_id] = {'action': 'change_price_spotify'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة سبوتيفاي (رقم فقط):"); return
        elif text == "✨ سعر جيميناي": admin_states[user_id] = {'action': 'change_price_gemini'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة جيميناي (رقم فقط):"); return
        elif text == "🎁 تعديل مكافأة الدعوة": admin_states[user_id] = {'action': 'change_referral'}; bot.send_message(user_id, "أرسل نقاط المكافأة الجديدة لدعوة الأصدقاء (رقم فقط):"); return
        elif text == "⚙️ تعديل سعر النقطة (SAR)": admin_states[user_id] = {'action': 'set_price_sar'}; bot.send_message(user_id, "أرسل سعر النقطة الواحدة بالريال السعودي (مثال: 1 أو 0.5):"); return
        elif text == "⚙️ تعديل سعر النقطة (YER)": admin_states[user_id] = {'action': 'set_price_yer'}; bot.send_message(user_id, "أرسل سعر النقطة الواحدة بالريال اليمني (مثال: 100):"); return
        elif text == "⚙️ تعديل سعر النقطة (USDT)": admin_states[user_id] = {'action': 'set_price_usdt'}; bot.send_message(user_id, "أرسل عدد النقاط التي يحصل عليها العميل مقابل كل 1 USDT (مثال: 15):"); return
        elif text == "🔍 استعلام عن مستخدم": admin_states[user_id] = {'action': 'check_user'}; bot.send_message(user_id, "أرسل ID العميل للاستعلام عن بياناته وحسابه:"); return
        elif text == "📊 إحصائيات المستخدمين":
            all_users = list(users_collection.find({}))
            msg = f"📊 <b>إحصائيات مستخدمي البوت:</b>\n\n👥 <b>العدد الإجمالي:</b> {len(all_users)} مستخدم\n\n<b>قائمة المشتركين:</b>\n"
            for u in all_users[:30]:
                diff_days = (get_ksa_time() - u.get('last_active', get_ksa_time())).days if isinstance(u.get('last_active'), datetime.datetime) else 0
                status_dot = "🟢" if diff_days <= 3 else ("🟡" if diff_days <= 7 else "🔴")
                msg += f"{status_dot} {u.get('first_name', 'مستخدم')} | <code>{u.get('user_id')}</code> | ({u.get('points', 0)} نقطة)\n"
            bot.send_message(user_id, msg, reply_markup=admin_keyboard()); return
        elif text == "🚫 قائمة المحظورين":
            banned_users = list(users_collection.find({"$or": [{"is_banned": True}, {"is_muted": True}]}))
            if not banned_users: bot.send_message(user_id, "✅ لا يوجد أي مستخدم محظور أو مكتوم حالياً.", reply_markup=admin_keyboard())
            else:
                msg = f"🚫 <b>قائمة المحظورين والمكتومين ({len(banned_users)}):</b>\n\n"
                for u in banned_users: msg += f"• {'محظور 🚫' if u.get('is_banned') else 'مكتوم 🔇'} | {u.get('first_name', 'مستخدم')} | <code>{u.get('user_id')}</code>\n"
                bot.send_message(user_id, msg, reply_markup=admin_keyboard())
            return

    users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": get_ksa_time()}})

    if not check_user_subscription(user_id):
        bot.send_message(user_id, "⚠️ <b>عذراً، يجب عليك الانضمام لقناة ومجموعة المتجر أولاً لتتمكن من استخدام البوت!</b>", reply_markup=subscription_required_markup())
        return

    user = users_collection.find_one({"user_id": user_id})
    if not user: return bot.send_message(user_id, "⚠️ الرجاء إرسال أمر /start أولاً لتسجيل حسابك.")
    if user.get("is_banned", False):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
        bot.send_message(user_id, "⛔️ <b>عذراً، حسابك محظور من استخدام الخدمات. للتواصل مع الإدارة:</b>", reply_markup=markup, parse_mode="HTML")
        return

    bot_settings = get_settings()

    if text == BTN_DAILY:
        today_str = get_ksa_time().strftime("%Y-%m-%d")
        yesterday_str = (get_ksa_time() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        last_date = user.get("last_collected_date")
        streak = user.get("streak", 0)

        if last_date == today_str:
            bot.send_message(message.chat.id, "⏳ لقد قمت بجمع هديتك اليوم! ننتظرك غداً بشوق.")
            return

        streak = streak + 1 if last_date == yesterday_str else 1
        is_seventh_day = (streak % 7 == 0)
        pts_added = 2 if is_seventh_day else 1
        
        new_points = user.get("points", 0) + pts_added
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": pts_added}, "$set": {"last_collected_date": today_str, "streak": streak}})
        
        daily_msg = (f"🎉 <b>تسجيل حضور ناجح!</b>\n═══════════════════════\n\n"
                     f"💎 +{pts_added} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n"
                     f"💰 الرصيد: {new_points} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n"
                     f"📅 سلسلة الأيام: {streak} {'أيام' if is_seventh_day else 'يوم'}\n═══════════════════════")
        if is_seventh_day: daily_msg += "\n\n🔥 <b>سلسلة 7 أيام!</b>\n\nلقد حصلت على 2 عملة بدلاً من 1 عملة!"
        bot.send_message(message.chat.id, daily_msg, parse_mode="HTML")

    elif text == BTN_ACCOUNT:
        bot.send_message(message.chat.id, f"👤 <b>الاسم:</b> {user.get('first_name', 'غير معروف')}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {user.get('points', 0)} نقطة\n🤝 <b>المدعوين:</b> {user.get('invites', 0)}", parse_mode="HTML")

    elif text == BTN_MAIN:
        user_states[user_id] = {}
        bot.send_message(user_id, "🏠 مرحباً بك في الرئيسية.", reply_markup=main_keyboard())

    elif text == BTN_INVITE:
        bot.send_message(user_id, f"🎉 <b>دعوة خاصة لك!</b>\n✨ اكتشف أفضل الاشتراكات والخدمات الرقمية، واستمتع بعروض حصرية ومزايا مميزة. 🚀\n\n🎁 شارك الرابط واحصل على ({bot_settings.get('referral_bonus', 2)}) نقطة عن كل تسجيل:\n\nhttps://t.me/{bot.get_me().username}?start={user_id}", parse_mode="HTML")

    elif text == BTN_CONTACT:
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    elif text == BTN_DEPOSIT:
        user_states[user_id] = {'dep_msgs': []}
        sar_price, yer_price, usdt_pts = bot_settings.get("point_price_sar", 1.0), bot_settings.get("point_price_yer", 100.0), bot_settings.get("points_per_usdt", 15.0)
        msg_text = (
            "💳 <b>تعليمات الإيداع</b>\n\n"
            "📊 <b>سعر الصرف:</b>\n"
            f"▪️ 1 نقطة = {sar_price:g} SAR\n"
            f"▪️ 1 نقطة = {yer_price:g} YER\n"
            f"▪️ 1 USDT = {usdt_pts:g} نقطة\n\n"
            "⚠️ <b>ملاحظة:</b>\n"
            "• جميع عمليات الإيداع عبر Binance أو PayPal غير قابلة للاسترداد بعد تنفيذ عملية الدفع."
        )
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("💳 دفع سعودي", callback_data="dep_method_sar"),
            InlineKeyboardButton("💳 دفع يمني", callback_data="dep_method_yer"),
            InlineKeyboardButton("💳 PayPal", callback_data="dep_method_paypal"),
            InlineKeyboardButton("💳 Binance", callback_data="dep_method_binance")
        )
        m = bot.send_message(user_id, msg_text, reply_markup=markup, parse_mode="HTML")
        track_msg(user_id, m.message_id)

    elif text in [BTN_YT, BTN_SPOTIFY, BTN_GEMINI]:
        points = user.get("points", 0)
        price_map = {BTN_YT: bot_settings.get("price_yt", 15), BTN_SPOTIFY: bot_settings.get("price_spotify", 15), BTN_GEMINI: bot_settings.get("price_gemini", 15)}
        service_price = price_map[text]

        if points >= service_price:
            urls = {BTN_YT: "youtube.html", BTN_SPOTIFY: "spotify.html", BTN_GEMINI: "gemini.html"}
            if text == BTN_GEMINI:
                gemini_msg = (
                    f"📸 <b>ترقية Gemini Pro تلقائيًا</b>\n"
                    f"═══════════════════════\n"
                    f"💰 المطلوب: {service_price} عملة |\n"
                    f"💳 رصيدك : {points} عملة |\n"
                    f"═══════════════════════\n"
                    f"⚠️ <b>ملاحظة:</b>\n"
                    f"- يرجى عدم استخدام حساب Gmail تم إنشاؤه حديثًا لترقية Gemini Pro لأن نسبة الحظر تصل إلى 90%.\n"
                    f"- يرجى التفكير بعناية عند استخدام حساب Gmail الرئيسي الخاص بك للترقية نظرًا لوجود خطر قفل الحساب.\n"
                    f"- يرجى التأكد من تمكين التحقق بخطوتين (2FA). <a href='https://myaccount.google.com/signinoptions/two-step-verification'>هنا</a>.\n"
                    f"- إغلاق كافة سجلات الدفع <a href='https://pay.google.com/payments/home#settings'>هنا</a>.\n"
                    f"- مغادرة مجموعة العائلة (إن وجدت) <a href='https://myaccount.google.com/family/details'>هنا</a>.\n"
                    f"- أرسل مره واحدة فقط لحساب Gmail واحد وينتظر حتى يتم الرد عليك.\n"
                    f"- عند التأكد من اتباع كافة التعليمات المذكورة أعلاه ومن صحة المعلومات المدخلة في النموذج، تكون نسبة النجاح في الأعلى 90%.\n"
                    f"- استخدام التعليمات لرؤية التعليمات التفصيلية.\n"
                    f"═══════════════════════\n"
                    f"⚡️ المعلومات التي تقدمها ستكون مشفرة وسرية تمامًا.\n\n"
                    f"انقر فوق الزر أدناه لفتح النموذج:"
                )
                msg = bot.send_message(user_id, gemini_msg, parse_mode="HTML", disable_web_page_preview=True)
            else:
                msg = bot.send_message(user_id, f"{'📺 يوتيوب بريميوم' if text==BTN_YT else '🎵 سبوتيفاي بريميوم'}\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/{urls[text]}?uid={user_id}&pts={points}&service={urls[text].split('.')[0]}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

    elif text in [BTN_HELP, BTN_GUIDE]:
        bot.send_message(user_id, "⏳ سيتم إضافة المحتوى قريباً...")

# ==========================================
# --- نظام API لاستقبال بيانات النماذج ومعالجتها (مع أزرار التفعيل والرفض المتطورة) ---
# ==========================================
@app.route('/submit_form', methods=['POST'])
def submit_form():
    data = request.json
    user_id, msg_id, service_type, form_data = int(data.get('uid')), int(data.get('msg_id')), data.get('service', 'yt'), data.get('dataString')
    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("is_banned", False): return jsonify({"status": "banned"}), 403

    bot_settings = get_settings()
    price_map = {'youtube': bot_settings.get("price_yt", 15), 'spotify': bot_settings.get("price_spotify", 15), 'gemini': bot_settings.get("price_gemini", 15)}
    service_price = price_map.get(service_type, 15)

    if user and user.get("points", 0) >= service_price:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -service_price}})
        new_points = user.get("points", 0) - service_price
        
        if ADMIN_ID:
            # إنشاء أزرار الإدارة الجديدة (تفعيل / رفض / رد)
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("✅ تم التفعيل", callback_data=f"srv_app_{user_id}_{service_price}"),
                InlineKeyboardButton("❌ رفض الخدمة", callback_data=f"srv_rej_{user_id}_{service_price}")
            )
            markup.add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{user_id}"))
            
            try: bot.send_message(ADMIN_ID, f"🔔 <b>طلب جديد استلمناه للتو!</b>\n\n👤 العميل: {user.get('first_name', 'عميل')}\n🆔 رقم العميل: <code>{user_id}</code>\n\n📋 <b>البيانات:</b>\n{form_data}", reply_markup=markup)
            except: pass
            
        try: bot.delete_message(user_id, msg_id) 
        except: pass
        bot.send_message(user_id, f"🎉 <b>طلبك قيد التنفيذ، الرجاء الانتظار!</b>\n\n⭐ <b>رصيدك المتبقي:</b> {new_points} نقطة.\n\n<a href='https://t.me/bdallhshay7'>💬 للتواصل والاستفسار اضغط هنا</a>")
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

# ==========================================
# --- أكواد النماذج HTML المدمجة بالسيرفر ---
# ==========================================
@app.route('/youtube.html')
def youtube_form():
    return '''<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><script src="https://telegram.org/js/telegram-web-app.js"></script><style>body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; text-align: center; padding: 20px; color: #333; margin: 0; }.card { background: white; padding: 30px 20px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-top: 20px; }h2 { color: #333; margin-top: 0; display: flex; align-items: center; justify-content: center; gap: 8px;}p { color: #666; font-size: 15px; margin-bottom: 25px; }input { width: 100%; padding: 15px; margin-bottom: 10px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }input:focus { border-color: #FF0000; outline: none; }button { background-color: #FF0000; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(255,0,0,0.2); margin-top: 10px; }button:disabled { background-color: #ccc; cursor: not-allowed; }@keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }.input-error { border-color: #FF0000 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }.error-msg { color: #FF0000; font-size: 12px; font-weight: bold; margin-bottom: 15px; display: none; text-align: right; }</style></head><body><div class="card"><h2>يوتيوب بريميوم 📺</h2><p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p><input type="url" id="link" placeholder="https://offers.sheerid.com/..." oninput="clearError('link')"><div id="link-error" class="error-msg"></div><button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button></div><script>let tg = window.Telegram.WebApp;tg.expand();const urlParams = new URLSearchParams(window.location.search);const uid = urlParams.get('uid'); const msg_id = urlParams.get('msg_id');function clearError(id) {document.getElementById(id).classList.remove('input-error');document.getElementById(id + '-error').style.display = 'none';}function showError(id, msg) {let el = document.getElementById(id);el.classList.add('input-error');let errEl = document.getElementById(id + '-error');errEl.innerText = msg; errEl.style.display = 'block';setTimeout(() => el.classList.remove('input-error'), 400);}function sendData() {let link = document.getElementById('link').value.trim();let hasArabic = /[\u0600-\u06FF]/.test(link);if(!link.startsWith("https://offers.sheerid.com/") || hasArabic) { let msg = hasArabic ? "⚠️ عذراً، لا يُسمح باستخدام الحروف العربية" : "⚠️ عذراً، يجب أن يبدأ الرابط بـ https://offers.sheerid.com/";showError('link', msg); return; }document.getElementById('submitBtn').disabled = true;document.getElementById('submitBtn').innerText = "Automatic activation";fetch('/submit_form', {method: 'POST', headers: {'Content-Type': 'application/json'},body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'youtube', dataString: "الخدمة: يوتيوب بريميوم \\nالرابط: " + link})}).then(() => tg.close()).catch(() => {alert("حدث خطأ أثناء الإرسال.");document.getElementById('submitBtn').disabled = false;document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";});}</script></body></html>'''

@app.route('/spotify.html')
def spotify_form():
    return '''<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><script src="https://telegram.org/js/telegram-web-app.js"></script><style>body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; text-align: center; padding: 20px; color: #333; margin: 0; }.card { background: white; padding: 30px 20px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-top: 20px; }h2 { color: #333; margin-top: 0; display: flex; align-items: center; justify-content: center; gap: 8px;}p { color: #666; font-size: 15px; margin-bottom: 25px; }input { width: 100%; padding: 15px; margin-bottom: 10px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }input:focus { border-color: #1DB954; outline: none; }button { background-color: #1DB954; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(29,185,84,0.2); margin-top: 10px;}button:disabled { background-color: #ccc; cursor: not-allowed; }@keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }.input-error { border-color: #FF0000 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }.error-msg { color: #FF0000; font-size: 12px; font-weight: bold; margin-bottom: 15px; display: none; text-align: right; }</style></head><body><div class="card"><h2>سبوتيفاي بريميوم 🎵</h2><p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p><input type="url" id="link" placeholder="https://offers.sheerid.com/..." oninput="clearError('link')"><div id="link-error" class="error-msg"></div><button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button></div><script>let tg = window.Telegram.WebApp;tg.expand();const urlParams = new URLSearchParams(window.location.search);const uid = urlParams.get('uid'); const msg_id = urlParams.get('msg_id');function clearError(id) {document.getElementById(id).classList.remove('input-error');document.getElementById(id + '-error').style.display = 'none';}function showError(id, msg) {let el = document.getElementById(id);el.classList.add('input-error');let errEl = document.getElementById(id + '-error');errEl.innerText = msg; errEl.style.display = 'block';setTimeout(() => el.classList.remove('input-error'), 400);}function sendData() {let link = document.getElementById('link').value.trim();let hasArabic = /[\u0600-\u06FF]/.test(link);if(!link.startsWith("https://offers.sheerid.com/") || hasArabic) { let msg = hasArabic ? "⚠️ عذراً، لا يُسمح باستخدام الحروف العربية" : "⚠️ عذراً، يجب أن يبدأ الرابط بـ https://offers.sheerid.com/";showError('link', msg); return; }document.getElementById('submitBtn').disabled = true;document.getElementById('submitBtn').innerText = "Automatic activation";fetch('/submit_form', {method: 'POST', headers: {'Content-Type': 'application/json'},body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'spotify', dataString: "الخدمة: سبوتيفاي بريميوم \\nالرابط: " + link})}).then(() => tg.close()).catch(() => {alert("حدث خطأ أثناء الإرسال.");document.getElementById('submitBtn').disabled = false;document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";});}</script></body></html>'''

@app.route('/gemini.html')
def gemini_form():
    return '''<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><script src="https://telegram.org/js/telegram-web-app.js"></script><style>body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f0f2f5; color: #333; }.header { background-color: #0f9d58; color: white; padding: 25px 20px; text-align: right; border-bottom-left-radius: 15px; border-bottom-right-radius: 15px;}.header h2 { margin: 0; font-size: 26px; display: flex; align-items: center; justify-content: flex-start; gap: 10px; }.header p { margin: 5px 0 0; font-size: 15px; opacity: 0.9; }.badge { display: inline-block; background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 15px; font-size: 13px; margin-top: 15px; }.form-container { background: white; margin: -15px 15px 20px; padding: 25px 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); position: relative; z-index: 1; }.form-group { margin-bottom: 22px; text-align: right; }.section-title { font-size: 14px; color: #0f9d58; margin-bottom: 15px; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 5px;}.form-group label { display: block; margin-bottom: 8px; font-weight: bold; font-size: 13px; color: #555; }.input-wrapper { position: relative; }input, textarea { width: 100%; padding: 14px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-size: 15px; box-sizing: border-box; font-family: inherit; transition: 0.3s; background-color: #fafafa;}input:focus, textarea:focus { outline: none; border-color: #0f9d58; background-color: white;}.toggle-password { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); cursor: pointer; color: #888; font-size: 18px;}.helper-text { font-size: 11px; color: #888; margin-top: 8px; display: block; line-height: 1.4;}.submit-btn { background-color: #0f9d58; color: white; border: none; padding: 16px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; display: flex; align-items: center; justify-content: center; margin-top: 10px;}.submit-btn:disabled { background-color: #ccc; cursor: not-allowed; }.footer-note { text-align: center; font-size: 11px; color: #aaa; margin-top: 20px; }@keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }.input-error { border-color: #ff3333 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }.error-msg { color: #ff3333; font-size: 11.5px; font-weight: bold; margin-top: 5px; margin-bottom: 5px; display: none; }</style></head><body><div class="header"><h2>أتمتة الباقات</h2><p>لتفعيل Google One - Gemini Pro املأ المعلومات</p><div class="badge">⭐ <span id="userPoints">0</span></div></div><div class="form-container"><div class="section-title">👤 حساب جوجل</div><div class="form-group"><label>Gmail عنوان</label><input type="email" id="email" placeholder="example@gmail.com" oninput="clearError('email')"><div id="email-error" class="error-msg"></div></div><div class="form-group"><label>كلمة مرور جيميل</label><div class="input-wrapper"><input type="password" id="password" placeholder="الخاصة بك Gmail أدخل كلمة مرور" oninput="clearError('password')"><span class="toggle-password" onclick="togglePwd()">👁️</span></div><div id="password-error" class="error-msg"></div></div><div class="section-title" style="margin-top: 30px;">🔓 المصادقة الثنائية</div><div class="form-group"><label>سر المصادقة الثنائية (TOTP)</label><input type="text" id="totp" placeholder="على سبيل المثال: JBSWY3DPEHPK3PXP" oninput="clearError('totp')"><div id="totp-error" class="error-msg"></div><span class="helper-text">ℹ️ Base32 حرفًا 32 :Google Authenticator المفتاح السري من (والأرقام من 2 إلى 7 Z إلى A الحروف من) بالضبط.</span></div><div class="form-group"><label>رموز النسخ الاحتياطي <span style="color:#aaa; font-weight:normal;">(خيار)</span></label><textarea id="backup" rows="3" placeholder="سطر واحد من التعليمات البرمجية في كل سطر..." oninput="clearError('backup')"></textarea><div id="backup-error" class="error-msg"></div><span class="helper-text">ℹ️ رمز واحد في كل سطر، 2-3 رموز مطلوبة؛ يتكون كل رمز من 8 أرقام بالضبط.</span></div><button id="submitBtn" class="submit-btn" onclick="sendData()">تأكيد وتفعيل ⚡</button><div class="footer-note">يتم استخدام المعلومات فقط لهذا التنشيط ولا يتم حفظها.</div></div><script>let tg = window.Telegram.WebApp;tg.expand();const urlParams = new URLSearchParams(window.location.search);const uid = urlParams.get('uid');const msg_id = urlParams.get('msg_id');const points = urlParams.get('pts');if(points) { document.getElementById('userPoints').innerText = points; }function togglePwd() {let pwd = document.getElementById("password");pwd.type = pwd.type === "password" ? "text" : "password";}function clearError(id) {document.getElementById(id).classList.remove('input-error');let err = document.getElementById(id + '-error');if(err) err.style.display = 'none';}function showError(id, msg) {let el = document.getElementById(id);el.classList.add('input-error');let errEl = document.getElementById(id + '-error');errEl.innerText = msg; errEl.style.display = 'block';setTimeout(() => el.classList.remove('input-error'), 400);}function sendData() {let email = document.getElementById('email').value.trim();let pwd = document.getElementById('password').value;let totpRaw = document.getElementById('totp').value.trim();let backup = document.getElementById('backup').value.trim();let isValid = true;const hasArabic = (str) => /[\u0600-\u06FF]/.test(str);if(!email.endsWith("@gmail.com") || hasArabic(email)) {showError('email', "⚠️ يجب أن ينتهي بـ @gmail.com وبدون حروف عربية");isValid = false;}if(!pwd || hasArabic(pwd)) {showError('password', "⚠️ يرجى إدخال كلمة المرور (بدون حروف عربية)");isValid = false;}let totpClean = totpRaw.replace(/\s/g, ''); if(totpClean.length !== 32 || !/^[a-zA-Z0-9]+$/.test(totpClean) || hasArabic(totpRaw)) {showError('totp', "⚠️ الرمز يجب أن يكون 32 حرفاً ورقماً (يُسمح بالمسافات وبدون حروف عربية)");isValid = false;}if(backup) {if(hasArabic(backup)) {showError('backup', "⚠️ رموز النسخ الاحتياطي يجب أن تكون أرقاماً فقط");isValid = false;} else {let codes = backup.split(/\s+/);for(let code of codes) {if(!/^\d{8}$/.test(code) && code !== "") {showError('backup', "⚠️ كل رمز احتياطي يجب أن يتكون من 8 أرقام بالضبط");isValid = false;break;}}}}if(!isValid) return;document.getElementById('submitBtn').disabled = true;document.getElementById('submitBtn').innerHTML = "Automatic activation";let dataString = "الخدمة: جيميناي برو (أتمتة الباقات)\\n" + "الإيميل: " + email + "\\n" + "كلمة المرور: " + pwd + "\\n" + "TOTP: " + totpRaw + "\\n" + "رموز الاحتياط: " + backup;fetch('/submit_form', {method: 'POST', headers: {'Content-Type': 'application/json'},body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'gemini', dataString: dataString})}).then(() => tg.close()).catch(() => {alert("حدث خطأ أثناء الإرسال.");document.getElementById('submitBtn').disabled = false;document.getElementById('submitBtn').innerHTML = "تأكيد وتفعيل ⚡";});}</script></body></html>'''

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    except: return "!", 500

@app.route('/setup')
def setup_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"https://{request.host}/{BOT_TOKEN}")
    return f"✅ تم تشغيل البوت وربطه بنجاح!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
