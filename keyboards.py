# keyboards.py
from telegram import ReplyKeyboardMarkup

def get_main_keyboard(language='ar'):
    keyboard = [
        ["🇱🇧 حسابي" if language == 'ar' else "🇱🇧 My Account", "🌾 محاصيلي" if language == 'ar' else "🌾 My Crops"],
        ["🧾 سجل الحصاد" if language == 'ar' else "🧾 Record Harvest", "💵 المدفوعات المعلقة" if language == 'ar' else "💵 Pending Payments"],
        ["🗓️ التسميد/علاج" if language == 'ar' else "🗓️ Fertilize & Treat", "💸 مصاريف" if language == 'ar' else "💸 Expenses"],
        ["📈 الأسعار بالسوق" if language == 'ar' else "📈 Market Prices", "📊 ملخص الاسبوع" if language == 'ar' else "📊 Weekly Summary"],
        ["❓مساعدة" if language == 'ar' else "❓Help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
