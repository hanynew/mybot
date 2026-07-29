import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, request, jsonify
from pymongo import MongoClient
import datetime
import threading
import time

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
        s = {
            "_id": "bot_settings", 
            "price_yt": 15, 
            "price_spotify": 15, 
            "price_gemini": 15, 
            "referral_bonus": 2
        }
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
    if str(user_id) == str(ADMIN_ID):
        return True
    try:
        channel_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if channel_member.status in ['left', 'kicked']:
            return False
        group_member = bot.get_chat_member(GROUP_USERNAME, user_id)
        if group_member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        print(f"Error checking sub: {e}")
        return True

def subscription_required_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    markup.add(InlineKeyboardButton("💬 انضم لمجموعة المناقشة", url=f"https://t.me/{GROUP_USERNAME[1:]}"))
    markup.add(InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
    return markup

def delayed_delete(chat_id, message_id, delay=4):
    time.sleep(delay)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        bot.send_message(message.chat.id, "🛠️ <b>مرحباً بك في لوحة تحكم الإدارة:</b>\nاختر الإجراء الذي تريده من الأزرار بالأسفل 👇", reply_markup=admin_keyboard())
    else:
        bot.send_message(message.chat.id, "⛔️ عذراً، لا تملك صلاحية الدخول.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    args = message.text.split()
    
    user = users_collection.find_one({"user_id": user_id})

    if user and user.get("is_banned", False):
        bot.send_message(user_id, "⛔️ <b>عذراً، تم حظر حسابك نهائياً من المتجر. للتواصل مع الإدارة:</b> @bdallhshay7", parse_mode="HTML")
        return

    if not check_user_subscription(user_id):
        bot.send_message(
            user_id, 
            "⚠️ <b>عذراً، يجب عليك الانضمام لقناة ومجموعة المتجر أولاً لتتمكن من استخدام البوت الاستفادة من الخدمات والخصومات!</b>\n\nبعد الانضمام، اضغط على زر <b>(تحقق من الاشتراك ✅)</b> بالأسفل 👇", 
            reply_markup=subscription_required_markup()
        )
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "points": 0,
            "invites": 0,
            "last_collected_date": None,
            "streak": 0,
            "is_banned": False,
            "join_date": now_str,
            "last_active": datetime.datetime.now(),
            "warning_count": 0
        })
        if len(args) > 1 and args[1].isdigit():
            referrer_id = int(args[1])
            if referrer_id != user_id:
                ref_bonus = get_settings().get("referral_bonus", 2)
                users_collection.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"points": ref_bonus, "invites": 1}}
                )
                try: bot.send_message(referrer_id, f"🎉 ياي! قام صديق بالتسجيل عبر رابطك! تمت إضافة ({ref_bonus}) نقطة لرصيدك بنجاح.")
                except: pass
    else:
        users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": datetime.datetime.now()}})

    welcome_text = f"أهلاً بك يا <b>{first_name}</b> في متجرنا الإلكتروني <b>بوابة الاشتراكات</b>! 🤖✨\n\nتفضل باختيار ما تريد من القائمة التفاعلية بالأسفل 👇"
    kb = group_keyboard() if message.chat.type in ['group', 'supergroup'] else main_keyboard()
    bot.send_message(message.chat.id, welcome_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    user_id = call.from_user.id
    if check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح! أهلاً بك.")
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ لم تقم بالانضمام للقناة أو المجموعة بعد!", show_alert=True)

# --- معالجة أزرار الأدمين الخاصة بالمزعجين (رفع الحظر أو تأكيده) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_temp_') or call.data.startswith('ban_perm_'))
def handle_moderation_actions(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔️ للآدمن فقط!", show_alert=True)
        return
    
    parts = call.data.split('_')
    action = parts[0] # unban أو ban
    target_id = int(parts[2])
    
    if action == 'unban':
        # رفع التقييد المؤقت
        try:
            bot.restrict_chat_member(
                GROUP_USERNAME, target_id, 
                can_send_messages=True, 
                can_send_media_messages=True, 
                can_send_other_messages=True, 
                can_add_web_page_previews=True
            )
            bot.send_message(target_id, "🌟 <b>تم العفو عنك وإلغاء الإيقاف المؤقت!</b>\n\nنرجو منك الالتزام بقوانين المجموعة وعدم تكرار المخالفة حتى لا تعرض نفسك للحظر النهائي. نورتنا من جديد! 🤝")
            bot.answer_callback_query(call.id, "✅ تم رفع الإيقاف المؤقت وإرسال رسالة محفزة للعميل.")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ حدث خطأ: {e}", show_alert=True)
            
    elif action == 'ban':
        # تأكيد الحظر النهائي
        users_collection.update_one({"user_id": target_id}, {"$set": {"is_banned": True}})
        try:
            bot.ban_chat_member(GROUP_USERNAME, target_id)
            ban_msg = (
                f"🚫 <b>عذراً، تم حظر حسابك نهائياً من المتجر والمجموعة.</b>\n\n"
                f"لقد تم اتخاذ هذا القرار الإداري بسبب مخالفة الشروط والتعليمات.\n"
                f"إذا كنت ترى أن هناك خطأ أو رغبت في التواصل مع الإدارة لطلب رفع الحظر، يمكنك مراسلتنا عبر الزر أدناه 👇"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
            bot.send_message(target_id, ban_msg, reply_markup=markup)
            
            bot.answer_callback_query(call.id, "✅ تم تأكيد الحظر النهائي وحظر المستخدم بنجاح.")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ حدث خطأ: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_button(call):
    if str(call.from_user.id) == str(ADMIN_ID):
        target_id = call.data.split('_')[1]
        admin_states[call.from_user.id] = {'action': 'reply_user', 'target': target_id}
        bot.send_message(ADMIN_ID, f"✍️ <b>وضع الرد مفعل:</b>\nاكتب رسالتك الآن للعميل: <code>{target_id}</code>\n\n(لإلغاء الأمر أرسل /cancel)")
        bot.answer_callback_query(call.id)

# --- نظام الفلترة والرقابة الذكية في المجموعة ---
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def group_moderation(message):
    user_id = message.from_user.id
    if str(user_id) == str(ADMIN_ID):
        return

    text = message.text or ""
    text_lower = text.lower()
    
    bad_keywords = [
        "http://", "https://", "t.me/", "@", 
        "تعارف", "بنات", "سنابي", "واتساب", "رقمي", "كلمني", 
        "اباحي", "جنس", "مخنث", "نيك", "شرموط", "سكس", "عشق", "غزل", "حبيبي", "تعال خاص"
    ]
    
    is_violation = any(word in text_lower for word in bad_keywords)

    if is_violation:
        try:
            bot.delete_message(message.chat.id, message.message_id)
            
            user = users_collection.find_one({"user_id": user_id})
            warnings = user.get("warning_count", 0) if user else 0
            
            if warnings >= 1:
                users_collection.update_one({"user_id": user_id}, {"$set": {"is_banned": True}})
                bot.ban_chat_member(message.chat.id, user_id)
                bot.send_message(message.chat.id, f"🚫 تم حظر العضو <code>{user_id}</code> نهائياً لتكراره المخالفة.", parse_mode="HTML")
                try:
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
                    bot.send_message(user_id, "⛔️ <b>تم حظر حسابك نهائياً من المتجر والمجموعة بسبب تكرار المخالفات وإرسال محتوى محظور.</b>", reply_markup=markup)
                except: pass
            else:
                users_collection.update_one({"user_id": user_id}, {"$inc": {"warning_count": 1}})
                
                until_date = int(time.time()) + 7200
                bot.restrict_chat_member(message.chat.id, user_id, until_date=until_date, can_send_messages=False)
                
                bot.send_message(message.chat.id, f"⚠️ تنبيه: تم كتم العضو <code>{user_id}</code> لمدة ساعتين بسبب محتوى مخالف.", parse_mode="HTML")
                
                try:
                    bot.send_message(user_id, f"⚠️ <b>تحذير إداري أمني:</b>\nتم إيقافك مؤقتاً في المجموعة لمدة ساعتين بسبب إرسال محتوى مخالف أو روابط.\nإذا كررت المخالفة سيتم حظرك نهائياً من المتجر.")
                except: pass
                
                # إرسال إشعار للأدمن مع زرين لرفع أو تأكيد الحظر
                if ADMIN_ID:
                    admin_alert = (
                        f"🚨 <b>مستخدم مزعج/مخالف جديد!</b>\n\n"
                        f"👤 الاسم: {message.from_user.first_name}\n"
                        f"🆔 الآيدي: <code>{user_id}</code>\n"
                        f"💬 الرسالة المخالفة:\n<code>{text}</code>\n\n"
                        f"⚡️ <i>الإجراء: تم كتمه ساعتين وإرسال تحذير له. ماذا تريد أن تفعل؟</i>"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.row(
                        InlineKeyboardButton("🔓 رفع الإيقاف", callback_data=f"unban_temp_{user_id}"),
                        InlineKeyboardButton("⛔ تأكيد الحظر", callback_data=f"ban_perm_{user_id}")
                    )
                    bot.send_message(ADMIN_ID, admin_alert, reply_markup=markup)
                    
        except Exception as e:
            print(f"Error in group moderation: {e}")

# --- معالجة النصوص (العملاء والإدارة) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    is_admin = (str(user_id) == str(ADMIN_ID))
    is_group = message.chat.type in ['group', 'supergroup']

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
            
            # --- تعديل أسعار الخدمات مع النشر التلقائي في القناة ---
            elif action == 'change_price_yt':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_yt": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة يوتيوب إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = (
                        f"📢 <b>تحديث مميز في أسعار الخدمات! 📺</b>\n\n"
                        f"تم تخفيض/تعديل سعر اشتراك <b>يوتيوب بريميوم</b> ليصبح فقط <b>{new_price}</b> نقطة!\n"
                        f"سارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except Exception as e:
                    print(f"Error publishing to channel: {e}")

            elif action == 'change_price_spotify':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_spotify": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة سبوتيفاي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = (
                        f"📢 <b>تحديث مميز في أسعار الخدمات! 🎵</b>\n\n"
                        f"تم تخفيض/تعديل سعر اشتراك <b>سبوتيفاي بريميوم</b> ليصبح فقط <b>{new_price}</b> نقطة!\n"
                        f"سارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except Exception as e:
                    print(f"Error publishing to channel: {e}")

            elif action == 'change_price_gemini':
                new_price = int(text)
                settings_collection.update_one({"_id": "bot_settings"}, {"$set": {"price_gemini": new_price}})
                bot.send_message(user_id, f"✅ تم تغيير سعر خدمة جيميناي إلى {new_price} نقطة.", reply_markup=admin_keyboard())
                try:
                    channel_msg = (
                        f"📢 <b>تحديث مميز في أسعار الخدمات! ✨</b>\n\n"
                        f"تم تخفيض/تعديل سعر اشتراك <b>جيميناي برو</b> ليصبح فقط <b>{new_price}</b> نقطة!\n"
                        f"سارع بطلب تفعيلك الفوري الآن عبر البوت 👇"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🛍️ اطلب الآن ⚡", url=f"https://t.me/{bot.get_me().username}"))
                    bot.send_message(CHANNEL_USERNAME, channel_msg, reply_markup=markup)
                except Exception as e:
                    print(f"Error publishing to channel: {e}")

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
        except Exception as e:
            bot.send_message(user_id, f"❌ حدث خطأ، يرجى التحقق من المدخلات.\nالخطأ: {e}")
        del admin_states[user_id]
        return

    if is_admin and not is_group:
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
        bot.send_message(
            user_id, 
            "⚠️ <b>عذراً، يجب عليك الانضمام لقناة ومجموعة المتجر أولاً لتتمكن من استخدام البوت!</b>", 
            reply_markup=subscription_required_markup()
        )
        return

    user = users_collection.find_one({"user_id": user_id})
    if not user: return bot.send_message(user_id, "⚠️ الرجاء إرسال أمر /start أولاً لتسجيل حسابك.")
    if user.get("is_banned", False):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 التواصل مع الإدارة", url="https://t.me/bdallhshay7"))
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
            resp = bot.send_message(message.chat.id, "⏳ لقد قمت بجمع هديتك اليوم! ننتظرك غداً بشوق.")
            if is_group:
                try: bot.delete_message(message.chat.id, message.message_id)
                except: pass
                threading.Thread(target=delayed_delete, args=(message.chat.id, resp.message_id)).start()
            return

        streak = streak + 1 if last_date == yesterday_str else 1
        is_seventh_day = (streak % 7 == 0)
        pts_added = 2 if is_seventh_day else 1
        
        new_points = user.get("points", 0) + pts_added
        users_collection.update_one({"user_id": user_id}, {"$inc": {"points": pts_added}, "$set": {"last_collected_date": today_str, "streak": streak}})
        
        if is_seventh_day:
            daily_msg = (
                f"🎉 <b>تسجيل حضور ناجح!</b>\n"
                f"═══════════════════════\n\n"
                f"💎 +2 عملة |\n"
                f"💰 الرصيد: {new_points} عملة |\n"
                f"📅 سلسلة الأيام: {streak} أيام\n"
                f"═══════════════════════\n\n"
                f"🔥 <b>سلسلة 7 أيام!</b>\n\n"
                f"لقد حصلت على 2 عملة بدلاً من 1 عملة!"
            )
        else:
            daily_msg = (
                f"🎉 <b>تسجيل حضور ناجح!</b>\n"
                f"═══════════════════════\n\n"
                f"💎 +1 وحدة نقدية |\n"
                f"💰 الرصيد: {new_points} وحدة نقدية |\n"
                f"📅 عدد الأيام المتتالية: {streak} يوم\n"
                f"═══════════════════════"
            )

        resp = bot.send_message(message.chat.id, daily_msg, parse_mode="HTML")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            # حذف رسالة الطلب ورسالة الرد معاً بعد ثوانٍ في المجموعة
            threading.Thread(target=delayed_delete, args=(message.chat.id, resp.message_id, 4)).start()

    elif text == BTN_ACCOUNT:
        points = user.get("points", 0)
        account_msg = f"👤 <b>الاسم:</b> {user.get('first_name', 'غير معروف')}\n🆔 <b>رقم الحساب:</b> <code>{user_id}</code>\n⭐ <b>الرصيد:</b> {points} نقطة\n🤝 <b>المدعوين:</b> {user.get('invites', 0)}"
        resp = bot.send_message(message.chat.id, account_msg, parse_mode="HTML")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            threading.Thread(target=delayed_delete, args=(message.chat.id, resp.message_id, 4)).start()

    elif text == BTN_MAIN and not is_group:
        bot.send_message(user_id, "🏠 مرحباً بك في الرئيسية.", reply_markup=main_keyboard())

    elif text == BTN_INVITE and not is_group:
        bot.send_message(user_id, f"🎁 <b>دعوة الأصدقاء</b>\n\nشارك الرابط واحصل على ({ref_bonus}) نقطة عن كل تسجيل:\n\nhttps://t.me/{bot.get_me().username}?start={user_id}")

    elif text == BTN_CONTACT and not is_group:
        bot.send_message(user_id, "💬 للتواصل المباشر مع الإدارة:\n\n<a href='https://t.me/bdallhshay7'>اضغط هنا للتواصل مع الدعم</a>", parse_mode="HTML")

    elif text in [BTN_YT, BTN_SPOTIFY, BTN_GEMINI] and not is_group:
        points = user.get("points", 0)
        price_map = {
            BTN_YT: bot_settings.get("price_yt", 15),
            BTN_SPOTIFY: bot_settings.get("price_spotify", 15),
            BTN_GEMINI: bot_settings.get("price_gemini", 15)
        }
        service_price = price_map[text]

        if points >= service_price:
            urls = {BTN_YT: "youtube.html", BTN_SPOTIFY: "spotify.html", BTN_GEMINI: "gemini.html"}
            names = {BTN_YT: "📺 يوتيوب بريميوم", BTN_SPOTIFY: "🎵 سبوتيفاي بريميوم", BTN_GEMINI: "✨ جيميناي برو"}
            msg = bot.send_message(user_id, f"{names[text]}\n\n💎 <b>التكلفة:</b> {service_price} نقطة.")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📝 فتح النموذج للطلب", web_app=WebAppInfo(url=f"https://mybot-1-d6wr.onrender.com/{urls[text]}?uid={user_id}&pts={points}&service={urls[text].split('.')[0]}&msg_id={msg.message_id}")))
            bot.edit_message_reply_markup(user_id, msg.message_id, reply_markup=markup)
        else:
            bot.send_message(user_id, f"😔 <b>عذراً، رصيدك غير كافٍ.</b>\nرصيدك: {points} نقطة.\nالمطلوب: {service_price} نقطة.")

    elif text in [BTN_HELP, BTN_GUIDE, BTN_DEPOSIT] and not is_group:
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
    price_map = {
        'youtube': bot_settings.get("price_yt", 15),
        'spotify': bot_settings.get("price_spotify", 15),
        'gemini': bot_settings.get("price_gemini", 15)
    }
    service_price = price_map.get(service_type, 15)

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
            input { width: 100%; padding: 15px; margin-bottom: 10px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }
            input:focus { border-color: #FF0000; outline: none; }
            button { background-color: #FF0000; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(255,0,0,0.2); margin-top: 10px; }
            button:disabled { background-color: #ccc; cursor: not-allowed; }
            @keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }
            .input-error { border-color: #FF0000 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }
            .error-msg { color: #FF0000; font-size: 12px; font-weight: bold; margin-bottom: 15px; display: none; text-align: right; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>يوتيوب بريميوم 📺</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://offers.sheerid.com/..." oninput="clearError('link')">
            <div id="link-error" class="error-msg"></div>
            <button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            const urlParams = new URLSearchParams(window.location.search);
            const uid = urlParams.get('uid'); 
            const msg_id = urlParams.get('msg_id');

            function clearError(id) {
                document.getElementById(id).classList.remove('input-error');
                document.getElementById(id + '-error').style.display = 'none';
            }
            function showError(id, msg) {
                let el = document.getElementById(id);
                el.classList.add('input-error');
                let errEl = document.getElementById(id + '-error');
                errEl.innerText = msg; errEl.style.display = 'block';
                setTimeout(() => el.classList.remove('input-error'), 400);
            }

            function sendData() {
                let link = document.getElementById('link').value.trim();
                let hasArabic = /[\u0600-\u06FF]/.test(link);
                
                if(!link.startsWith("https://offers.sheerid.com/") || hasArabic) { 
                    let msg = hasArabic ? "⚠️ عذراً، لا يُسمح باستخدام الحروف العربية" : "⚠️ عذراً، يجب أن يبدأ الرابط بـ https://offers.sheerid.com/";
                    showError('link', msg); return; 
                }
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerText = "جاري الإرسال...";
                fetch('/submit_form', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'youtube', dataString: "الخدمة: يوتيوب بريميوم \\nالرابط: " + link})
                }).then(() => tg.close()).catch(() => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";
                });
            }
        </script>
    </body>
    </html>
    '''

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
            input { width: 100%; padding: 15px; margin-bottom: 10px; border: 1.5px solid #eee; border-radius: 10px; font-size: 16px; box-sizing: border-box; transition: 0.3s; text-align: left; direction: ltr; }
            input:focus { border-color: #1DB954; outline: none; }
            button { background-color: #1DB954; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; font-weight: bold; width: 100%; cursor: pointer; box-shadow: 0 4px 6px rgba(29,185,84,0.2); margin-top: 10px;}
            button:disabled { background-color: #ccc; cursor: not-allowed; }
            @keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }
            .input-error { border-color: #FF0000 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }
            .error-msg { color: #FF0000; font-size: 12px; font-weight: bold; margin-bottom: 15px; display: none; text-align: right; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>سبوتيفاي بريميوم 🎵</h2>
            <p>يرجى لصق رابط التحقق والدفع الخاص بك في الأسفل:</p>
            <input type="url" id="link" placeholder="https://offers.sheerid.com/..." oninput="clearError('link')">
            <div id="link-error" class="error-msg"></div>
            <button id="submitBtn" onclick="sendData()">تأكيد وطلب التفعيل</button>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            const urlParams = new URLSearchParams(window.location.search);
            const uid = urlParams.get('uid'); const msg_id = urlParams.get('msg_id');
            
            function clearError(id) {
                document.getElementById(id).classList.remove('input-error');
                document.getElementById(id + '-error').style.display = 'none';
            }
            function showError(id, msg) {
                let el = document.getElementById(id);
                el.classList.add('input-error');
                let errEl = document.getElementById(id + '-error');
                errEl.innerText = msg; errEl.style.display = 'block';
                setTimeout(() => el.classList.remove('input-error'), 400);
            }

            function sendData() {
                let link = document.getElementById('link').value.trim();
                let hasArabic = /[\u0600-\u06FF]/.test(link);
                
                if(!link.startsWith("https://offers.sheerid.com/") || hasArabic) { 
                    let msg = hasArabic ? "⚠️ عذراً، لا يُسمح باستخدام الحروف العربية" : "⚠️ عذراً، يجب أن يبدأ الرابط بـ https://offers.sheerid.com/";
                    showError('link', msg); return; 
                }
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerText = "جاري الإرسال...";
                fetch('/submit_form', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'spotify', dataString: "الخدمة: سبوتيفاي بريميوم \\nالرابط: " + link})
                }).then(() => tg.close()).catch(() => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerText = "تأكيد وطلب التفعيل";
                });
            }
        </script>
    </body>
    </html>
    '''

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
            .submit-btn { background-color: #0f9d58; color: white; border: none; padding: 16px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; display: flex; align-items: center; justify-content: center; margin-top: 10px;}
            .submit-btn:disabled { background-color: #ccc; cursor: not-allowed; }
            .footer-note { text-align: center; font-size: 11px; color: #aaa; margin-top: 20px; }
            @keyframes shake { 0%, 100% {transform: translateX(0);} 25% {transform: translateX(-5px);} 50% {transform: translateX(5px);} 75% {transform: translateX(-5px);} }
            .input-error { border-color: #ff3333 !important; background-color: #ffe6e6 !important; animation: shake 0.4s; }
            .error-msg { color: #ff3333; font-size: 11.5px; font-weight: bold; margin-top: 5px; margin-bottom: 5px; display: none; }
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
                <input type="email" id="email" placeholder="example@gmail.com" oninput="clearError('email')">
                <div id="email-error" class="error-msg"></div>
            </div>
            
            <div class="form-group">
                <label>كلمة مرور جيميل</label>
                <div class="input-wrapper">
                    <input type="password" id="password" placeholder="الخاصة بك Gmail أدخل كلمة مرور" oninput="clearError('password')">
                    <span class="toggle-password" onclick="togglePwd()">👁️</span>
                </div>
                <div id="password-error" class="error-msg"></div>
            </div>
            
            <div class="section-title" style="margin-top: 30px;">🔓 المصادقة الثنائية</div>
            
            <div class="form-group">
                <label>سر المصادقة الثنائية (TOTP)</label>
                <input type="text" id="totp" placeholder="على سبيل المثال: JBSWY3DPEHPK3PXP" oninput="clearError('totp')">
                <div id="totp-error" class="error-msg"></div>
                <span class="helper-text">ℹ️ Base32 حرفًا 32 :Google Authenticator المفتاح السري من (والأرقام من 2 إلى 7 Z إلى A الحروف من) بالضبط.</span>
            </div>
            
            <div class="form-group">
                <label>رموز النسخ الاحتياطي <span style="color:#aaa; font-weight:normal;">(خيار)</span></label>
                <textarea id="backup" rows="3" placeholder="سطر واحد من التعليمات البرمجية في كل سطر..." oninput="clearError('backup')"></textarea>
                <div id="backup-error" class="error-msg"></div>
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
            if(points) { document.getElementById('userPoints').innerText = points; }
            
            function togglePwd() {
                let pwd = document.getElementById("password");
                pwd.type = pwd.type === "password" ? "text" : "password";
            }
            
            function clearError(id) {
                document.getElementById(id).classList.remove('input-error');
                let err = document.getElementById(id + '-error');
                if(err) err.style.display = 'none';
            }

            function showError(id, msg) {
                let el = document.getElementById(id);
                el.classList.add('input-error');
                let errEl = document.getElementById(id + '-error');
                errEl.innerText = msg; errEl.style.display = 'block';
                setTimeout(() => el.classList.remove('input-error'), 400);
            }
            
            function sendData() {
                let email = document.getElementById('email').value.trim();
                let pwd = document.getElementById('password').value;
                let totpRaw = document.getElementById('totp').value.trim();
                let backup = document.getElementById('backup').value.trim();
                
                let isValid = true;
                const hasArabic = (str) => /[\u0600-\u06FF]/.test(str);
                
                if(!email.endsWith("@gmail.com") || hasArabic(email)) {
                    showError('email', "⚠️ يجب أن ينتهي بـ @gmail.com وبدون حروف عربية");
                    isValid = false;
                }
                
                if(!pwd || hasArabic(pwd)) {
                    showError('password', "⚠️ يرجى إدخال كلمة المرور (بدون حروف عربية)");
                    isValid = false;
                }
                
                let totpClean = totpRaw.replace(/\s/g, ''); 
                if(totpClean.length !== 32 || !/^[a-zA-Z0-9]+$/.test(totpClean) || hasArabic(totpRaw)) {
                    showError('totp', "⚠️ الرمز يجب أن يكون 32 حرفاً ورقماً (يُسمح بالمسافات وبدون حروف عربية)");
                    isValid = false;
                }
                
                if(backup) {
                    if(hasArabic(backup)) {
                        showError('backup', "⚠️ رموز النسخ الاحتياطي يجب أن تكون أرقاماً فقط");
                        isValid = false;
                    } else {
                        let codes = backup.split(/\s+/);
                        for(let code of codes) {
                            if(!/^\d{8}$/.test(code) && code !== "") {
                                showError('backup', "⚠️ كل رمز احتياطي يجب أن يتكون من 8 أرقام بالضبط");
                                isValid = false;
                                break;
                            }
                        }
                    }
                }
                
                if(!isValid) return;
                
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').innerHTML = "جاري الإرسال... ⏳";

                let dataString = "الخدمة: جيميناي برو (أتمتة الباقات)\\n" + 
                                 "الإيميل: " + email + "\\n" +
                                 "كلمة المرور: " + pwd + "\\n" +
                                 "TOTP: " + totpRaw + "\\n" +
                                 "رموز الاحتياط: " + backup;
                
                fetch('/submit_form', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, msg_id: msg_id, service: 'gemini', dataString: dataString})
                }).then(() => tg.close()).catch(() => {
                    alert("حدث خطأ أثناء الإرسال.");
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').innerHTML = "تأكيد وتفعيل ⚡";
                });
            }
        </script>
    </body>
    </html>
    '''

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
