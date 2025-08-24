# onboarding.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import re
from datetime import datetime, date, timedelta
from core_singleton import get_farm_core   # <-- changed
from keyboards import get_main_keyboard

ONBOARD_STATES = {
    'LANGUAGE': 0,
    'NAME': 1,
    'PHONE': 2,
    'VILLAGE': 3
}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    telegram_id = user.id
    farm_core = get_farm_core()   # get at runtime
    farmer = farm_core.get_farmer(telegram_id)

    if farmer:
        welcome_message = f"مرحبا بعودتك، {farmer['name']}!" if farmer['language'] == 'ar' else f"Welcome back, {farmer['name']}!"
        await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard(farmer['language']))
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "مرحبا! يبدو أن هذه أول مرة تستخدم فيها البوت. دعنا ننشئ حسابك.\n\n"
            "Welcome! It looks like this is your first time using the bot. Let's create your account.",
            reply_markup=ReplyKeyboardMarkup([["عربي", "English"]], resize_keyboard=True)
        )
        return ONBOARD_STATES['LANGUAGE']

# ... similarly inside get_village():
async def get_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['village'] = update.message.text
    telegram_id = update.effective_user.id
    farm_core = get_farm_core()
    farmer = farm_core.create_farmer(
        telegram_id=telegram_id,
        name=context.user_data['name'],
        phone=context.user_data['phone'],
        village=context.user_data['village'],
        language=context.user_data['language']
    )
    # rest unchanged...









'''# onboarding.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import re
from datetime import datetime, date, timedelta
from core_singleton import farm_core
from keyboards import get_main_keyboard

ONBOARD_STATES = {
    'LANGUAGE': 0,
    'NAME': 1,
    'PHONE': 2,
    'VILLAGE': 3
}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    telegram_id = user.id
    farmer = farm_core.get_farmer(telegram_id)

    if farmer:
        welcome_message = f"مرحبا بعودتك، {farmer['name']}!" if farmer['language'] == 'ar' else f"Welcome back, {farmer['name']}!"
        await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard(farmer['language']))
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "مرحبا! يبدو أن هذه أول مرة تستخدم فيها البوت. دعنا ننشئ حسابك.\n\n"
            "Welcome! It looks like this is your first time using the bot. Let's create your account.",
            reply_markup=ReplyKeyboardMarkup([["عربي", "English"]], resize_keyboard=True)
        )
        return ONBOARD_STATES['LANGUAGE']

# Onboarding flow
async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data['language'] = 'ar' if text == "عربي" else 'en'
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو اسمك؟" if lang == 'ar' else "What's your name?",
        reply_markup=ReplyKeyboardRemove()
    )
    return ONBOARD_STATES['NAME']

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو رقم هاتفك؟" if lang == 'ar' else "What's your phone number?"
    )
    return ONBOARD_STATES['PHONE']

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text
    lang = context.user_data['language']
    # Validate phone number
    if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
        await update.message.reply_text(
            "رقم الهاتف غير صالح. حاول مرة أخرى." if lang == 'ar' else "Invalid phone number. Try again."
        )
        return ONBOARD_STATES['PHONE']
    context.user_data['phone'] = phone
    await update.message.reply_text(
        "ما هي قريتك أو منطقتك؟" if lang == 'ar' else "What's your village or area?"
    )
    return ONBOARD_STATES['VILLAGE']

async def get_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['village'] = update.message.text
    telegram_id = update.effective_user.id
    farmer = farm_core.create_farmer(
        telegram_id=telegram_id,
        name=context.user_data['name'],
        phone=context.user_data['phone'],
        village=context.user_data['village'],
        language=context.user_data['language']
    )
    lang = context.user_data['language']
    if farmer:
        await update.message.reply_text(
            f"تم إنشاء حسابك بنجاح! مرحبا {farmer['name']}." if lang == 'ar' else f"Your account has been created! Welcome {farmer['name']}.",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "حدث خطأ أثناء إنشاء الحساب. حاول مرة أخرى." if lang == 'ar' else "Error creating account. Please try again."
        )
    return ConversationHandler.END
'''
