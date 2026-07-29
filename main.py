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

# --- إعداد قناة ومجموعة المتجر ---
CHANNEL_USERNAME = "@SubGateSA"
GROUP_USERNAME = "@SubGateChat"

# --- إعداد قاعدة البيانات MongoDB ---
MONGO_URI = "mongodb+srv://hanytgribi_db_user:KA1999KA@cluster0.kez5fjj.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['MyBotDB']
users_collection = db['users']
settings_collection = db['settings']

def get_settings():
    s = settings_collection.find_one({"_id": "bot_settings"})
    if not s:
        s = {"_id": "bot_settings", "price_yt": 15, "price_spotify": 15, "price_gemini": 15, "referral_bonus": 2}
        settings_collection.insert_one(s)
    return s

admin_states = {}

# --- تتبع الفلود والسبام ---
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
    markup.add(KeyboardButton("📊 إحصائيات المستخدمين"), KeyboardButton("🚫 قائمة المحظورين"))
    markup.add(KeyboardButton("🔍 استعلام عن مستخدم"), KeyboardButton(BTN_MAIN))
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

# وظيفة حذف الرسائل المزدوجة (الطلب والرد)
def delayed_delete(chat_id, user_msg_id, bot_msg_id, delay=2.5):
    time.sleep(delay)
    try: bot.delete_message(chat_id, user_msg_id)
    except: pass
    try: bot.delete_message(chat_id, bot_msg_id)
    except: pass

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

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not user:
        users_collection.insert_one({"user_id": user_id, "first_name": message.from_user.first_name, "points": 0, "invites": 0, "last_collected_date": None, "streak": 0, "is_banned": False, "join_date": now_str, "last_active": datetime.datetime.now(), "warning_count": 0})
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != user_id:
                rb = get_settings().get("referral_bonus", 2)
                users_collection.update_one({"user_id": ref_id}, {"$inc": {"points": rb, "invites": 1}})
                try: bot.send_message(ref_id, f"🎉 ياي! قام صديق بالتسجيل عبر رابطك! تمت إضافة ({rb}) نقطة لرصيدك بنجاح.")
                except: pass
    else:
        users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": datetime.datetime.now()}})

    kb = group_keyboard() if message.chat.type in ['group', 'supergroup'] else main_keyboard()
    bot.send_message(message.chat.id, f"أهلاً بك يا <b>{message.from_user.first_name}</b> في متجرنا الإلكتروني <b>بوابة الاشتراكات</b>! 🤖✨\n\nتفضل باختيار ما تريد من القائمة التفاعلية بالأسفل 👇", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    if check_user_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح! أهلاً بك.")
        try: bot.delete_message(call.from_user.id, call.message.message_id)
        except: pass
        send_welcome(call.message)
    else: bot.answer_callback_query(call.id, "❌ لم تقم بالانضمام للقناة أو المجموعة بعد!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_temp_') or call.data.startswith('ban_perm_'))
def handle_moderation_actions(call):
    if str(call.from_user.id) != str(ADMIN_ID): return bot.answer_callback_query(call.id, "⛔️ للآدمن فقط!", show_alert=True)
    parts = call.data.split('_'); action = parts[0]; target_id = int(parts[2])
    
    if action == 'unban':
        try:
            bot.restrict_chat_member(GROUP_USERNAME, target_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            bot.send_message(target_id, "🌟 <b>تم العفو عنك وإلغاء الإيقاف المؤقت في المجموعة!</b>\n\nنرجو منك الالتزام بقوانين المجموعة وعدم تكرار المخالفة. نورتنا من جديد! 🤝")
            bot.answer_callback_query(call.id, "✅ تم رفع الإيقاف المؤقت بنجاح.")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e: bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)
            
    elif action == 'ban':
        users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": True}})
        try:
            bot.ban_chat_member(GROUP_USERNAME, target_id)
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
            bot.send_message(target_id, f"🚫 <b>عذراً، تم حظر حسابك نهائياً من المتجر والمجموعة.</b>\n\nلقد تم اتخاذ هذا القرار الإداري بسبب مخالفة الشروط والتعليمات.\nللتواصل مع الإدارة لطلب رفع الحظر 👇", reply_markup=markup)
            bot.answer_callback_query(call.id, "✅ تم تأكيد الحظر النهائي للمستخدم في البوت والمجموعة.")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e: bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_button(call):
    if str(call.from_user.id) == str(ADMIN_ID):
        target_id = call.data.split('_')[1]
        admin_states[call.from_user.id] = {'action': 'reply_user', 'target': target_id}
        bot.send_message(ADMIN_ID, f"✍️ <b>وضع الرد مفعل:</b>\nاكتب رسالتك الآن للعميل: <code>{target_id}</code>\n\n(لإلغاء الأمر أرسل /cancel)")
        bot.answer_callback_query(call.id)

# ==========================================
# --- نظام الحماية المتقدم جداً للمجموعات ---
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'], content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation'])
def advanced_group_moderation(message):
    user_id = message.from_user.id
    if str(user_id) == str(ADMIN_ID): return

    # 1. السماح لأزرار البوت بالمرور وتنفيذها فوراً (تجاوز الفلترة)
    if message.content_type == 'text' and message.text in [BTN_DAILY, BTN_ACCOUNT]:
        process_group_buttons(message)
        return

    violation_type = None
    text = message.text or message.caption or ""
    text_lower = text.lower()

    # 2. حماية الوسائط (منع الملصقات، الصور، الفيديو، الخ)
    if message.content_type != 'text':
        violation_type = f"إرسال وسائط ممنوعة ({message.content_type})"

    # 3. حماية الفلود والسبام السريع
    if not violation_type:
        now = time.time()
        if user_id not in user_flood_tracker: user_flood_tracker[user_id] = []
        user_flood_tracker[user_id] = [t for t in user_flood_tracker[user_id] if now - t < 5]
        user_flood_tracker[user_id].append(now)
        if len(user_flood_tracker[user_id]) >= 4:
            violation_type = "إرسال رسائل سريعة (فلود / Flood)"

    # 4. التكرار العشوائي لنفس الرسالة
    if not violation_type and text:
        if user_id in user_last_msg:
            if user_last_msg[user_id]['text'] == text_lower:
                user_last_msg[user_id]['count'] += 1
                if user_last_msg[user_id]['count'] >= 3:
                    violation_type = "تكرار نفس الرسالة (سبام / Spam)"
            else: user_last_msg[user_id] = {'text': text_lower, 'count': 1}
        else: user_last_msg[user_id] = {'text': text_lower, 'count': 1}

    # 5. حماية الروابط
    if not violation_type and re.search(r'(http|https|t\.me|@\w+|\.com|\.net|\.org)', text_lower):
        violation_type = "إرسال روابط أو معرفات خارجية"

    # 6. فلتر الكلمات المسيئة والإباحية (شديد الحساسية ضد التحايل)
    if not violation_type:
        normalized_text = re.sub(r'[\W_0-9]+', '', text_lower)
        bad_roots = ["سكس", "نيك", "قحب", "شرمو", "مخنث", "ديوث", "طيز", "زبي", "كسك", "سنابي", "تعارف", "sex", "porn", "fuck", "nude", "ممحون", "خاص", "شواذ", "كلب", "حيوان", "زبال"]
        if any(bad in normalized_text for bad in bad_roots):
            violation_type = "ألفاظ مسيئة أو غير أخلاقية"

    # 7. فلتر الرسائل العشوائية والعبثية (Gibberish)
    if not violation_type and text:
        no_space = text.replace(" ", "")
        if re.search(r'(.)\1{4,}', no_space):
            violation_type = "رسالة مزعجة (تكرار حروف عبثي)"
        elif any(len(word) > 15 and re.search(r'[\u0600-\u06FF]', word) for word in text.split()):
            violation_type = "رسالة عشوائية (أحرف متلاصقة بلا معنى)"
        elif re.search(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{5,}', text):
            violation_type = "رسالة عشوائية (أحرف مبهمة)"

    # تنفيذ العقوبة إذا تم اكتشاف مخالفة
    if violation_type:
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        
        users_collection.update_one({"user_id": user_id}, {"$inc": {"warning_count": 1}})
        try: bot.restrict_chat_member(message.chat.id, user_id, until_date=int(time.time()) + 7200, can_send_messages=False)
        except: pass

        if ADMIN_ID:
            content_display = text if message.content_type == 'text' else f"[{message.content_type}]"
            admin_alert = (
                f"🚨 <b>اكتشاف مخالفة وتم الكتم!</b>\n\n"
                f"👤 الاسم: {message.from_user.first_name}\n"
                f"🆔 الآيدي: <code>{user_id}</code>\n"
                f"📌 نوع المخالفة: <b>{violation_type}</b>\n"
                f"💬 المحتوى المكتشف:\n<code>{content_display}</code>\n"
                f"⏰ الوقت: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"⚡️ <i>الإجراء: تم الحذف والكتم لمدة ساعتين في المجموعة (دون حظره من البوت).</i>"
            )
            markup = InlineKeyboardMarkup().row(
                InlineKeyboardButton("🔓 رفع الكتم", callback_data=f"unban_temp_{user_id}"),
                InlineKeyboardButton("⛔ حظر نهائي", callback_data=f"ban_perm_{user_id}")
            )
            try: bot.send_message(ADMIN_ID, admin_alert, reply_markup=markup)
            except: pass

# === وظيفة تنفيذ الأزرار داخل المجموعة (مع الحذف المزدوج الدقيق) ===
def process_group_buttons(message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        resp = bot.reply_to(message, "⚠️ الرجاء التسجيل في البوت أولاً عبر الخاص.")
        threading.Thread(target=delayed_delete, args=(message.chat.id, message.message_id, resp.message_id, 2.5)).start()
        return

    if message.text == BTN_DAILY:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        last_date = user.get("last_collected_date")
        streak = user.get("streak", 0)

        if last_date == today_str:
            resp = bot.reply_to(message, "⏳ لقد قمت بجمع هديتك اليوم! ننتظرك غداً بشوق.")
            threading.Thread(target=delayed_delete, args=(message.chat.id, message.message_id, resp.message_id, 2.5)).start()
            return

        streak = streak + 1 if last_date == yesterday_str else 1
        is_seventh_day = (streak % 7 == 0)
        pts_added = 2 if is_seventh_day else 1
        
        new_points = user.get("points", 0) + pts_added
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": pts_added}, "$set": {"last_collected_date": today_str, "streak": streak}})
        
        daily_msg = f"🎉 <b>تسجيل حضور ناجح!</b>\n═══════════════════════\n\n💎 +{pts_added} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n💰 الرصيد: {new_points} {'عملة' if is_seventh_day else 'وحدة نقدية'} |\n📅 سلسلة الأيام: {streak} {'أيام' if is_seventh_day else 'يوم'}\n═══════════════════════"
        if is_seventh_day: daily_msg += "\n\n🔥 <b>سلسلة 7 أيام!</b>\n\nلقد حصلت على 2 عملة بدلاً من 1 عملة!"

        resp = bot.reply_to(message, daily_msg, parse_mode="HTML")
        threading.Thread(target=delayed_delete, args=(message.chat.id, message.message_id, resp.message_id, 2.5)).start()

    elif message.text == BTN_ACCOUNT:
        account_msg = f"👤 <b>الاسم:</b> {user.get('first_name', 'غير معروف')}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {user.get('points', 0)} نقطة\n🤝 <b>المدعوين:</b> {user.get('invites', 0)}"
        resp = bot.reply_to(message, account_msg, parse_mode="HTML")
        threading.Thread(target=delayed_delete, args=(message.chat.id, message.message_id, resp.message_id, 2.5)).start()


# --- معالجة النصوص (العملاء في الخاص والإدارة) ---
@bot.message_handler(func=lambda message: message.chat.type == 'private')
def handle_private_text(message):
    user_id = message.from_user.id
    text = message.text
    is_admin = (str(user_id) == str(ADMIN_ID))

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
                users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": False, "warning_count": 0}})
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
                return
            elif action == 'reply_user':
                target_id = int(state['target'])
                bot.send_message(target_id, text)
                bot.send_message(user_id, "✅ تم إرسال رسالتك للعميل بنجاح.", reply_markup=admin_keyboard())
            elif action == 'broadcast':
                users = users_collection.find({})
                count = 0
                for u in users:
                    try: bot.send_message(u['user_id'], text); count += 1
                    except: pass
                bot.send_message(user_id, f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.", reply_markup=admin_keyboard())
            
            elif action == 'change_price_yt':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_yt": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة يوتيوب إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = f"📢 <b>تحديث مميز في أسعار الخدمات! 📺</b>\n\nتم تعديل سعر اشتراك <b>يوتيوب بريميوم</b> ليصبح فقط <b>{new_price}</b> نقطة!\nسارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except: pass

            elif action == 'change_price_spotify':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_spotify": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة سبوتيفاي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = f"📢 <b>تحديث مميز في أسعار الخدمات! 🎵</b>\n\nتم تعديل سعر اشتراك <b>سبوتيفاي بريميوم</b> ليصبح فقط <b>{new_price}</b> نقطة!\nسارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except: pass

            elif action == 'change_price_gemini':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_gemini": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة جيميناي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = f"📢 <b>تحديث مميز في أسعار الخدمات! ✨</b>\n\nتم تعديل سعر اشتراك <b>جيميناي برو</b> ليصبح فقط <b>{new_price}</b> نقطة!\nسارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except: pass

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
                    u_banned = "نعم 🚫" if target_user.get("is_banned", False) else "لا ✅"
                    bot.send_message(user_id, f"🔍 <b>نتيجة الاستعلام:</b>\n\n👤 <b>الاسم:</b> {u_name}\n🆔 <b>الآيدي:</b> <code>{target_id}</code>\n⭐ <b>الرصيد:</b> {u_pts} نقطة\n🤝 <b>المدعوين:</b> {u_invites} أشخاص\n🔒 <b>محظور؟</b> {u_banned}", reply_markup=admin_keyboard())
                else: bot.send_message(user_id, "❌ لم يتم العثور على هذا المستخدم في قاعدة البيانات.", reply_markup=admin_keyboard())
            elif action == 'broadcast':
                users = users_collection.find({})
                count = 0
                for u in users:
                    try: bot.send_message(u['user_id'], text); count += 1
                    except: pass
                bot.send_message(user_id, f"✅ تمت الإذاعة بنجاح لـ {count} مستخدم.", reply_markup=admin_keyboard())
        except Exception as e:
            bot.send_message(user_id, f"❌ حدث خطأ، يرجى التحقق من المدخلات.\nالخطأ: {e}")
        del admin_states[user_id]
        return

    if is_admin:
        if text == "🚫 حظر مستخدم":
            admin_states[user_id] = {'action': 'ban_user'}; bot.send_message(user_id, "أرسل الآن ID المستخدم ليتم حظره:\n(أرسل /cancel للإلغاء)"); return
        elif text == "✅ فك حظر":
            admin_states[user_id] = {'action': 'unban_user'}; bot.send_message(user_id, "أرسل الآن ID المستخدم لفك حظره:\n(أرسل /cancel للإلغاء)"); return
        elif text == "➕ إضافة نقاط":
            admin_states[user_id] = {'action': 'add_points'}; bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم عدد النقاط.\nمثال: <code>123456789 50</code>", parse_mode="HTML"); return
        elif text == "➖ سحب نقاط":
            admin_states[user_id] = {'action': 'remove_points'}; bot.send_message(user_id, "أرسل ID العميل ثم مسافة ثم النقاط المسحوبة.\nمثال: <code>123456789 15</code>", parse_mode="HTML"); return
        elif text == "📩 رد/رسالة لمستخدم":
            admin_states[user_id] = {'action': 'reply_user_step1'}; bot.send_message(user_id, "أرسل أولاً ID العميل الذي تريد مراسلته:"); return
        elif text == "📢 إذاعة للجميع":
            admin_states[user_id] = {'action': 'broadcast'}; bot.send_message(user_id, "أرسل الإعلان الآن وسيتم توزيعه لجميع المستخدمين:"); return
        elif text == "📺 سعر يوتيوب":
            admin_states[user_id] = {'action': 'change_price_yt'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة يوتيوب (رقم فقط):"); return
        elif text == "🎵 سعر سبوتيفاي":
            admin_states[user_id] = {'action': 'change_price_spotify'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة سبوتيفاي (رقم فقط):"); return
        elif text == "✨ سعر جيميناي":
            admin_states[user_id] = {'action': 'change_price_gemini'}; bot.send_message(user_id, "أرسل السعر الجديد لخدمة جيميناي (رقم فقط):"); return
        elif text == "🎁 تعديل مكافأة الدعوة":
            admin_states[user_id] = {'action': 'change_referral'}; bot.send_message(user_id, "أرسل نقاط المكافأة الجديدة لدعوة الأصدقاء (رقم فقط):"); return
        elif text == "🔍 استعلام عن مستخدم":
            admin_states[user_id] = {'action': 'check_user'}; bot.send_message(user_id, "أرسل ID العميل للاستعلام عن بياناته وحسابه:"); return
        elif text == "📊 إحصائيات المستخدمين":
            all_users = list(users_collection.find({}))
            total = len(all_users)
            now = datetime.datetime.now()
            msg = f"📊 <b>إحصائيات مستخدمي البوت:</b>\n\n👥 <b>العدد الإجمالي:</b> {total} مستخدم\n\n<b>قائمة المشتركين:</b>\n"
            for u in all_users[:30]:
                u_name = u.get('first_name', 'مستخدم')
                u_id = u.get('user_id')
                u_pts = u.get('points', 0)
                u_date = u.get('join_date', 'غير متوفر')
                last_act = u.get('last_active', now)
                
                diff_days = (now - last_act).days if isinstance(last_act, datetime.datetime) else 0
                if diff_days <= 3: status_dot = "🟢"
                elif diff_days <= 7: status_dot = "🟡"
                else: status_dot = "🔴"
                
                msg += f"{status_dot} {u_name} | <code>{u_id}</code> | ({u_pts} نقطة) | 📅 {u_date}\n"
                
            if total > 30: msg += f"\n...وغيرهم {total - 30} مستخدم."
            bot.send_message(user_id, msg, reply_markup=admin_keyboard())
            return
        elif text == "🚫 قائمة المحظورين":
            banned_users = list(users_collection.find({"is_banned": True}))
            total_banned = len(banned_users)
            if total_banned == 0:
                bot.send_message(user_id, "✅ لا يوجد أي مستخدم محظور حالياً.", reply_markup=admin_keyboard())
            else:
                msg = f"🚫 <b>قائمة المحظورين ({total_banned}):</b>\n\n"
                for u in banned_users:
                    msg += f"• {u.get('first_name', 'مستخدم')} | <code>{u.get('user_id')}</code>\n"
                bot.send_message(user_id, msg, reply_markup=admin_keyboard())
            return

    users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": datetime.datetime.now()}})

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
    ref_bonus = bot_settings.get("referral_bonus", 2)

    if text == BTN_DAILY:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
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
        points = user.get("points", 0)
        account_msg = f"👤 <b>الاسم:</b> {user.get('first_name', 'غير معروف')}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {points} نقطة\n🤝 <b>المدعوين:</b> {user.get('invites', 0)}"
        bot.send_message(message.chat.id, account_msg, parse_mode="HTML")

    elif text == BTN_MAIN:
        bot.send_message(user_id, "🏠 مرحباً بك في الرئيسية.", reply_markup=main_keyboard())

    elif text == BTN_INVITE:
        bot.send_message(user_id, f"🎁 <b>دعوة الأصدقاء</b>\n\nشارك الرابط واحصل على ({ref_bonus}) نقطة عن كل تسجيل:\n\nhttps://t.me/{bot.get_me().username}?start={user_id}")

    elif text == BTN_CONTACT:
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    elif text in [BTN_YT, BTN_SPOTIFY, BTN_GEMINI]:
        points = user.get("points", 0)
        price_map = {BTN_YT: bot_settings.get("price_yt", 15), BTN_SPOTIFY: bot_settings.get("price_spotify", 15), BTN_GEMINI: bot_settings.get("price_gemini", 15)}
        service_price = price_map[text]

        if points >= service_price:
            urls = {BTN_YT: "youtube.html", BTN_SPOTIFY: "spotify.html", BTN_GEMINI: "gemini.html"}
            names = {BTN_YT: "📺 يوتيوب بريميوم", BTN_SPOTIFY: "🎵 سبوتيفاي بريميوم", BTN_GEMINI: "✨ جيميناي برو"}
            msg = bot.send_message(user_id, f"{names[text]}\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/{urls[text]}?uid={user_id}&pts={points}&service={urls[text].split('.')[0]}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

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
    service_type = data.get('service', 'yt')
    form_data = data.get('dataString')

    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("is_banned", False): return jsonify({"status": "banned"}), 403

    bot_settings = get_settings()
    price_map = {'youtube': bot_settings.get("price_yt", 15), 'spotify': bot_settings.get("price_spotify", 15), 'gemini': bot_settings.get("price_gemini", 15)}
    service_price = price_map.get(service_type, 15)

    if user and user.get("points", 0) >= service_price:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": -service_price}})
        new_points = user.get("points", 0) - service_price
        if ADMIN_ID:
            admin_msg = f"🔔 <b>طلب جديد استلمناه للتو!</b>\n\n👤 العميل: {user.get('first_name', 'عميل')}\n🆔 رقم العميل: <code>{user_id}</code>\n\n📋 <b>البيانات المرسلة:</b>\n{form_data}"
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✍️ رد على العميل", callback_data=f"reply_{user_id}"))
            try: bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup)
            except: pass
        try: bot.delete_message(user_id, msg_id) 
        except: pass
        bot.send_message(user_id, f"🎉 <b>طلبك قيد التنفيذ، الرجاء الانتظار!</b>\n\n⭐ <b>رصيدك المتبقي:</b> {new_points} نقطة.\n\n<a href='https://t.me/bdallhshay7'>💬 للتواصل والاستفسار اضغط هنا</a>")
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

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
