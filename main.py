# main.py
import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)

from core_singleton import farm_core
from keyboards import get_main_keyboard
from onboarding import start, language_selection, get_name, get_phone, get_village, ONBOARD_STATES

# Import everything crop/harvest/edit related from aboutcrop
from aboutcrop import (
    add_crop_start_callback,
    add_crop_name_handler,
    add_crop_date_handler,
    add_crop_notes_handler,
    addcrop_skip_notes_callback,
    CROP_STATES,
    my_crops,
    crops_callback_handler,
    crop_manage_callback,
    crop_delete_callback,
    confirm_delete_callback,
    crop_edit_entry_callback,
    edit_field_choice_callback,
    edit_name_handler,
    edit_date_handler,
    edit_notes_handler,
    EDIT_STATES,
    record_harvest,
    harvest_select_callback,
    harvest_date_callback,
    harvest_date,
    harvest_quantity,
    harvest_delivery_callback,
    harvest_delivery_collector,
    harvest_delivery_market,
    harvest_skip_callback,
    HARVEST_STATES,
)

# aboutmoney
from aboutmoney import (
    add_expense,
    expense_crop,
    expense_category,
    expense_amount,
    expense_date,
    pending_payments,
    mark_paid_callback,
    payment_amount,
    create_pending_callback,
    EXPENSE_STATES,
    PAYMENT_STATES,
)

# abouttreatment (new inline-first treatment flow)
from abouttreatment import (
    add_treatment,
    treatment_crop,
    treatment_product,
    treatment_date,
    treatment_date_callback,
    treatment_cost,
    treatment_next_date,
    treatment_skip_callback,
    TREATMENT_STATES,
)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Cancel command
async def cancel(update: Update, context) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    # when cancelling, show main keyboard
    if update.message:
        await update.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    elif update.callback_query:
        await update.callback_query.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    return ConversationHandler.END

# Help command
async def help_command(update: Update, context) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    help_text = (
        "❓ مساعدة:\n\n"
        "• 🇱🇧 حسابي: عرض معلومات الحساب\n"
        "• 🌾 محاصيلي: عرض جميع المحاصيل\n"
        "• 🧾 سجل الحصاد: تسجيل حصاد جديد\n"
        "• 💵 المدفوعات المعلقة: عرض المدفوعات المتوقعة\n"
        "• 🗓️ التسميد/علاج: إضافة علاج أو تسميد\n"
        "• 💸 مصاريف: تسجيل المصاريف\n"
        "• 📈 الأسعار بالسوق: عرض أسعار السوق\n"
        "• 📊 ملخص الاسبوع: عرض ملخص الأسبوع\n"
    ) if lang == 'ar' else (
        "❓ Help:\n\n"
        "• 🇱🇧 My Account: View account information\n"
        "• 🌾 My Crops: View all crops\n"
        "• 🧾 Record Harvest: Record a new harvest\n"
        "• 💵 Pending Payments: View expected payments\n"
        "• 🗓️ Fertilize & Treat: Add treatment or fertilization\n"
        "• 💸 Expenses: Record expenses\n"
        "• 📈 Market Prices: View market prices\n"
        "• 📊 Weekly Summary: View weekly summary\n"
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

# My account
async def my_account(update: Update, context) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

# Handle main menu selections (text from main ReplyKeyboard)
async def handle_message(update: Update, context) -> None:
    text = update.message.text or ""
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    if text in ["🇱🇧 حسابي", "🇱🇧 My Account"]:
        await my_account(update, context)
    elif text in ["🌾 محاصيلي", "🌾 My Crops"]:
        await my_crops(update, context)
    elif text in ["📈 الأسعار بالسوق", "📈 Market Prices"]:
        from aboutmoney import market_prices
        await market_prices(update, context)
    elif text in ["📊 ملخص الاسبوع", "📊 Weekly Summary"]:
        from aboutmoney import weekly_summary
        await weekly_summary(update, context)
    elif text in ["❓مساعدة", "❓Help"]:
        await help_command(update, context)
    elif text in ["💸 مصاريف", "💸 Expenses"]:
        # start expense flow
        await add_expense(update, context)
    elif text in ["💵 المدفوعات المعلقة", "💵 Pending Payments"]:
        await pending_payments(update, context)
    elif text in ["🗓️ التسميد/علاج", "🗓️ Fertilize & Treat"]:
        # start treatment flow
        await add_treatment(update, context)
    else:
        # fallback
        await update.message.reply_text("أمر غير معروف. استخدم /help" if lang == 'ar' else "Unknown command. Use /help", reply_markup=get_main_keyboard(lang))

def main() -> None:
    application = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    # Registration conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ONBOARD_STATES['LANGUAGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_selection)],
            ONBOARD_STATES['NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ONBOARD_STATES['PHONE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ONBOARD_STATES['VILLAGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add crop conversation handler — entry point is the inline "Add Crop" button (callback)
    add_crop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_crop_start_callback, pattern=r"^crop_add$")],
        states={
            CROP_STATES['CROP_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_name_handler)],
            CROP_STATES['CROP_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_date_handler)],
            CROP_STATES['CROP_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Harvest conversation handler (inline-first)
    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|🧾 Record Harvest)$"), record_harvest)],
        states={
            HARVEST_STATES['HARVEST_CROP']: [
                CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, None)
            ],
            HARVEST_STATES['HARVEST_DATE']: [
                CallbackQueryHandler(harvest_date_callback, pattern=r"^harvest_date:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_date)
            ],
            HARVEST_STATES['HARVEST_QUANTITY']: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quantity)
            ],
            HARVEST_STATES['HARVEST_DELIVERY']: [
                CallbackQueryHandler(harvest_delivery_callback, pattern=r"^harvest_delivery:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, None)
            ],
            HARVEST_STATES['DELIVERY_COLLECTOR']: [
                CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:collector$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery_collector)
            ],
            HARVEST_STATES['DELIVERY_MARKET']: [
                CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:market$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery_market)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Edit conversation: started by callback crop_edit:<id>
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:")],
        states={
            EDIT_STATES['CHOOSE_FIELD']: [CallbackQueryHandler(edit_field_choice_callback, pattern=r"^edit_field:")],
            EDIT_STATES['EDIT_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_name_handler)],
            EDIT_STATES['EDIT_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date_handler)],
            EDIT_STATES['EDIT_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Expense conversation (entry via menu text or button)
    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|💸 Expenses)$"), add_expense)],
        states={
            EXPENSE_STATES['EXPENSE_CROP']: [CallbackQueryHandler(expense_crop, pattern=r"^expense_crop:"), MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)],
            EXPENSE_STATES['EXPENSE_CATEGORY']: [CallbackQueryHandler(expense_category, pattern=r"^expense_cat:"), MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)],
            EXPENSE_STATES['EXPENSE_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_STATES['EXPENSE_DATE']: [CallbackQueryHandler(expense_date, pattern=r"^expense_date:"), MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Payment marking conversation (started via inline "Mark Paid" button)
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_")],
        states={
            PAYMENT_STATES['PAYMENT_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Treatment conversation (inline-first)
    treatment_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🗓️ التسميد/علاج|🗓️ Fertilize & Treat)$"), add_treatment)],
        states={
            TREATMENT_STATES['TREATMENT_CROP']: [
                CallbackQueryHandler(treatment_crop, pattern=r"^treatment_crop:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_crop)
            ],
            TREATMENT_STATES['TREATMENT_PRODUCT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_product)],
            TREATMENT_STATES['TREATMENT_DATE']: [
                CallbackQueryHandler(treatment_date_callback, pattern=r"^treatment_date:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_date)
            ],
            TREATMENT_STATES['TREATMENT_COST']: [
                CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:cost$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_cost)
            ],
            TREATMENT_STATES['TREATMENT_NEXT_DATE']: [
                CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:next$"),
                CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_next:pick$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_next_date)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Register handlers
    application.add_handler(reg_conv_handler)
    application.add_handler(add_crop_conv)
    application.add_handler(harvest_conv_handler)
    application.add_handler(edit_conv)
    application.add_handler(expense_conv)
    application.add_handler(payment_conv)
    application.add_handler(treatment_conv)

    # Generic handlers and callback handlers (from aboutcrop)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # main menu text handler
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^crop_page:"))  # pagination/navigation
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^prefcrop:"))
    application.add_handler(CallbackQueryHandler(crop_manage_callback, pattern=r"^crop_manage:"))
    application.add_handler(CallbackQueryHandler(crop_delete_callback, pattern=r"^crop_delete:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete:"))
    application.add_handler(CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    # aboutcrop inline-only callbacks
    application.add_handler(CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"))
    application.add_handler(CallbackQueryHandler(harvest_date_callback, pattern=r"^harvest_date:"))
    application.add_handler(CallbackQueryHandler(harvest_delivery_callback, pattern=r"^harvest_delivery:"))
    application.add_handler(CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:"))
    application.add_handler(CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$"))

    # aboutmoney callbacks
    application.add_handler(CallbackQueryHandler(create_pending_callback, pattern=r"^create_pending:"))
    application.add_handler(CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_"))

    # abouttreatment inline callbacks used outside conv routing
    application.add_handler(CallbackQueryHandler(treatment_date_callback, pattern=r"^treatment_date:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_next:"))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()












'''import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)

from core_singleton import farm_core
from keyboards import get_main_keyboard
from onboarding import start, language_selection, get_name, get_phone, get_village, ONBOARD_STATES

# from aboutcrop we import the new names / handlers
from aboutcrop import (
    # my crops + management
    my_crops,
    crops_callback_handler,
    crop_manage_callback,
    crop_delete_callback,
    confirm_delete_callback,
    # edit flow
    crop_edit_entry_callback,
    edit_field_choice_callback,
    edit_name_handler,
    edit_date_handler,
    edit_notes_handler,
    EDIT_STATES,
    # add-crop conversation (started from inline "Add Crop")
    add_crop_start_callback,
    add_crop_name_handler,
    add_crop_date_handler,
    add_crop_notes_handler,
    CROP_STATES,
    # harvest
    record_harvest,
    harvest_crop,
    harvest_date,
    harvest_quantity,
    harvest_delivery,
    harvest_delivery_collector,
    harvest_delivery_market,
    HARVEST_STATES,
)

from aboutmoney import (
    add_expense,
    expense_crop,
    expense_category,
    expense_amount,
    expense_date,
    pending_payments,
    mark_paid_callback,
    payment_amount,
    record_delivery,
    delivery_select_harvest,
    stored_delivery_collector,
    stored_delivery_market,
    market_prices,
    weekly_summary,
    EXPENSE_STATES,
    PAYMENT_STATES,
    DELIVERY_STATES,
)
from abouttreatment import (
    add_treatment,
    treatment_crop,
    treatment_product,
    treatment_date,
    treatment_cost,
    treatment_next_date,
    TREATMENT_STATES,
)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Cancel command
async def cancel(update: Update, context) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    await update.message.reply_text(
        "تم الإلغاء." if lang == 'ar' else "Cancelled.",
        reply_markup=get_main_keyboard(lang)
    )
    return ConversationHandler.END

# Help command
async def help_command(update: Update, context) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    help_text = (
        "❓ مساعدة:\n\n"
        "• 🇱🇧 حسابي: عرض معلومات الحساب\n"
        "• 🌾 محاصيلي: عرض جميع المحاصيل\n"
        "• 🧾 سجل الحصاد: تسجيل حصاد جديد\n"
        "• 🚚 سجل التسليم: تسليم المحصول إلى الجامع\n"
        "• 💵 المدفوعات المعلقة: عرض المدفوعات المتوقعة\n"
        "• 🗓️ التسميد/علاج: إضافة علاج أو تسميد\n"
        "• 💸 مصاريف: تسجيل المصاريف\n"
        "• 📈 الأسعار بالسوق: عرض أسعار السوق\n"
        "• 📊 ملخص الاسبوع: عرض ملخص الأسبوع\n"
    ) if lang == 'ar' else (
        "❓ Help:\n\n"
        "• 🇱🇧 My Account: View account information\n"
        "• 🌾 My Crops: View all crops\n"
        "• 🧾 Record Harvest: Record a new harvest\n"
        "• 🚚 Record Delivery: Deliver to collector\n"
        "• 💵 Pending Payments: View expected payments\n"
        "• 🗓️ Fertilize & Treat: Add treatment or fertilization\n"
        "• 💸 Expenses: Record expenses\n"
        "• 📈 Market Prices: View market prices\n"
        "• 📊 Weekly Summary: View weekly summary\n"
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

# My account
async def my_account(update: Update, context) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

# Handle main menu selections
async def handle_message(update: Update, context) -> None:
    text = update.message.text or ""
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    if text in ["🇱🇧 حسابي", "🇱🇧 My Account"]:
        await my_account(update, context)
    elif text in ["🌾 محاصيلي", "🌾 My Crops"]:
        await my_crops(update, context)
    elif text in ["📈 الأسعار بالسوق", "📈 Market Prices"]:
        await market_prices(update, context)
    elif text in ["📊 ملخص الاسبوع", "📊 Weekly Summary"]:
        await weekly_summary(update, context)
    elif text in ["❓مساعدة", "❓Help"]:
        await help_command(update, context)

def main() -> None:
    application = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    # Registration conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ONBOARD_STATES['LANGUAGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_selection)],
            ONBOARD_STATES['NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ONBOARD_STATES['PHONE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ONBOARD_STATES['VILLAGE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add crop conversation handler — entry point is the inline "Add Crop" button (callback)
    add_crop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_crop_start_callback, pattern=r"^crop_add$")],
        states={
            CROP_STATES['CROP_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_name_handler)],
            CROP_STATES['CROP_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_date_handler)],
            CROP_STATES['CROP_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Record harvest conversation handler
    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|🧾 Record Harvest)$"), record_harvest)],
        states={
            HARVEST_STATES['HARVEST_CROP']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_crop)],
            HARVEST_STATES['HARVEST_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_date)],
            HARVEST_STATES['HARVEST_QUANTITY']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quantity)],
            HARVEST_STATES['HARVEST_DELIVERY']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery)],
            HARVEST_STATES['DELIVERY_COLLECTOR']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery_collector)],
            HARVEST_STATES['DELIVERY_MARKET']: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery_market)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Edit conversation: started by callback crop_edit:<id>
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:")],
        states={
            EDIT_STATES['CHOOSE_FIELD']: [CallbackQueryHandler(edit_field_choice_callback, pattern=r"^edit_field:")],
            EDIT_STATES['EDIT_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_name_handler)],
            EDIT_STATES['EDIT_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date_handler)],
            EDIT_STATES['EDIT_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Register handlers
    application.add_handler(reg_conv_handler)
    application.add_handler(add_crop_conv)          # add crop started from inline "Add Crop"
    application.add_handler(harvest_conv_handler)
    application.add_handler(edit_conv)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^crop_page:"))  # pagination/navigation
    application.add_handler(CallbackQueryHandler(crop_manage_callback, pattern=r"^crop_manage:"))
    application.add_handler(CallbackQueryHandler(crop_delete_callback, pattern=r"^crop_delete:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete:"))
    application.add_handler(CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:"))
    application.add_handler(CallbackQueryHandler(mark_paid_callback))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
'''























'''
import os
import logging
from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from farmcore import FarmCore

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FarmCore
farm_core = FarmCore()

# Define conversation states
LANGUAGE, NAME, PHONE, VILLAGE = range(4)
CROP_NAME, CROP_PLANTING_DATE = range(2)
HARVEST_CROP, HARVEST_DATE, HARVEST_QUANTITY, HARVEST_DELIVERY, DELIVERY_COLLECTOR, DELIVERY_MARKET = range(6)
TREATMENT_CROP, TREATMENT_PRODUCT, TREATMENT_DATE, TREATMENT_COST, TREATMENT_NEXT_DATE = range(5)
EXPENSE_CROP, EXPENSE_CATEGORY, EXPENSE_AMOUNT, EXPENSE_DATE = range(4)
PAYMENT_AMOUNT = range(1)

# Main keyboard
def get_main_keyboard(language='ar'):
    keyboard = [
        ["🇱🇧 حسابي" if language == 'ar' else "🇱🇧 My Account", "➕ أضف محصول" if language == 'ar' else "➕ Add Crop"],
        ["🌾 محاصيلي" if language == 'ar' else "🌾 My Crops", "🧾 سجل الحصاد" if language == 'ar' else "🧾 Record Harvest"],
        ["🚚 سجل التسليم" if language == 'ar' else "🚚 Record Delivery", "💵 المدفوعات المعلقة" if language == 'ar' else "💵 Pending Payments"],
        ["🗓️ التسميد/علاج" if language == 'ar' else "🗓️ Fertilize & Treat", "💸 مصاريف" if language == 'ar' else "💸 Expenses"],
        ["📈 الأسعار بالسوق" if language == 'ar' else "📈 Market Prices", "📊 ملخص الاسبوع" if language == 'ar' else "📊 Weekly Summary"],
        ["❓مساعدة" if language == 'ar' else "❓Help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

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
        return LANGUAGE

# Onboarding flow
async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data['language'] = 'ar' if text == "عربي" else 'en'
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو اسمك؟" if lang == 'ar' else "What's your name?",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو رقم هاتفك؟" if lang == 'ar' else "What's your phone number?"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['phone'] = update.message.text
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هي قريتك أو منطقتك؟" if lang == 'ar' else "What's your village or area?"
    )
    return VILLAGE

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

# Add crop flow
async def add_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [["تفاح" if lang == 'ar' else "Apple", "زيتون" if lang == 'ar' else "Olive"],
                ["طماطم" if lang == 'ar' else "Tomato", "خيار" if lang == 'ar' else "Cucumber"],
                ["بطاطس" if lang == 'ar' else "Potato"]]
    await update.message.reply_text(
        "ما هو اسم المحصول؟" if lang == 'ar' else "What's the crop name?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CROP_NAME

async def crop_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['crop_name'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    keyboard = [["اليوم" if lang == 'ar' else "Today", "أمس" if lang == 'ar' else "Yesterday"],
                ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم زراعة المحصول؟" if lang == 'ar' else "When was the crop planted?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CROP_PLANTING_DATE

async def crop_planting_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']

    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return CROP_PLANTING_DATE

    try:
        planting_date = date.today() if text in ["اليوم", "Today"] else \
                        date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"] else \
                        datetime.strptime(text, "%Y-%m-%d").date()
        crop = farm_core.add_crop(
            farmer_id=farmer['id'],  # Use UUID farmer_id
            name=context.user_data['crop_name'],
            planting_date=planting_date
        )
        if crop:
            await update.message.reply_text(
                f"تم إضافة المحصول {crop['name']} بنجاح! ✅" if lang == 'ar' else f"Crop {crop['name']} added successfully! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang == 'ar' else "Error adding crop. Please try again."
            )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD"
        )
        return CROP_PLANTING_DATE

# Record harvest flow
async def record_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else "No crops found. Add a crop first."
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول:" if lang == 'ar' else "Choose crop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_CROP

async def harvest_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود." if lang == 'ar' else "Crop not found."
        )
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    keyboard = [["اليوم" if lang == 'ar' else "Today", "أمس" if lang == 'ar' else "Yesterday"],
                ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم الحصاد؟" if lang == 'ar' else "When was the harvest?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_DATE

async def harvest_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return HARVEST_DATE
    try:
        harvest_date = date.today() if text in ["اليوم", "Today"] else \
                       date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"] else \
                       datetime.strptime(text, "%Y-%m-%d").date()
        context.user_data['harvest_date'] = harvest_date
        await update.message.reply_text(
            "كم الكمية (كجم)؟" if lang == 'ar' else "Enter quantity (kg):"
        )
        return HARVEST_QUANTITY
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return HARVEST_DATE

async def harvest_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        quantity = float(update.message.text)
        context.user_data['harvest_quantity'] = quantity
        keyboard = [["نعم - تم التسليم" if lang == 'ar' else "Yes - Delivered", "لا - مخزون" if lang == 'ar' else "No - Stored"]]
        await update.message.reply_text(
            "هل تم تسليمه إلى الجامع؟" if lang == 'ar' else "Was it handed to the collector?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HARVEST_DELIVERY
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return HARVEST_QUANTITY

async def harvest_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    status = "delivered" if text in ["نعم - تم التسليم", "Yes - Delivered"] else "stored"
    harvest = farm_core.record_harvest(
        crop_id=context.user_data['crop_id'],
        harvest_date=context.user_data['harvest_date'],
        quantity=context.user_data['harvest_quantity'],
        notes=None,
        status=status
    )
    if not harvest:
        await update.message.reply_text(
            "خطأ في تسجيل الحصاد." if lang == 'ar' else "Error recording harvest."
        )
        return ConversationHandler.END
    context.user_data['harvest_id'] = harvest['id']
    if status == "delivered":
        await update.message.reply_text(
            "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)"
        )
        return DELIVERY_COLLECTOR
    else:
        await update.message.reply_text(
            f"تم تسجيل الحصاد بنجاح! ✅ {context.user_data['harvest_quantity']} kg" if lang == 'ar' else f"Harvest recorded! ✅ {context.user_data['harvest_quantity']} kg",
            reply_markup=get_main_keyboard(lang)
        )
        return ConversationHandler.END

async def delivery_collector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    context.user_data['collector_name'] = None if text.lower() in ["تخطي", "skip"] else text
    await update.message.reply_text(
        "إلى أي سوق؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Which market? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_MARKET

async def delivery_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    market = None if text.lower() in ["تخطي", "skip"] else text
    delivery = farm_core.record_delivery(
        harvest_id=context.user_data['harvest_id'],
        delivery_date=date.today(),
        collector_name=context.user_data['collector_name'],
        market=market
    )
    if delivery:
        await update.message.reply_text(
            "تم تسجيل التسليم! ✅ الدفع متوقع خلال 7 أيام" if lang == 'ar' else "Delivery recorded! ✅ Payment expected in 7 days",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "خطأ في تسجيل التسليم." if lang == 'ar' else "Error recording delivery."
        )
    return ConversationHandler.END

# Pending payments
async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    payments = farm_core.get_pending_payments(farmer['id'])
    if not payments:
        await update.message.reply_text(
            "لا توجد مدفوعات معلقة." if lang == 'ar' else "No pending payments."
        )
        return ConversationHandler.END
    message = "💰 المدفوعات المعلقة:\n\n" if lang == 'ar' else "💰 Pending Payments:\n\n"
    for payment in payments:
        crop_name = payment['deliveries']['harvests']['crops']['name']
        quantity = payment['deliveries']['harvests']['quantity']
        expected_date = payment['expected_date']
        amount = payment.get('expected_amount', 'غير محدد' if lang == 'ar' else 'N/A')
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            "تسجيل الدفع" if lang == 'ar' else "Mark Paid",
            callback_data=f"paid_{payment['id']}"
        )]])
        message += f"• {crop_name}: {quantity} kg - {amount} LBP\n  متوقع: {expected_date}\n"
        await update.message.reply_text(message, reply_markup=markup)
        message = ""
    return ConversationHandler.END

async def mark_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    payment_id = query.data.split('_')[1]  # UUID string
    context.user_data['payment_id'] = payment_id
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    await query.message.reply_text(
        "أدخل المبلغ المدفوع (LBP):" if lang == 'ar' else "Enter amount paid (LBP):"
    )
    await query.answer()
    return PAYMENT_AMOUNT

async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        amount = float(update.message.text)
        payment = farm_core.record_payment(
            payment_id=context.user_data['payment_id'],
            paid_amount=amount,
            paid_date=date.today()
        )
        if payment:
            await update.message.reply_text(
                "تم تسجيل الدفع! ✅" if lang == 'ar' else "Payment recorded! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ في تسجيل الدفع." if lang == 'ar' else "Error recording payment."
            )
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return PAYMENT_AMOUNT
    return ConversationHandler.END

# Treatment flow
async def add_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else "No crops found. Add a crop first."
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول:" if lang == 'ar' else "Choose crop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_CROP

async def treatment_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود." if lang == 'ar' else "Crop not found."
        )
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    await update.message.reply_text(
        "ما هو اسم المنتج؟ (مثال: مبيد، سماد)" if lang == 'ar' else "What's the product name? (e.g., pesticide, fertilizer)"
    )
    return TREATMENT_PRODUCT

async def treatment_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_name'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    keyboard = [["اليوم" if lang == 'ar' else "Today"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم العلاج؟" if lang == 'ar' else "When was the treatment applied?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_DATE

async def treatment_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return TREATMENT_DATE
    try:
        treatment_date = date.today() if text in ["اليوم", "Today"] else datetime.strptime(text, "%Y-%m-%d").date()
        context.user_data['treatment_date'] = treatment_date
        await update.message.reply_text(
            "التكلفة؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Cost? (optional, type 'Skip' to skip)"
        )
        return TREATMENT_COST
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return TREATMENT_DATE

async def treatment_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip']:
        cost = None
    else:
        try:
            cost = float(text)
        except ValueError:
            await update.message.reply_text(
                "أدخل رقمًا صحيحًا أو 'تخطي'." if lang == 'ar' else "Enter a valid number or 'Skip'."
            )
            return TREATMENT_COST
    context.user_data['treatment_cost'] = cost
    keyboard = [["تخطي" if lang == 'ar' else "Skip"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "التاريخ القادم للعلاج؟ (اختياري)" if lang == 'ar' else "Next treatment date? (optional)",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_NEXT_DATE

async def treatment_next_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip']:
        next_date = None
    else:
        try:
            next_date = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            await update.message.reply_text(
                "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
            )
            return TREATMENT_NEXT_DATE
    treatment = farm_core.add_treatment(
        crop_id=context.user_data['crop_id'],
        treatment_date=context.user_data['treatment_date'],
        product_name=context.user_data['product_name'],
        cost=context.user_data['treatment_cost'],
        next_due_date=next_date
    )
    if treatment:
        await update.message.reply_text(
            "تم تسجيل العلاج! ✅" if lang == 'ar' else "Treatment recorded! ✅",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "خطأ في تسجيل العلاج." if lang == 'ar' else "Error recording treatment."
        )
    return ConversationHandler.END

# Expense flow
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    keyboard = [["بدون محصول" if lang == 'ar' else "No Crop"]] + [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول (اختياري):" if lang == 'ar' else "Choose crop (optional):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EXPENSE_CROP

async def expense_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if crop_name in ["بدون محصول", "No Crop"]:
        context.user_data['crop_id'] = None
    else:
        crop = next((c for c in crops if c['name'] == crop_name), None)
        if not crop:
            await update.message.reply_text(
                "المحصول غير موجود." if lang == 'ar' else "Crop not found."
            )
            return EXPENSE_CROP
        context.user_data['crop_id'] = crop['id']
    keyboard = [["بذور" if lang == 'ar' else "Seeds", "سماد" if lang == 'ar' else "Fertilizer", "نقل" if lang == 'ar' else "Transport"]]
    await update.message.reply_text(
        "اختر الفئة:" if lang == 'ar' else "Choose category:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EXPENSE_CATEGORY

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['category'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    await update.message.reply_text(
        "أدخل المبلغ (LBP):" if lang == 'ar' else "Enter amount (LBP):"
    )
    return EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        keyboard = [["اليوم" if lang == 'ar' else "Today"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
        await update.message.reply_text(
            "تاريخ المصروف؟" if lang == 'ar' else "Expense date?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EXPENSE_DATE
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return EXPENSE_AMOUNT

async def expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return EXPENSE_DATE
    try:
        expense_date = date.today() if text in ["اليوم", "Today"] else datetime.strptime(text, "%Y-%m-%d").date()
        expense = farm_core.add_expense(
            farmer_id=farmer['id'],
            expense_date=expense_date,
            category=context.user_data['category'],
            amount=context.user_data['amount'],
            crop_id=context.user_data['crop_id']
        )
        if expense:
            await update.message.reply_text(
                "تم تسجيل المصروف! ✅" if lang == 'ar' else "Expense recorded! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ في تسجيل المصروف." if lang == 'ar' else "Error recording expense."
            )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return EXPENSE_DATE

# Record delivery for stored harvests
async def record_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    harvests = farm_core.get_stored_harvests(farmer['id'])
    if not harvests:
        await update.message.reply_text(
            "لا توجد حصادات مخزنة." if lang == 'ar' else "No stored harvests found."
        )
        return ConversationHandler.END
    keyboard = [[f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})"] for h in harvests]
    await update.message.reply_text(
        "اختر الحصاد للتسليم:" if lang == 'ar' else "Choose harvest to deliver:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELIVERY_COLLECTOR

async def delivery_stored_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    harvests = farm_core.get_stored_harvests(farmer['id'])
    harvest = next((h for h in harvests if f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})" == text), None)
    if not harvest:
        await update.message.reply_text(
            "الحصاد غير موجود." if lang == 'ar' else "Harvest not found."
        )
        return ConversationHandler.END
    context.user_data['harvest_id'] = harvest['id']
    await update.message.reply_text(
        "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_COLLECTOR

# Market prices
async def market_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    prices = farm_core.get_market_prices()
    if not prices:
        await update.message.reply_text(
            "لا توجد أسعار سوق حاليًا." if lang == 'ar' else "No market prices available."
        )
        return
    message = "📈 أسعار السوق:\n\n" if lang == 'ar' else "📈 Market Prices:\n\n"
    for price in prices:
        message += f"• {price['crop_name']}: {price['price_per_kg']} LBP/kg ({price['price_date']})\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# Weekly summary
async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    summary = farm_core.get_weekly_summary(farmer['id'])
    message = "📊 ملخص الأسبوع:\n\n" if lang == 'ar' else "📊 Weekly Summary:\n\n"
    message += f"إجمالي الحصاد: {summary['total_harvest']} kg\n" if lang == 'ar' else f"Total Harvest: {summary['total_harvest']} kg\n"
    message += f"إجمالي المصاريف: {summary['total_expenses']} LBP\n" if lang == 'ar' else f"Total Expenses: {summary['total_expenses']} LBP\n"
    message += f"المدفوعات المعلقة: {summary['total_pending']} LBP\n" if lang == 'ar' else f"Pending Payments: {summary['total_pending']} LBP\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# My crops
async def my_crops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل." if lang == 'ar' else "No crops found."
        )
        return
    message = "🌾 محاصيلك:\n\n" if lang == 'ar' else "🌾 Your Crops:\n\n"
    for crop in crops:
        message += f"• {crop['name']} (مزروع: {crop['planting_date']})\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# My account
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    help_text = (
        "❓ مساعدة:\n\n"
        "• 🇱🇧 حسابي: عرض معلومات الحساب\n"
        "• ➕ أضف محصول: إضافة محصول جديد\n"
        "• 🌾 محاصيلي: عرض جميع المحاصيل\n"
        "• 🧾 سجل الحصاد: تسجيل حصاد جديد\n"
        "• 🚚 سجل التسليم: تسليم المحصول إلى الجامع\n"
        "• 💵 المدفوعات المعلقة: عرض المدفوعات المتوقعة\n"
        "• 🗓️ التسميد/علاج: إضافة علاج أو تسميد\n"
        "• 💸 مصاريف: تسجيل المصاريف\n"
        "• 📈 الأسعار بالسوق: عرض أسعار السوق\n"
        "• 📊 ملخص الاسبوع: عرض ملخص الأسبوع\n"
    ) if lang == 'ar' else (
        "❓ Help:\n\n"
        "• 🇱🇧 My Account: View account information\n"
        "• ➕ Add Crop: Add a new crop\n"
        "• 🌾 My Crops: View all crops\n"
        "• 🧾 Record Harvest: Record a new harvest\n"
        "• 🚚 Record Delivery: Deliver to collector\n"
        "• 💵 Pending Payments: View expected payments\n"
        "• 🗓️ Fertilize & Treat: Add treatment or fertilization\n"
        "• 💸 Expenses: Record expenses\n"
        "• 📈 Market Prices: View market prices\n"
        "• 📊 Weekly Summary: View weekly summary\n"
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    await update.message.reply_text(
        "تم الإلغاء." if lang == 'ar' else "Cancelled.",
        reply_markup=get_main_keyboard(lang)
    )
    return ConversationHandler.END

# Handle main menu selections
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    if text in ["🇱🇧 حسابي", "🇱🇧 My Account"]:
        await my_account(update, context)
    elif text in ["🌾 محاصيلي", "🌾 My Crops"]:
        await my_crops(update, context)
    elif text in ["📈 الأسعار بالسوق", "📈 Market Prices"]:
        await market_prices(update, context)
    elif text in ["📊 ملخص الاسبوع", "📊 Weekly Summary"]:
        await weekly_summary(update, context)
    elif text in ["❓مساعدة", "❓Help"]:
        await help_command(update, context)

def main() -> None:
    application = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    # Registration conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_selection)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add crop conversation handler
    crop_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(➕ أضف محصول|Add Crop)$"), add_crop)],
        states={
            CROP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_name)],
            CROP_PLANTING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_planting_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Record harvest conversation handler
    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|Record Harvest)$"), record_harvest)],
        states={
            HARVEST_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_crop)],
            HARVEST_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_date)],
            HARVEST_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quantity)],
            HARVEST_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery)],
            DELIVERY_COLLECTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_collector)],
            DELIVERY_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_market)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Treatment conversation handler
    treatment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🗓️ التسميد/علاج|Fertilize & Treat)$"), add_treatment)],
        states={
            TREATMENT_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_crop)],
            TREATMENT_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_product)],
            TREATMENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_date)],
            TREATMENT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_cost)],
            TREATMENT_NEXT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_next_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Expense conversation handler
    expense_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|Expenses)$"), add_expense)],
        states={
            EXPENSE_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)],
            EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Payment conversation handler
    payment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💵 المدفوعات المعلقة|Pending Payments)$"), pending_payments)],
        states={
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add handlers
    application.add_handler(reg_conv_handler)
    application.add_handler(crop_conv_handler)
    application.add_handler(harvest_conv_handler)
    application.add_handler(treatment_conv_handler)
    application.add_handler(expense_conv_handler)
    application.add_handler(payment_conv_handler)
    application.add_handler(MessageHandler(filters.Regex("^(🚚 سجل التسليم|Record Delivery)$"), record_delivery))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(mark_paid_callback))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()'''




























"""import os
import logging
import asyncio
from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram.error import NetworkError, TelegramError
from farmcore import FarmCore
from typing import Dict, List, Optional, Tuple
import re
import json
from decimal import Decimal, InvalidOperation

# Enhanced logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("farmbot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FarmCore
farm_core = FarmCore()

# Define conversation states
LANGUAGE, NAME, PHONE, VILLAGE = range(4)
CROP_NAME, CROP_PLANTING_DATE, CROP_AREA = range(3)
HARVEST_CROP, HARVEST_DATE, HARVEST_QUANTITY, HARVEST_QUALITY, HARVEST_DELIVERY, DELIVERY_COLLECTOR, DELIVERY_MARKET = range(7)
TREATMENT_CROP, TREATMENT_PRODUCT, TREATMENT_DATE, TREATMENT_COST, TREATMENT_NEXT_DATE = range(5)
EXPENSE_CROP, EXPENSE_CATEGORY, EXPENSE_AMOUNT, EXPENSE_DATE, EXPENSE_DESCRIPTION = range(5)
PAYMENT_AMOUNT, PAYMENT_CONFIRMATION = range(2)
FEEDBACK = range(1)

# Rate limiting configuration
RATE_LIMIT_SECONDS = 1.5
user_last_interaction = {}
user_sessions = {}

# Cache for market prices
market_prices_cache = {"data": None, "timestamp": None}
CACHE_DURATION = 3600  # 1 hour

# Main keyboard with improved layout
def get_main_keyboard(language='ar'):
    keyboard = [
        ["👤 حسابي" if language == 'ar' else "👤 My Account", "🌱 أضف محصول" if language == 'ar' else "🌱 Add Crop"],
        ["🌾 محاصيلي" if language == 'ar' else "🌾 My Crops", "📊 إحصاءات" if language == 'ar' else "📊 Statistics"],
        ["📦 سجل الحصاد" if language == 'ar' else "📦 Record Harvest", "🚚 سجل التسليم" if language == 'ar' else "🚚 Record Delivery"],
        ["💰 المدفوعات" if language == 'ar' else "💰 Payments", "💸 المصاريف" if language == 'ar' else "💸 Expenses"],
        ["🧴 العلاجات" if language == 'ar' else "🧴 Treatments", "📈 أسعار السوق" if language == 'ar' else "📈 Market Prices"],
        ["📝 الملاحظات" if language == 'ar' else "📝 Feedback", "❓ المساعدة" if language == 'ar' else "❓ Help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Date picker inline keyboard
def get_date_picker(language='ar'):
    today = date.today()
    keyboard = [
        [InlineKeyboardButton("اليوم" if language == 'ar' else "Today", callback_data=f"date_{today.isoformat()}"),
         InlineKeyboardButton("أمس" if language == 'ar' else "Yesterday", callback_data=f"date_{(today - timedelta(days=1)).isoformat()}")],
        [InlineKeyboardButton("اختر تاريخًا" if language == 'ar' else "Pick Date", callback_data="date_manual")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Quality selection keyboard
def get_quality_keyboard(language='ar'):
    keyboard = [
        ["ممتاز" if language == 'ar' else "Excellent", "جيد" if language == 'ar' else "Good"],
        ["متوسط" if language == 'ar' else "Average", "ضعيف" if language == 'ar' else "Poor"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Expense categories keyboard
def get_expense_categories(language='ar'):
    keyboard = [
        ["بذور" if language == 'ar' else "Seeds", "أسمدة" if language == 'ar' else "Fertilizers"],
        ["مبيدات" if language == 'ar' else "Pesticides", "ري" if language == 'ar' else "Irrigation"],
        ["عمالة" if language == 'ar' else "Labor", "وقود" if language == 'ar' else "Fuel"],
        ["نقل" if language == 'ar' else "Transport", "أخرى" if language == 'ar' else "Other"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Rate limiting check
def is_rate_limited(user_id: int) -> bool:
    now = datetime.now().timestamp()
    last_interaction = user_last_interaction.get(user_id, 0)
    if now - last_interaction < RATE_LIMIT_SECONDS:
        return True
    user_last_interaction[user_id] = now
    return False

# Format currency for display
def format_currency(amount, language='ar'):
    if amount is None:
        return "غير محدد" if language == 'ar' else "Not specified"
    return f"{amount:,.0f} ل.ل" if language == 'ar' else f"{amount:,.0f} LBP"

# Format decimal numbers
def format_decimal(number, language='ar'):
    if number is None:
        return "غير محدد" if language == 'ar' else "Not specified"
    return f"{number:,.1f}"

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    telegram_id = user.id

    if is_rate_limited(telegram_id):
        await update.message.reply_text("يرجى الانتظار قليلاً قبل إرسال طلب آخر." if language == 'ar' else "Please wait a moment before sending another request.")
        return ConversationHandler.END

    farmer = farm_core.get_farmer(telegram_id)

    if farmer:
        welcome_message = (
            f"مرحبًا بعودتك، {farmer['name']}! 👋\n\n"
            f"مزرعتك في {farmer['village']} تزدهر 🌱\n"
            f"اختر من الخيارات أدناه لإدارة مزرعتك:"
        ) if farmer['language'] == 'ar' else (
            f"Welcome back, {farmer['name']}! 👋\n\n"
            f"Your farm in {farmer['village']} is thriving 🌱\n"
            f"Choose from the options below to manage your farm:"
        )
        await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard(farmer['language']))

        # Send upcoming treatment reminders
        treatments = farm_core.get_upcoming_treatments(farmer['id'])
        if treatments:
            reminder = "🔔 تذكير: لديك علاجات قادمة:\n\n" if farmer['language'] == 'ar' else "🔔 Reminder: Upcoming treatments:\n\n"
            for t in treatments:
                crop_name = t['crops']['name'] if t.get('crops') else "محصول غير معروف"
                reminder += f"• {crop_name}: {t['product_name']} في {t['next_due_date']}\n"
            await update.message.reply_text(reminder)

        # Check for pending payments
        payments = farm_core.get_pending_payments(farmer['id'])
        if payments:
            payment_msg = "💵 لديك مدفوعات معلقة:\n\n" if farmer['language'] == 'ar' else "💵 You have pending payments:\n\n"
            for p in payments[:3]:  # Show only first 3
                delivery = p.get('deliveries', {})
                harvest = delivery.get('harvests', {}) if delivery else {}
                crop = harvest.get('crops', {}) if harvest else {}
                crop_name = crop.get('name', 'محصول غير معروف') if farmer['language'] == 'ar' else crop.get('name', 'Unknown crop')
                amount = format_currency(p.get('expected_amount'), farmer['language'])
                payment_msg += f"• {crop_name}: {amount} (متوقع: {p.get('expected_date')})\n"

            if len(payments) > 3:
                payment_msg += f"\nو {len(payments) - 3} أكثر..." if farmer['language'] == 'ar' else f"\nAnd {len(payments) - 3} more..."

            await update.message.reply_text(
                payment_msg,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "عرض جميع المدفوعات" if farmer['language'] == 'ar' else "View All Payments",
                        callback_data="view_payments"
                    )
                ]])
            )
        return ConversationHandler.END
    else:
        # Initialize user session
        user_sessions[telegram_id] = {
            'language': 'ar',
            'registration_step': 'language'
        }

        await update.message.reply_text(
            "مرحبًا! 🌱 يبدو أن هذه أول مرة تستخدم فيها بوت FarmBot.\n\n"
            "Welcome! 🌱 It looks like this is your first time using FarmBot.\n\n"
            "اختر اللغة / Choose language:",
            reply_markup=ReplyKeyboardMarkup([["عربي", "English"]], resize_keyboard=True)
        )
        return LANGUAGE

# Onboarding flow
async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id

    if text not in ["عربي", "English"]:
        await update.message.reply_text(
            "يرجى اختيار اللغة من الخيارات المتاحة.\nPlease choose a language from the available options.",
            reply_markup=ReplyKeyboardMarkup([["عربي", "English"]], resize_keyboard=True)
        )
        return LANGUAGE

    user_sessions[user_id]['language'] = 'ar' if text == "عربي" else 'en'
    lang = user_sessions[user_id]['language']
    user_sessions[user_id]['registration_step'] = 'name'

    await update.message.reply_text(
        "ما هو اسمك الكامل؟ مثال: محمد أحمد" if lang == 'ar' else "What's your full name? Example: Mohammed Ahmed",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_sessions[user_id]['language']

    if not name or len(name) < 2:
        await update.message.reply_text(
            "يرجى إدخال اسم صالح (حرفين على الأقل)." if lang == 'ar' else "Please enter a valid name (at least 2 characters)."
        )
        return NAME

    user_sessions[user_id]['name'] = name
    user_sessions[user_id]['registration_step'] = 'phone'

    await update.message.reply_text(
        "ما هو رقم هاتفك؟ مثال: +96170123456" if lang == 'ar' else "What's your phone number? Example: +96170123456"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_sessions[user_id]['language']

    # Basic phone validation
    if not re.match(r"^\+?[0-9\s\-\(\)]{8,20}$", phone):
        await update.message.reply_text(
            "يرجى إدخال رقم هاتف صالح (مثال: +96170123456)." if lang == 'ar' else "Please enter a valid phone number (e.g., +96170123456)."
        )
        return PHONE

    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['registration_step'] = 'village'

    # Get location suggestions based on common farming areas in Lebanon
    location_suggestions = ["بعلبك", "زحلة", "الهرمل", "البقاع", "صور", "صيدا", "طرابلس", "جبيل", "عكار"]
    if lang != 'ar':
        location_suggestions = ["Baalbek", "Zahle", "Hermel", "Bekaa", "Tyre", "Sidon", "Tripoli", "Byblos", "Akkar"]

    keyboard = [[loc] for loc in location_suggestions] + [["أخرى" if lang == 'ar' else "Other"]]

    await update.message.reply_text(
        "ما هي قريتك أو منطقتك؟ اختر من القائمة أو اكتب اسم منطقتك:" if lang == 'ar' else
        "What's your village or area? Choose from the list or type your area name:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return VILLAGE

async def get_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    village = update.message.text.strip()
    user_id = update.effective_user.id
    lang = user_sessions[user_id]['language']

    if not village or len(village) < 2:
        await update.message.reply_text(
            "يرجى إدخال اسم قرية صالح." if lang == 'ar' else "Please enter a valid village name."
        )
        return VILLAGE

    user_sessions[user_id]['village'] = village
    telegram_id = update.effective_user.id

    # Create farmer account
    farmer = farm_core.create_farmer(
        telegram_id=telegram_id,
        name=user_sessions[user_id]['name'],
        phone=user_sessions[user_id]['phone'],
        village=user_sessions[user_id]['village'],
        language=user_sessions[user_id]['language']
    )

    if farmer:
        # Clean up session
        if user_id in user_sessions:
            del user_sessions[user_id]

        welcome_msg = (
            f"تم إنشاء حسابك بنجاح! ✅\n\n"
            f"👤 الاسم: {farmer['name']}\n"
            f"📞 الهاتف: {farmer['phone']}\n"
            f"🏡 المنطقة: {farmer['village']}\n\n"
            f"🔒 ملاحظة: بياناتك آمنة وتُستخدم فقط لتحسين تجربتك الزراعية.\n\n"
            f"اختر من الخيارات أدناه لبدء إدارة مزرعتك:"
        ) if lang == 'ar' else (
            f"Your account has been created successfully! ✅\n\n"
            f"👤 Name: {farmer['name']}\n"
            f"📞 Phone: {farmer['phone']}\n"
            f"🏡 Area: {farmer['village']}\n\n"
            f"🔒 Note: Your data is secure and used only to improve your farming experience.\n\n"
            f"Choose from the options below to start managing your farm:"
        )

        await update.message.reply_text(welcome_msg, reply_markup=get_main_keyboard(lang))

        # Send quick guide
        guide_msg = (
            "📋 دليل سريع:\n\n"
            "• أضف محاصيلك باستخدام زر '🌱 أضف محصول'\n"
            "• سجل حصادك باستخدام '📦 سجل الحصاد'\n"
            "• تتبع مصاريفك باستخدام '💸 المصاريف'\n"
            "• تابع أسعار السوق باستخدام '📈 أسعار السوق'"
        ) if lang == 'ar' else (
            "📋 Quick Guide:\n\n"
            "• Add your crops using '🌱 Add Crop'\n"
            "• Record your harvest using '📦 Record Harvest'\n"
            "• Track expenses using '💸 Expenses'\n"
            "• Follow market prices using '📈 Market Prices'"
        )

        await update.message.reply_text(guide_msg)
    else:
        await update.message.reply_text(
            "حدث خطأ أثناء إنشاء الحساب. يرجى المحاولة مرة أخرى." if lang == 'ar' else
            "Error creating account. Please try again."
        )

    return ConversationHandler.END

# Add crop flow
async def add_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    lang = farmer['language']

    # Initialize crop session
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['crop'] = {}

    # Dynamic crop suggestions based on market prices and season
    current_month = datetime.now().month
    seasonal_crops = get_seasonal_crops(current_month, lang)

    keyboard = [[crop] for crop in seasonal_crops] + [["أدخل اسم آخر" if lang == 'ar' else "Enter another name"]]

    await update.message.reply_text(
        "ما هو اسم المحصول؟ اختر من المحاصيل المناسبة لهذا الموسم أو أدخل اسمًا جديدًا:" if lang == 'ar' else
        "What's the crop name? Choose from seasonal crops or enter a new one:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CROP_NAME

def get_seasonal_crops(month, language='ar'):
    # Crops suitable for planting in different seasons in Lebanon
    spring_crops = ["طماطم", "خيار", "فلفل", "باذنجان", "كوسا"] if language == 'ar' else ["Tomato", "Cucumber", "Pepper", "Eggplant", "Zucchini"]
    summer_crops = ["بطيخ", "شمام", "ذرة", "بامية", "بقلة"] if language == 'ar' else ["Watermelon", "Melon", "Corn", "Okra", "Purslane"]
    fall_crops = ["خس", "سبانخ", "جزر", "فجل", "بصل"] if language == 'ar' else ["Lettuce", "Spinach", "Carrot", "Radish", "Onion"]
    winter_crops = ["ثوم", "كراث", "ملفوف", "بروكلي", "قرنبيط"] if language == 'ar' else ["Garlic", "Leek", "Cabbage", "Broccoli", "Cauliflower"]

    if month in [3, 4, 5]:  # Spring
        return spring_crops
    elif month in [6, 7, 8]:  # Summer
        return summer_crops
    elif month in [9, 10, 11]:  # Fall
        return fall_crops
    else:  # Winter
        return winter_crops

async def crop_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if not crop_name or len(crop_name) < 2:
        await update.message.reply_text(
            "يرجى إدخال اسم محصول صالح." if lang == 'ar' else "Please enter a valid crop name."
        )
        return CROP_NAME

    user_sessions[user_id]['crop']['name'] = crop_name

    await update.message.reply_text(
        "متى تم زراعة المحصول؟ اختر تاريخًا:" if lang == 'ar' else "When was the crop planted? Choose a date:",
        reply_markup=get_date_picker(lang)
    )
    return CROP_PLANTING_DATE

async def crop_planting_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    user_id = update.effective_user.id

    query = update.callback_query
    if query:
        await query.answer()
        text = query.data
    else:
        text = update.message.text

    if text == "date_manual":
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD). مثال: 2025-08-20" if lang == 'ar' else "Enter date (YYYY-MM-DD). Example: 2025-08-20"
        )
        return CROP_PLANTING_DATE

    try:
        if text.startswith("date_"):
            planting_date = datetime.strptime(text.split("_")[1], "%Y-%m-%d").date()
        else:
            planting_date = datetime.strptime(text, "%Y-%m-%d").date()

        # Validate date (not in the future)
        if planting_date > date.today():
            await update.message.reply_text(
                "لا يمكن أن يكون تاريخ الزراعة في المستقبل. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                "Planting date cannot be in the future. Please enter a valid date."
            )
            return CROP_PLANTING_DATE

        user_sessions[user_id]['crop']['planting_date'] = planting_date

        await update.message.reply_text(
            "ما هي مساحة الأرض المزروعة (بالدونم)؟ مثال: 2.5" if lang == 'ar' else
            "What is the planted area (in dunums)? Example: 2.5"
        )
        return CROP_AREA

    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD (مثال: 2025-08-20)." if lang == 'ar' else
            "Invalid date format. Use YYYY-MM-DD (e.g., 2025-08-20)."
        )
        return CROP_PLANTING_DATE

async def crop_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    try:
        area = float(update.message.text)
        if area <= 0:
            raise ValueError("Area must be positive")

        user_sessions[user_id]['crop']['area'] = area

        # Add the crop to database
        crop_data = user_sessions[user_id]['crop']
        crop = farm_core.add_crop(
            farmer_id=farmer['id'],
            name=crop_data['name'],
            planting_date=crop_data['planting_date'],
            area=area
        )

        if crop:
            # Clean up session
            if 'crop' in user_sessions[user_id]:
                del user_sessions[user_id]['crop']

            # Get expected harvest dates based on crop type (simplified)
            harvest_info = get_harvest_info(crop_data['name'], crop_data['planting_date'], lang)

            success_msg = (
                f"تم إضافة المحصول {crop['name']} بنجاح! ✅\n"
                f"تاريخ الزراعة: {crop_data['planting_date']}\n"
                f"المساحة: {area} دونم\n"
                f"{harvest_info}"
            ) if lang == 'ar' else (
                f"Crop {crop['name']} added successfully! ✅\n"
                f"Planting date: {crop_data['planting_date']}\n"
                f"Area: {area} dunums\n"
                f"{harvest_info}"
            )

            await update.message.reply_text(success_msg, reply_markup=get_main_keyboard(lang))
        else:
            await update.message.reply_text(
                "خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang == 'ar' else "Error adding crop. Please try again."
            )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "يرجى إدخال رقم صحيح للمساحة (مثال: 2.5)." if lang == 'ar' else
            "Please enter a valid number for area (e.g., 2.5)."
        )
        return CROP_AREA

def get_harvest_info(crop_name, planting_date, language='ar'):
    # Simplified harvest estimation based on common crops in Lebanon
    harvest_times = {
        "طماطم": 90, "Tomato": 90,
        "خيار": 60, "Cucumber": 60,
        "فلفل": 80, "Pepper": 80,
        "باذنجان": 85, "Eggplant": 85,
        "كوسا": 50, "Zucchini": 50,
        "بطيخ": 85, "Watermelon": 85,
        "شمام": 80, "Melon": 80,
        "ذرة": 75, "Corn": 75,
        "بامية": 55, "Okra": 55,
        "خس": 45, "Lettuce": 45,
        "سبانخ": 40, "Spinach": 40,
        "جزر": 70, "Carrot": 70,
        "فجل": 30, "Radish": 30,
        "بصل": 100, "Onion": 100,
        "ثوم": 120, "Garlic": 120,
        "كراث": 90, "Leek": 90,
        "ملفوف": 85, "Cabbage": 85,
        "بروكلي": 70, "Broccoli": 70,
        "قرنبيط": 75, "Cauliflower": 75
    }

    days_to_harvest = harvest_times.get(crop_name, 60)  # Default to 60 days
    expected_harvest = planting_date + timedelta(days=days_to_harvest)

    if language == 'ar':
        return f"من المتوقع أن يكون الحصاد بعد حوالي {days_to_harvest} يومًا (حوالي {expected_harvest})"
    else:
        return f"Harvest is expected in about {days_to_harvest} days (around {expected_harvest})"

# Record harvest flow
async def record_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else
            "No crops found. Add a crop first."
        )
        return ConversationHandler.END

    lang = farmer['language']

    # Initialize harvest session
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['harvest'] = {}

    # Show only crops that are ready for harvest (simplified logic)
    ready_crops = [crop for crop in crops if is_crop_ready(crop)]

    if not ready_crops:
        await update.message.reply_text(
            "لا توجد محاصيل جاهزة للحصاد بعد." if lang == 'ar' else
            "No crops are ready for harvest yet."
        )
        return ConversationHandler.END

    keyboard = [[crop['name']] for crop in ready_crops]

    await update.message.reply_text(
        "اختر المحصول الذي تريد تسجيل حصاده:" if lang == 'ar' else "Choose the crop you want to record harvest for:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_CROP

def is_crop_ready(crop):
    # Simplified logic to determine if a crop is ready for harvest
    planting_date = crop.get('planting_date')
    if not planting_date:
        return False

    if isinstance(planting_date, str):
        planting_date = datetime.strptime(planting_date, "%Y-%m-%d").date()

    days_planted = (date.today() - planting_date).days

    # Assume most crops are ready between 45-120 days
    return 45 <= days_planted <= 120

async def harvest_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)

    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود. حاول مرة أخرى." if lang == 'ar' else "Crop not found. Try again."
        )
        return HARVEST_CROP

    user_sessions[user_id]['harvest']['crop_id'] = crop['id']

    await update.message.reply_text(
        "متى تم الحصاد؟ اختر تاريخًا:" if lang == 'ar' else "When was the harvest? Choose a date:",
        reply_markup=get_date_picker(lang)
    )
    return HARVEST_DATE

async def harvest_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    user_id = update.effective_user.id

    query = update.callback_query
    if query:
        await query.answer()
        text = query.data
    else:
        text = update.message.text

    if text == "date_manual":
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD). مثال: 2025-08-20" if lang == 'ar' else "Enter date (YYYY-MM-DD). Example: 2025-08-20"
        )
        return HARVEST_DATE

    try:
        if text.startswith("date_"):
            harvest_date = datetime.strptime(text.split("_")[1], "%Y-%m-%d").date()
        else:
            harvest_date = datetime.strptime(text, "%Y-%m-%d").date()

        # Validate date (not in the future and not before planting date)
        if harvest_date > date.today():
            await update.message.reply_text(
                "لا يمكن أن يكون تاريخ الحصاد في المستقبل. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                "Harvest date cannot be in the future. Please enter a valid date."
            )
            return HARVEST_DATE

        # Get crop planting date for validation
        crop_id = user_sessions[user_id]['harvest']['crop_id']
        crop = farm_core.get_crop(crop_id)
        if crop and crop.get('planting_date'):
            planting_date = crop['planting_date']
            if isinstance(planting_date, str):
                planting_date = datetime.strptime(planting_date, "%Y-%m-%d").date()

            if harvest_date < planting_date:
                await update.message.reply_text(
                    "لا يمكن أن يكون تاريخ الحصاد قبل تاريخ الزراعة. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                    "Harvest date cannot be before planting date. Please enter a valid date."
                )
                return HARVEST_DATE

        user_sessions[user_id]['harvest']['harvest_date'] = harvest_date

        await update.message.reply_text(
            "كم الكمية (كجم)؟ مثال: 50.5" if lang == 'ar' else "Enter quantity (kg): Example: 50.5"
        )
        return HARVEST_QUANTITY

    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD." if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD."
        )
        return HARVEST_DATE

async def harvest_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    try:
        quantity = float(update.message.text)
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        user_sessions[user_id]['harvest']['quantity'] = quantity

        await update.message.reply_text(
            "ما هي جودة المحصول؟" if lang == 'ar' else "What is the quality of the harvest?",
            reply_markup=get_quality_keyboard(lang)
        )
        return HARVEST_QUALITY

    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا (مثال: 50.5)." if lang == 'ar' else "Enter a valid number (e.g., 50.5)."
        )
        return HARVEST_QUANTITY

async def harvest_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    quality_map = {
        "ممتاز": "excellent", "Excellent": "excellent",
        "جيد": "good", "Good": "good",
        "متوسط": "average", "Average": "average",
        "ضعيف": "poor", "Poor": "poor"
    }

    quality = quality_map.get(text, "good")
    user_sessions[user_id]['harvest']['quality'] = quality

    keyboard = [["نعم - تم التسليم" if lang == 'ar' else "Yes - Delivered", "لا - مخزون" if lang == 'ar' else "No - Stored"]]

    await update.message.reply_text(
        "هل تم تسليمه إلى الجامع؟" if lang == 'ar' else "Was it handed to the collector?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_DELIVERY

async def harvest_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    status = "delivered" if text in ["نعم - تم التسليم", "Yes - Delivered"] else "stored"

    # Record the harvest
    harvest_data = user_sessions[user_id]['harvest']
    harvest = farm_core.record_harvest(
        crop_id=harvest_data['crop_id'],
        harvest_date=harvest_data['harvest_date'],
        quantity=harvest_data['quantity'],
        quality=harvest_data.get('quality', 'good'),
        notes=None,
        status=status
    )

    if not harvest:
        await update.message.reply_text(
            "خطأ في تسجيل الحصاد. حاول مرة أخرى." if lang == 'ar' else "Error recording harvest. Try again."
        )
        # Clean up session
        if 'harvest' in user_sessions[user_id]:
            del user_sessions[user_id]['harvest']
        return ConversationHandler.END

    user_sessions[user_id]['harvest_id'] = harvest['id']

    if status == "delivered":
        await update.message.reply_text(
            "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)"
        )
        return DELIVERY_COLLECTOR
    else:
        # Clean up session
        if 'harvest' in user_sessions[user_id]:
            del user_sessions[user_id]['harvest']

        await update.message.reply_text(
            f"تم تسجيل الحصاد بنجاح! ✅ {harvest_data['quantity']} kg" if lang == 'ar' else
            f"Harvest recorded! ✅ {harvest_data['quantity']} kg",
            reply_markup=get_main_keyboard(lang)
        )
        return ConversationHandler.END

async def delivery_collector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    context.user_data['collector_name'] = None if text.lower() in ["تخطي", "skip"] else text

    await update.message.reply_text(
        "إلى أي سوق؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Which market? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_MARKET

async def delivery_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    market = None if text.lower() in ["تخطي", "skip"] else text

    delivery = farm_core.record_delivery(
        harvest_id=user_sessions[user_id]['harvest_id'],
        delivery_date=date.today(),
        collector_name=context.user_data.get('collector_name'),
        market=market
    )

    # Clean up session
    if 'harvest' in user_sessions[user_id]:
        del user_sessions[user_id]['harvest']
    if 'harvest_id' in user_sessions[user_id]:
        del user_sessions[user_id]['harvest_id']
    if 'collector_name' in context.user_data:
        del context.user_data['collector_name']

    if delivery:
        # Calculate expected payment based on market prices
        harvest_data = farm_core.get_harvest(user_sessions[user_id]['harvest_id'])
        crop_name = harvest_data['crops']['name'] if harvest_data.get('crops') else "محصول غير معروف"
        quantity = harvest_data['quantity']

        # Get current market price for the crop
        market_price = farm_core.get_current_market_price(crop_name)
        expected_amount = quantity * market_price if market_price else None

        if expected_amount:
            # Update payment with expected amount
            farm_core.update_payment_expected_amount(delivery['id'], expected_amount)

            payment_msg = (
                f"تم تسجيل التسليم! ✅\n"
                f"الدخل المتوقع: {format_currency(expected_amount, lang)}\n"
                f"سيتم الدفع خلال 7 أيام تقريبًا"
            ) if lang == 'ar' else (
                f"Delivery recorded! ✅\n"
                f"Expected income: {format_currency(expected_amount, lang)}\n"
                f"Payment expected within 7 days"
            )
        else:
            payment_msg = (
                "تم تسجيل التسليم! ✅\n"
                "سيتم الدفع خلال 7 أيام تقريبًا"
            ) if lang == 'ar' else (
                "Delivery recorded! ✅\n"
                "Payment expected within 7 days"
            )

        await update.message.reply_text(payment_msg, reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text(
            "خطأ في تسجيل التسليم. حاول مرة أخرى." if lang == 'ar' else "Error recording delivery. Try again."
        )

    return ConversationHandler.END

# Pending payments with inline actions
async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    lang = farmer['language']
    payments = farm_core.get_pending_payments(farmer['id'])

    if not payments:
        await update.message.reply_text(
            "لا توجد مدفوعات معلقة." if lang == 'ar' else "No pending payments."
        )
        return ConversationHandler.END

    message = "💰 المدفوعات المعلقة:\n\n" if lang == 'ar' else "💰 Pending Payments:\n\n"

    for payment in payments:
        delivery = payment.get('deliveries', {})
        harvest = delivery.get('harvests', {}) if delivery else {}
        crop = harvest.get('crops', {}) if harvest else {}
        crop_name = crop.get('name', 'محصول غير معروف') if lang == 'ar' else crop.get('name', 'Unknown crop')
        quantity = harvest.get('quantity', 0)
        expected_amount = format_currency(payment.get('expected_amount'), lang)
        expected_date = payment.get('expected_date', 'غير محدد')

        message += f"• {crop_name}: {quantity} kg - {expected_amount}\n  متوقع: {expected_date}\n\n"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("تسجيل الدفع" if lang == 'ar' else "Mark Paid", callback_data=f"paid_{payment['id']}")],
            [InlineKeyboardButton("تذكير لاحقًا" if lang == 'ar' else "Remind Later", callback_data=f"remind_{payment['id']}")]
        ])

        await update.message.reply_text(message, reply_markup=markup)
        message = ""

    return ConversationHandler.END

async def mark_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("paid_"):
        payment_id = query.data.split("_")[1]
        user_id = update.effective_user.id

        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['payment_id'] = payment_id

        farmer = farm_core.get_farmer(user_id)
        lang = farmer['language']

        await query.message.reply_text(
            "أدخل المبلغ المدفوع (LBP): مثال: 500000" if lang == 'ar' else "Enter amount paid (LBP): Example: 500000"
        )
        return PAYMENT_AMOUNT

    elif query.data.startswith("remind_"):
        payment_id = query.data.split("_")[1]
        farmer = farm_core.get_farmer(update.effective_user.id)
        farm_core.schedule_reminder(payment_id, date.today() + timedelta(days=3))

        await query.message.reply_text(
            "تم جدولة تذكير بعد 3 أيام." if farmer['language'] == 'ar' else "Reminder scheduled in 3 days."
        )
        return ConversationHandler.END

async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")

        user_sessions[user_id]['paid_amount'] = amount

        payment_id = user_sessions[user_id]['payment_id']
        payment = farm_core.get_payment(payment_id)

        if payment and payment.get('expected_amount'):
            expected = payment['expected_amount']
            difference = amount - expected

            if abs(difference) > expected * 0.1:  # More than 10% difference
                diff_msg = (
                    f"المبلغ المدخل يختلف عن المبلغ المتوقع بمقدار {format_currency(abs(difference), lang)}\n"
                    f"المتوقع: {format_currency(expected, lang)}\n"
                    f"المدخل: {format_currency(amount, lang)}\n\n"
                    f"هل أنت متأكد من المبلغ؟"
                ) if lang == 'ar' else (
                    f"The entered amount differs from the expected amount by {format_currency(abs(difference), lang)}\n"
                    f"Expected: {format_currency(expected, lang)}\n"
                    f"Entered: {format_currency(amount, lang)}\n\n"
                    f"Are you sure about the amount?"
                )

                keyboard = [["نعم", "لا"]]
                await update.message.reply_text(
                    diff_msg,
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                return PAYMENT_CONFIRMATION

        # If no significant difference or no expected amount, proceed with recording
        return await record_payment(update, context)

    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا (مثال: 500000)." if lang == 'ar' else "Enter a valid number (e.g., 500000)."
        )
        return PAYMENT_AMOUNT

async def payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if text in ["نعم", "Yes"]:
        return await record_payment(update, context)
    else:
        await update.message.reply_text(
            "أدخل المبلغ مرة أخرى:" if lang == 'ar' else "Enter the amount again:"
        )
        return PAYMENT_AMOUNT

async def record_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    payment_id = user_sessions[user_id]['payment_id']
    paid_amount = user_sessions[user_id]['paid_amount']

    payment = farm_core.record_payment(
        payment_id=payment_id,
        paid_amount=paid_amount,
        paid_date=date.today()
    )

    # Clean up session
    if 'payment_id' in user_sessions[user_id]:
        del user_sessions[user_id]['payment_id']
    if 'paid_amount' in user_sessions[user_id]:
        del user_sessions[user_id]['paid_amount']

    if payment:
        await update.message.reply_text(
            f"تم تسجيل الدفع! ✅ {format_currency(paid_amount, lang)}" if lang == 'ar' else
            f"Payment recorded! ✅ {format_currency(paid_amount, lang)}",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "خطأ في تسجيل الدفع. حاول مرة أخرى." if lang == 'ar' else "Error recording payment. Try again."
        )

    return ConversationHandler.END

# Treatment flow
async def add_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else
            "No crops found. Add a crop first."
        )
        return ConversationHandler.END

    lang = farmer['language']

    # Initialize treatment session
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['treatment'] = {}

    keyboard = [[crop['name']] for crop in crops]

    await update.message.reply_text(
        "اختر المحصول:" if lang == 'ar' else "Choose crop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_CROP

async def treatment_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)

    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود. حاول مرة أخرى." if lang == 'ar' else "Crop not found. Try again."
        )
        return TREATMENT_CROP

    user_sessions[user_id]['treatment']['crop_id'] = crop['id']

    # Suggest common treatments based on crop type
    common_treatments = get_common_treatments(crop_name, lang)

    keyboard = [[treatment] for treatment in common_treatments] + [["أدخل منتج آخر" if lang == 'ar' else "Enter another product"]]

    await update.message.reply_text(
        "ما هو اسم المنتج؟ اختر من القائمة أو أدخل اسمًا جديدًا:" if lang == 'ar' else
        "What's the product name? Choose from the list or enter a new one:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_PRODUCT

def get_common_treatments(crop_name, language='ar'):
    # Common treatments for different crops in Lebanon
    general_treatments = ["سماد عضوي", "سماد كيماوي", "مبيد حشرات", "مبيد أعشاب", "مبيد فطريات"]
    if language != 'ar':
        general_treatments = ["Organic Fertilizer", "Chemical Fertilizer", "Insecticide", "Herbicide", "Fungicide"]

    crop_specific = {
        "طماطم": ["مبيد الندوة المتأخرة", "سماد الطماطم المتخصص"],
        "Tomato": ["Late Blight Pesticide", "Specialized Tomato Fertilizer"],
        "خيار": ["مبيد البياض الدقيقي", "سماد الخيار المتخصص"],
        "Cucumber": ["Powdery Mildew Pesticide", "Specialized Cucumber Fertilizer"],
        "باذنجان": ["مبيد خنفساء البطاطس", "سماد الباذنجان المتخصص"],
        "Eggplant": ["Colorado Beetle Pesticide", "Specialized Eggplant Fertilizer"]
    }

    treatments = general_treatments + crop_specific.get(crop_name, [])
    return treatments

async def treatment_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_name = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if not product_name or len(product_name) < 2:
        await update.message.reply_text(
            "يرجى إدخال اسم منتج صالح." if lang == 'ar' else "Please enter a valid product name."
        )
        return TREATMENT_PRODUCT

    user_sessions[user_id]['treatment']['product_name'] = product_name

    await update.message.reply_text(
        "متى تم العلاج؟ اختر تاريخًا:" if lang == 'ar' else "When was the treatment applied? Choose a date:",
        reply_markup=get_date_picker(lang)
    )
    return TREATMENT_DATE

async def treatment_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    user_id = update.effective_user.id

    query = update.callback_query
    if query:
        await query.answer()
        text = query.data
    else:
        text = update.message.text

    if text == "date_manual":
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD). مثال: 2025-08-20" if lang == 'ar' else "Enter date (YYYY-MM-DD). Example: 2025-08-20"
        )
        return TREATMENT_DATE

    try:
        if text.startswith("date_"):
            treatment_date = datetime.strptime(text.split("_")[1], "%Y-%m-%d").date()
        else:
            treatment_date = datetime.strptime(text, "%Y-%m-%d").date()

        # Validate date (not in the future)
        if treatment_date > date.today():
            await update.message.reply_text(
                "لا يمكن أن يكون تاريخ العلاج في المستقبل. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                "Treatment date cannot be in the future. Please enter a valid date."
            )
            return TREATMENT_DATE

        user_sessions[user_id]['treatment']['treatment_date'] = treatment_date

        await update.message.reply_text(
            "التكلفة؟ (اختياري، اكتب 'تخطي' للتخطي) مثال: 100000" if lang == 'ar' else
            "Cost? (optional, type 'Skip' to skip) Example: 100000"
        )
        return TREATMENT_COST

    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD." if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD."
        )
        return TREATMENT_DATE

async def treatment_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if text.lower() in ['تخطي', 'skip']:
        cost = None
    else:
        try:
            cost = float(text)
            if cost < 0:
                raise ValueError("Cost cannot be negative")
        except ValueError:
            await update.message.reply_text(
                "أدخل رقمًا صحيحًا أو 'تخطي'. مثال: 100000" if lang == 'ar' else
                "Enter a valid number or 'Skip'. Example: 100000"
            )
            return TREATMENT_COST

    user_sessions[user_id]['treatment']['cost'] = cost

    await update.message.reply_text(
        "التاريخ القادم للعلاج؟ (اختياري، اكتب 'تخطي' أو اختر تاريخًا)" if lang == 'ar' else
        "Next treatment date? (optional, type 'Skip' or choose a date)",
        reply_markup=get_date_picker(lang)
    )
    return TREATMENT_NEXT_DATE

async def treatment_next_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    user_id = update.effective_user.id

    query = update.callback_query
    if query:
        await query.answer()
        text = query.data
    else:
        text = update.message.text

    if text.lower() in ['تخطي', 'skip']:
        next_date = None
    else:
        try:
            if text.startswith("date_"):
                next_date = datetime.strptime(text.split("_")[1], "%Y-%m-%d").date()
            else:
                next_date = datetime.strptime(text, "%Y-%m-%d").date()

            # Validate date (not in the past)
            if next_date < date.today():
                await update.message.reply_text(
                    "لا يمكن أن يكون تاريخ العلاج القادم في الماضي. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                    "Next treatment date cannot be in the past. Please enter a valid date."
                )
                return TREATMENT_NEXT_DATE

        except ValueError:
            await update.message.reply_text(
                "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD أو 'تخطي'." if lang == 'ar' else
                "Invalid date format. Use YYYY-MM-DD or 'Skip'."
            )
            return TREATMENT_NEXT_DATE

    treatment_data = user_sessions[user_id]['treatment']
    treatment = farm_core.add_treatment(
        crop_id=treatment_data['crop_id'],
        treatment_date=treatment_data['treatment_date'],
        product_name=treatment_data['product_name'],
        cost=treatment_data.get('cost'),
        next_due_date=next_date
    )

    # Clean up session
    if 'treatment' in user_sessions[user_id]:
        del user_sessions[user_id]['treatment']

    if treatment:
        success_msg = "تم تسجيل العلاج! ✅" if lang == 'ar' else "Treatment recorded! ✅"
        if next_date:
            success_msg += f"\nالتذكير القادم: {next_date}" if lang == 'ar' else f"\nNext reminder: {next_date}"

        await update.message.reply_text(success_msg, reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text(
            "خطأ في تسجيل العلاج. حاول مرة أخرى." if lang == 'ar' else "Error recording treatment. Try again."
        )

    return ConversationHandler.END

# Expense flow
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    lang = farmer['language']

    # Initialize expense session
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['expense'] = {}

    crops = farm_core.get_farmer_crops(farmer['id'])
    keyboard = [["بدون محصول" if lang == 'ar' else "No Crop"]] + [[crop['name']] for crop in crops]

    await update.message.reply_text(
        "اختر المحصول (اختياري):" if lang == 'ar' else "Choose crop (optional):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EXPENSE_CROP

async def expense_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if crop_name in ["بدون محصول", "No Crop"]:
        user_sessions[user_id]['expense']['crop_id'] = None
    else:
        crops = farm_core.get_farmer_crops(farmer['id'])
        crop = next((c for c in crops if c['name'] == crop_name), None)
        if not crop:
            await update.message.reply_text(
                "المحصول غير موجود. حاول مرة أخرى." if lang == 'ar' else "Crop not found. Try again."
            )
            return EXPENSE_CROP
        user_sessions[user_id]['expense']['crop_id'] = crop['id']

    await update.message.reply_text(
        "اختر الفئة:" if lang == 'ar' else "Choose category:",
        reply_markup=get_expense_categories(lang)
    )
    return EXPENSE_CATEGORY

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    if not category:
        await update.message.reply_text(
            "يرجى إدخال فئة صالحة." if lang == 'ar' else "Please enter a valid category."
        )
        return EXPENSE_CATEGORY

    user_sessions[user_id]['expense']['category'] = category

    await update.message.reply_text(
        "أدخل المبلغ (LBP): مثال: 200000" if lang == 'ar' else "Enter amount (LBP): Example: 200000"
    )
    return EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")

        user_sessions[user_id]['expense']['amount'] = amount

        await update.message.reply_text(
            "أدخل وصفًا للمصروف (اختياري):" if lang == 'ar' else "Enter expense description (optional):"
        )
        return EXPENSE_DESCRIPTION

    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا (مثال: 200000)." if lang == 'ar' else "Enter a valid number (e.g., 200000)."
        )
        return EXPENSE_AMOUNT

async def expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    user_sessions[user_id]['expense']['description'] = description if description else None

    await update.message.reply_text(
        "تاريخ المصروف؟ اختر تاريخًا:" if lang == 'ar' else "Expense date? Choose a date:",
        reply_markup=get_date_picker(lang)
    )
    return EXPENSE_DATE

async def expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    user_id = update.effective_user.id

    query = update.callback_query
    if query:
        await query.answer()
        text = query.data
    else:
        text = update.message.text

    if text == "date_manual":
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD). مثال: 2025-08-20" if lang == 'ar' else "Enter date (YYYY-MM-DD). Example: 2025-08-20"
        )
        return EXPENSE_DATE

    try:
        if text.startswith("date_"):
            expense_date = datetime.strptime(text.split("_")[1], "%Y-%m-%d").date()
        else:
            expense_date = datetime.strptime(text, "%Y-%m-%d").date()

        # Validate date (not in the future)
        if expense_date > date.today():
            await update.message.reply_text(
                "لا يمكن أن يكون تاريخ المصروف في المستقبل. يرجى إدخال تاريخ صحيح." if lang == 'ar' else
                "Expense date cannot be in the future. Please enter a valid date."
            )
            return EXPENSE_DATE

        expense_data = user_sessions[user_id]['expense']
        expense = farm_core.add_expense(
            farmer_id=farmer['id'],
            expense_date=expense_date,
            category=expense_data['category'],
            amount=expense_data['amount'],
            crop_id=expense_data.get('crop_id'),
            description=expense_data.get('description')
        )

        # Clean up session
        if 'expense' in user_sessions[user_id]:
            del user_sessions[user_id]['expense']

        if expense:
            await update.message.reply_text(
                f"تم تسجيل المصروف! ✅ {format_currency(expense_data['amount'], lang)}" if lang == 'ar' else
                f"Expense recorded! ✅ {format_currency(expense_data['amount'], lang)}",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ في تسجيل المصروف. حاول مرة أخرى." if lang == 'ar' else "Error recording expense. Try again."
            )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD." if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD."
        )
        return EXPENSE_DATE

# Record delivery for stored harvests
async def record_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return ConversationHandler.END

    lang = farmer['language']
    harvests = farm_core.get_stored_harvests(farmer['id'])

    if not harvests:
        await update.message.reply_text(
            "لا توجد حصادات مخزنة." if lang == 'ar' else "No stored harvests found."
        )
        return ConversationHandler.END

    # Initialize delivery session
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['delivery'] = {}

    keyboard = [[f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})"] for h in harvests]

    await update.message.reply_text(
        "اختر الحصاد للتسليم:" if lang == 'ar' else "Choose harvest to deliver:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELIVERY_COLLECTOR

async def delivery_stored_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language']

    harvests = farm_core.get_stored_harvests(farmer['id'])
    harvest = next((h for h in harvests if f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})" == text), None)

    if not harvest:
        await update.message.reply_text(
            "الحصاد غير موجود. حاول مرة أخرى." if lang == 'ar' else "Harvest not found. Try again."
        )
        return DELIVERY_COLLECTOR

    user_sessions[user_id]['delivery']['harvest_id'] = harvest['id']

    await update.message.reply_text(
        "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else
        "Collector's name? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_COLLECTOR

# Market prices with inline details
async def market_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return

    lang = farmer['language']

    # Check cache first
    current_time = datetime.now().timestamp()
    if (market_prices_cache['data'] is not None and
        market_prices_cache['timestamp'] is not None and
        current_time - market_prices_cache['timestamp'] < CACHE_DURATION):
        prices = market_prices_cache['data']
    else:
        prices = farm_core.get_market_prices()
        market_prices_cache['data'] = prices
        market_prices_cache['timestamp'] = current_time

    if not prices:
        await update.message.reply_text(
            "لا توجد أسعار سوق حاليًا." if lang == 'ar' else "No market prices available."
        )
        return

    message = "📈 أسعار السوق الحالية:\n\n" if lang == 'ar' else "📈 Current Market Prices:\n\n"

    # Group prices by crop and get the latest price for each
    crop_prices = {}
    for price in prices:
        crop_name = price['crop_name']
        if crop_name not in crop_prices or price['price_date'] > crop_prices[crop_name]['price_date']:
            crop_prices[crop_name] = price

    # Sort crops by name
    sorted_crops = sorted(crop_prices.keys())

    for crop in sorted_crops:
        price_data = crop_prices[crop]
        message += f"• {crop}: {format_currency(price_data['price_per_kg'], lang)}/kg ({price_data['price_date']})\n"

    message += "\n💡 ملاحظة: الأسعار قد تختلف حسب الجودة والمنطقة" if lang == 'ar' else "\n💡 Note: Prices may vary by quality and region"

    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# Weekly summary with detailed breakdown
async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return

    lang = farmer['language']
    summary = farm_core.get_weekly_summary(farmer['id'])

    message = "📊 ملخص الأسبوع:\n\n" if lang == 'ar' else "📊 Weekly Summary:\n\n"
    message += f"إجمالي الحصاد: {format_decimal(summary['total_harvest'])} kg\n" if lang == 'ar' else f"Total Harvest: {format_decimal(summary['total_harvest'])} kg\n"
    message += f"إجمالي المصاريف: {format_currency(summary['total_expenses'], lang)}\n" if lang == 'ar' else f"Total Expenses: {format_currency(summary['total_expenses'], lang)}\n"
    message += f"المدفوعات المعلقة: {format_currency(summary['total_pending'], lang)}\n" if lang == 'ar' else f"Pending Payments: {format_currency(summary['total_pending'], lang)}\n"

    if summary['harvests']:
        message += "\nتفاصيل الحصاد:\n" if lang == 'ar' else "\nHarvest Details:\n"
        for h in summary['harvests']:
            crop_name = h['crops']['name'] if h.get('crops') else "محصول غير معروف"
            message += f"• {crop_name}: {format_decimal(h['quantity'])} kg ({h['harvest_date']})\n"

    if summary['expenses']:
        message += "\nتفاصيل المصاريف:\n" if lang == 'ar' else "\nExpense Details:\n"
        for e in summary['expenses']:
            message += f"• {e['category']}: {format_currency(e['amount'], lang)} ({e['expense_date']})\n"

    # Calculate profit/loss
    income = summary.get('total_income', 0)
    expenses = summary['total_expenses']
    profit = income - expenses

    message += f"\n💰 صافي الدخل: {format_currency(profit, lang)}\n" if lang == 'ar' else f"\n💰 Net Income: {format_currency(profit, lang)}\n"

    if profit > 0:
        message += "📈 أرباح هذا الأسبوع ✅" if lang == 'ar' else "📈 Profit this week ✅"
    else:
        message += "📉 خسائر هذا الأسبوع ❌" if lang == 'ar' else "📉 Loss this week ❌"

    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# My crops with actionable buttons
async def my_crops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return

    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])

    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف واحدًا." if lang == 'ar' else
            "No crops found. Add one."
        )
        return

    message = "🌾 محاصيلك:\n\n" if lang == 'ar' else "🌾 Your Crops:\n\n"

    for crop in crops:
        # Calculate crop status
        status = get_crop_status(crop, lang)

        message += f"• {crop['name']} (مزروع: {crop['planting_date']})\n  {status}\n\n"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("إضافة حصاد" if lang == 'ar' else "Add Harvest", callback_data=f"harvest_{crop['id']}"),
             InlineKeyboardButton("إضافة علاج" if lang == 'ar' else "Add Treatment", callback_data=f"treatment_{crop['id']}")],
            [InlineKeyboardButton("تفاصيل المحصول" if lang == 'ar' else "Crop Details", callback_data=f"details_{crop['id']}")]
        ])

        await update.message.reply_text(message, reply_markup=markup)
        message = ""

    await update.message.reply_text(
        "اختر إجراءً أو عد إلى القائمة." if lang == 'ar' else "Choose an action or return to menu.",
        reply_markup=get_main_keyboard(lang)
    )

def get_crop_status(crop, language='ar'):
    planting_date = crop.get('planting_date')
    if not planting_date:
        return "غير معروف" if language == 'ar' else "Unknown"

    if isinstance(planting_date, str):
        planting_date = datetime.strptime(planting_date, "%Y-%m-%d").date()

    days_planted = (date.today() - planting_date).days

    if days_planted < 30:
        return "🌱 حديث الزراعة" if language == 'ar' else "🌱 Recently planted"
    elif days_planted < 60:
        return "🌿 في طور النمو" if language == 'ar' else "🌿 Growing"
    elif days_planted < 90:
        return "🌻 جاهز للحصاد قريبًا" if language == 'ar' else "🌻 Ready for harvest soon"
    else:
        return "✅ جاهز للحصاد" if language == 'ar' else "✅ Ready for harvest"

# My account with edit option
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if True else "Create an account first. Use /start"
        )
        return

    lang = farmer['language']

    # Get farm statistics
    stats = farm_core.get_farm_statistics(farmer['id'])

    message = (
        f"👤 حساب المزارع:\n\n"
        f"الاسم: {farmer['name']}\n"
        f"القرية: {farmer['village']}\n"
        f"الهاتف: {farmer['phone']}\n\n"
        f"📊 إحصائيات المزرعة:\n"
        f"عدد المحاصيل: {stats['crop_count']}\n"
        f"إجمالي الحصاد: {format_decimal(stats['total_harvest'])} kg\n"
        f"إجمالي الدخل: {format_currency(stats['total_income'], lang)}\n"
        f"إجمالي المصاريف: {format_currency(stats['total_expenses'], lang)}\n"
    ) if lang == 'ar' else (
        f"👤 Farmer Account:\n\n"
        f"Name: {farmer['name']}\n"
        f"Village: {farmer['village']}\n"
        f"Phone: {farmer['phone']}\n\n"
        f"📊 Farm Statistics:\n"
        f"Crops: {stats['crop_count']}\n"
        f"Total Harvest: {format_decimal(stats['total_harvest'])} kg\n"
        f"Total Income: {format_currency(stats['total_income'], lang)}\n"
        f"Total Expenses: {format_currency(stats['total_expenses'], lang)}\n"
    )

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("تعديل الحساب" if lang == 'ar' else "Edit Account", callback_data="edit_account")
    ]])

    await update.message.reply_text(message, reply_markup=markup)

# Feedback command
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    await update.message.reply_text(
        "أخبرنا برأيك أو اقتراحاتك لتحسين البوت! سيتم قراءة جميع الملاحظات بعناية." if lang == 'ar' else
        "Tell us your feedback or suggestions to improve the bot! All feedback will be carefully reviewed."
    )
    return FEEDBACK

async def process_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feedback_text = update.message.text
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language'] if farmer else 'ar'

    # Save feedback to database
    farm_core.record_feedback(user_id, feedback_text)

    await update.message.reply_text(
        "شكرًا لك على ملاحظاتك! نقدر مساهمتك في تحسين البوت." if lang == 'ar' else
        "Thank you for your feedback! We appreciate your contribution to improving the bot.",
        reply_markup=get_main_keyboard(lang)
    )
    return ConversationHandler.END

# Help command with contextual tips
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    help_text = (
        "❓ مساعدة FarmBot:\n\n"
        "• 👤 حسابي: عرض وتعديل معلومات الحساب وإحصائيات المزرعة\n"
        "• 🌱 أضف محصول: إضافة محصول جديد مع معلومات الزراعة\n"
        "• 🌾 محاصيلي: عرض جميع المحاصيل وإدارتها\n"
        "• 📊 إحصاءات: عرض إحصائيات الأداء والربحية\n"
        "• 📦 سجل الحصاد: تسجيل كميات الحصاد وجودتها\n"
        "• 🚚 سجل التسليم: تسجيل تسليم المحصول للجامع\n"
        "• 💰 المدفوعات: إدارة وتتبع المدفوعات المستحقة\n"
        "• 💸 المصاريف: تسجيل مصاريف المزرعة وتصنيفها\n"
        "• 🧴 العلاجات: تسجيل العلاجات والتسميد للمحاصيل\n"
        "• 📈 أسعار السوق: عرض أحدث أسعار السوق للمحاصيل\n\n"
        "💡 نصائح:\n"
        "• استخدم /cancel لإلغاء أي عملية جارية\n"
        "• أدخل البيانات بانتظام للحصول على إحصائيات دقيقة\n"
        "• تتبع أسعار السوق لتحقيق أفضل عائد لمحاصيلك\n\n"
        "📞 للدعم الفني: +96170123456"
    ) if lang == 'ar' else (
        "❓ FarmBot Help:\n\n"
        "• 👤 My Account: View and edit account information and farm statistics\n"
        "• 🌱 Add Crop: Add a new crop with planting information\n"
        "• 🌾 My Crops: View and manage all crops\n"
        "• 📊 Statistics: View performance and profitability statistics\n"
        "• 📦 Record Harvest: Record harvest quantities and quality\n"
        "• 🚚 Record Delivery: Record crop delivery to collector\n"
        "• 💰 Payments: Manage and track due payments\n"
        "• 💸 Expenses: Record and categorize farm expenses\n"
        "• 🧴 Treatments: Record crop treatments and fertilization\n"
        "• 📈 Market Prices: View latest market prices for crops\n\n"
        "💡 Tips:\n"
        "• Use /cancel to cancel any ongoing operation\n"
        "• Enter data regularly for accurate statistics\n"
        "• Track market prices to get the best return for your crops\n\n"
        "📞 Technical Support: +96170123456"
    )

    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    farmer = farm_core.get_farmer(user_id)
    lang = farmer['language'] if farmer else 'ar'

    # Clean up user session
    if user_id in user_sessions:
        del user_sessions[user_id]

    await update.message.reply_text(
        "تم الإلغاء. اختر خيارًا من القائمة." if lang == 'ar' else
        "Cancelled. Choose an option from the menu.",
        reply_markup=get_main_keyboard(lang)
    )
    return ConversationHandler.END

# Quick command shortcuts
async def add_crop_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await add_crop(update, context)

async def my_crops_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return await my_crops(update, context)

async def record_harvest_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await record_harvest(update, context)

async def market_prices_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return await market_prices(update, context)

async def statistics_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return await weekly_summary(update, context)

# Handle main menu selections
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_rate_limited(update.effective_user.id):
        await update.message.reply_text(
            "يرجى الانتظار قليلاً قبل إرسال طلب آخر." if True else
            "Please wait a moment before sending another request."
        )
        return

    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    if text in ["👤 حسابي", "👤 My Account"]:
        await my_account(update, context)
    elif text in ["🌾 محاصيلي", "🌾 My Crops"]:
        await my_crops(update, context)
    elif text in ["📊 إحصاءات", "📊 Statistics"]:
        await weekly_summary(update, context)
    elif text in ["📈 أسعار السوق", "📈 Market Prices"]:
        await market_prices(update, context)
    elif text in ["📝 الملاحظات", "📝 Feedback"]:
        await feedback(update, context)
    elif text in ["❓ المساعدة", "❓ Help"]:
        await help_command(update, context)
    else:
        await update.message.reply_text(
            "لم أفهم طلبك. يرجى اختيار أحد الخيارات من القائمة." if lang == 'ar' else
            "I didn't understand your request. Please choose an option from the menu.",
            reply_markup=get_main_keyboard(lang)
        )

# Handle callback queries
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "view_payments":
        await pending_payments(update, context)
    elif query.data.startswith("harvest_"):
        crop_id = query.data.split("_")[1]
        user_id = update.effective_user.id
        farmer = farm_core.get_farmer(user_id)

        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['harvest'] = {'crop_id': crop_id}

        await query.message.reply_text(
            "متى تم الحصاد؟ اختر تاريخًا:" if farmer['language'] == 'ar' else "When was the harvest? Choose a date:",
            reply_markup=get_date_picker(farmer['language'])
        )
    elif query.data.startswith("treatment_"):
        crop_id = query.data.split("_")[1]
        user_id = update.effective_user.id
        farmer = farm_core.get_farmer(user_id)

        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['treatment'] = {'crop_id': crop_id}

        await query.message.reply_text(
            "ما هو اسم المنتج؟" if farmer['language'] == 'ar' else "What's the product name?",
            reply_markup=ReplyKeyboardRemove()
        )
    elif query.data.startswith("details_"):
        crop_id = query.data.split("_")[1]
        crop = farm_core.get_crop(crop_id)
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language']

        if crop:
            # Get crop details including harvests, treatments, etc.
            details = farm_core.get_crop_details(crop_id)

            message = (
                f"📋 تفاصيل المحصول: {crop['name']}\n\n"
                f"تاريخ الزراعة: {crop['planting_date']}\n"
                f"المساحة: {crop.get('area', 'غير معروف')} دونم\n\n"
            ) if lang == 'ar' else (
                f"📋 Crop Details: {crop['name']}\n\n"
                f"Planting date: {crop['planting_date']}\n"
                f"Area: {crop.get('area', 'Unknown')} dunums\n\n"
            )

            if details.get('harvests'):
                message += "الحصادات:\n" if lang == 'ar' else "Harvests:\n"
                for harvest in details['harvests']:
                    message += f"• {harvest['harvest_date']}: {harvest['quantity']} kg\n"

            if details.get('treatments'):
                message += "\nالعلاجات:\n" if lang == 'ar' else "\nTreatments:\n"
                for treatment in details['treatments']:
                    message += f"• {treatment['treatment_date']}: {treatment['product_name']}\n"

            await query.message.reply_text(message)
        else:
            await query.message.reply_text(
                "لم يتم العثور على المحصول." if lang == 'ar' else "Crop not found."
            )

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if update and update.effective_user:
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language'] if farmer else 'ar'

        error_msg = (
            "عذرًا، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقًا." if lang == 'ar' else
            "Sorry, an unexpected error occurred. Please try again later."
        )

        try:
            await update.message.reply_text(error_msg, reply_markup=get_main_keyboard(lang))
        except:
            # If we can't send a message, just log the error
            pass

def main() -> None:
    # Check for required environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        return

    # Create application
    application = Application.builder().token(token).build()

    # Add error handler
    application.add_error_handler(error_handler)

    # Registration conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_selection)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Add crop conversation handler
    crop_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addcrop", add_crop_shortcut), MessageHandler(filters.Regex("^(🌱 أضف محصول|Add Crop)$"), add_crop)],
        states={
            CROP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_name)],
            CROP_PLANTING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_planting_date), CallbackQueryHandler(crop_planting_date)],
            CROP_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_area)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Record harvest conversation handler
    harvest_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("harvest", record_harvest_shortcut), MessageHandler(filters.Regex("^(📦 سجل الحصاد|Record Harvest)$"), record_harvest)],
        states={
            HARVEST_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_crop)],
            HARVEST_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_date), CallbackQueryHandler(harvest_date)],
            HARVEST_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quantity)],
            HARVEST_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quality)],
            HARVEST_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery)],
            DELIVERY_COLLECTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_collector)],
            DELIVERY_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_market)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Treatment conversation handler
    treatment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧴 العلاجات|Treatments)$"), add_treatment)],
        states={
            TREATMENT_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_crop)],
            TREATMENT_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_product)],
            TREATMENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_date), CallbackQueryHandler(treatment_date)],
            TREATMENT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_cost)],
            TREATMENT_NEXT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_next_date), CallbackQueryHandler(treatment_next_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Expense conversation handler
    expense_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 المصاريف|Expenses)$"), add_expense)],
        states={
            EXPENSE_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)],
            EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_description)],
            EXPENSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date), CallbackQueryHandler(expense_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Payment conversation handler
    payment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💰 المدفوعات|Payments)$"), pending_payments)],
        states={
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
            PAYMENT_CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Feedback conversation handler
    feedback_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(📝 الملاحظات|Feedback)$"), feedback)],
        states={
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_feedback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    # Add handlers
    application.add_handler(reg_conv_handler)
    application.add_handler(crop_conv_handler)
    application.add_handler(harvest_conv_handler)
    application.add_handler(treatment_conv_handler)
    application.add_handler(expense_conv_handler)
    application.add_handler(payment_conv_handler)
    application.add_handler(feedback_conv_handler)

    application.add_handler(MessageHandler(filters.Regex("^(🚚 سجل التسليم|Record Delivery)$"), record_delivery))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CallbackQueryHandler(mark_paid_callback))

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("crops", my_crops_shortcut))
    application.add_handler(CommandHandler("prices", market_prices_shortcut))
    application.add_handler(CommandHandler("stats", statistics_shortcut))
    application.add_handler(CommandHandler("cancel", cancel))

    # Start the bot
    logger.info("Starting FarmBot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
"""


"""
import os
import logging
from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from farmcore import FarmCore

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FarmCore
farm_core = FarmCore()

# Define conversation states
LANGUAGE, NAME, PHONE, VILLAGE = range(4)
CROP_NAME, CROP_PLANTING_DATE = range(2)
HARVEST_CROP, HARVEST_DATE, HARVEST_QUANTITY, HARVEST_DELIVERY, DELIVERY_COLLECTOR, DELIVERY_MARKET = range(6)
TREATMENT_CROP, TREATMENT_PRODUCT, TREATMENT_DATE, TREATMENT_COST, TREATMENT_NEXT_DATE = range(5)
EXPENSE_CROP, EXPENSE_CATEGORY, EXPENSE_AMOUNT, EXPENSE_DATE = range(4)
PAYMENT_AMOUNT = range(1)

# Main keyboard
def get_main_keyboard(language='ar'):
    keyboard = [
        ["🇱🇧 حسابي" if language == 'ar' else "🇱🇧 My Account", "➕ أضف محصول" if language == 'ar' else "➕ Add Crop"],
        ["🌾 محاصيلي" if language == 'ar' else "🌾 My Crops", "🧾 سجل الحصاد" if language == 'ar' else "🧾 Record Harvest"],
        ["🚚 سجل التسليم" if language == 'ar' else "🚚 Record Delivery", "💵 المدفوعات المعلقة" if language == 'ar' else "💵 Pending Payments"],
        ["🗓️ التسميد/علاج" if language == 'ar' else "🗓️ Fertilize & Treat", "💸 مصاريف" if language == 'ar' else "💸 Expenses"],
        ["📈 الأسعار بالسوق" if language == 'ar' else "📈 Market Prices", "📊 ملخص الاسبوع" if language == 'ar' else "📊 Weekly Summary"],
        ["❓مساعدة" if language == 'ar' else "❓Help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

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
        return LANGUAGE

# Onboarding flow
async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data['language'] = 'ar' if text == "عربي" else 'en'
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو اسمك؟" if lang == 'ar' else "What's your name?",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هو رقم هاتفك؟" if lang == 'ar' else "What's your phone number?"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['phone'] = update.message.text
    lang = context.user_data['language']
    await update.message.reply_text(
        "ما هي قريتك أو منطقتك؟" if lang == 'ar' else "What's your village or area?"
    )
    return VILLAGE

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

# Add crop flow
async def add_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [["تفاح" if lang == 'ar' else "Apple", "زيتون" if lang == 'ar' else "Olive"],
                ["طماطم" if lang == 'ar' else "Tomato", "خيار" if lang == 'ar' else "Cucumber"],
                ["بطاطس" if lang == 'ar' else "Potato"]]
    await update.message.reply_text(
        "ما هو اسم المحصول؟" if lang == 'ar' else "What's the crop name?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CROP_NAME

async def crop_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['crop_name'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    keyboard = [["اليوم" if lang == 'ar' else "Today", "أمس" if lang == 'ar' else "Yesterday"],
                ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم زراعة المحصول؟" if lang == 'ar' else "When was the crop planted?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CROP_PLANTING_DATE

async def crop_planting_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']

    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return CROP_PLANTING_DATE

    try:
        planting_date = date.today() if text in ["اليوم", "Today"] else \
                        date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"] else \
                        datetime.strptime(text, "%Y-%m-%d").date()
        crop = farm_core.add_crop(
            farmer_id=farmer['id'],  # Use UUID farmer_id
            name=context.user_data['crop_name'],
            planting_date=planting_date
        )
        if crop:
            await update.message.reply_text(
                f"تم إضافة المحصول {crop['name']} بنجاح! ✅" if lang == 'ar' else f"Crop {crop['name']} added successfully! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang == 'ar' else "Error adding crop. Please try again."
            )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD"
        )
        return CROP_PLANTING_DATE

# Record harvest flow
async def record_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else "No crops found. Add a crop first."
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول:" if lang == 'ar' else "Choose crop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_CROP

async def harvest_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود." if lang == 'ar' else "Crop not found."
        )
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    keyboard = [["اليوم" if lang == 'ar' else "Today", "أمس" if lang == 'ar' else "Yesterday"],
                ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم الحصاد؟" if lang == 'ar' else "When was the harvest?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HARVEST_DATE

async def harvest_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return HARVEST_DATE
    try:
        harvest_date = date.today() if text in ["اليوم", "Today"] else \
                       date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"] else \
                       datetime.strptime(text, "%Y-%m-%d").date()
        context.user_data['harvest_date'] = harvest_date
        await update.message.reply_text(
            "كم الكمية (كجم)؟" if lang == 'ar' else "Enter quantity (kg):"
        )
        return HARVEST_QUANTITY
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return HARVEST_DATE

async def harvest_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        quantity = float(update.message.text)
        context.user_data['harvest_quantity'] = quantity
        keyboard = [["نعم - تم التسليم" if lang == 'ar' else "Yes - Delivered", "لا - مخزون" if lang == 'ar' else "No - Stored"]]
        await update.message.reply_text(
            "هل تم تسليمه إلى الجامع؟" if lang == 'ar' else "Was it handed to the collector?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HARVEST_DELIVERY
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return HARVEST_QUANTITY

async def harvest_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    status = "delivered" if text in ["نعم - تم التسليم", "Yes - Delivered"] else "stored"
    harvest = farm_core.record_harvest(
        crop_id=context.user_data['crop_id'],
        harvest_date=context.user_data['harvest_date'],
        quantity=context.user_data['harvest_quantity'],
        notes=None,
        status=status
    )
    if not harvest:
        await update.message.reply_text(
            "خطأ في تسجيل الحصاد." if lang == 'ar' else "Error recording harvest."
        )
        return ConversationHandler.END
    context.user_data['harvest_id'] = harvest['id']
    if status == "delivered":
        await update.message.reply_text(
            "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)"
        )
        return DELIVERY_COLLECTOR
    else:
        await update.message.reply_text(
            f"تم تسجيل الحصاد بنجاح! ✅ {context.user_data['harvest_quantity']} kg" if lang == 'ar' else f"Harvest recorded! ✅ {context.user_data['harvest_quantity']} kg",
            reply_markup=get_main_keyboard(lang)
        )
        return ConversationHandler.END

async def delivery_collector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    context.user_data['collector_name'] = None if text.lower() in ["تخطي", "skip"] else text
    await update.message.reply_text(
        "إلى أي سوق؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Which market? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_MARKET

async def delivery_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    market = None if text.lower() in ["تخطي", "skip"] else text
    delivery = farm_core.record_delivery(
        harvest_id=context.user_data['harvest_id'],
        delivery_date=date.today(),
        collector_name=context.user_data['collector_name'],
        market=market
    )
    if delivery:
        await update.message.reply_text(
            "تم تسجيل التسليم! ✅ الدفع متوقع خلال 7 أيام" if lang == 'ar' else "Delivery recorded! ✅ Payment expected in 7 days",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "خطأ في تسجيل التسليم." if lang == 'ar' else "Error recording delivery."
        )
    return ConversationHandler.END

# Pending payments
async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    payments = farm_core.get_pending_payments(farmer['id'])
    if not payments:
        await update.message.reply_text(
            "لا توجد مدفوعات معلقة." if lang == 'ar' else "No pending payments."
        )
        return ConversationHandler.END
    message = "💰 المدفوعات المعلقة:\n\n" if lang == 'ar' else "💰 Pending Payments:\n\n"
    for payment in payments:
        crop_name = payment['deliveries']['harvests']['crops']['name']
        quantity = payment['deliveries']['harvests']['quantity']
        expected_date = payment['expected_date']
        amount = payment.get('expected_amount', 'غير محدد' if lang == 'ar' else 'N/A')
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            "تسجيل الدفع" if lang == 'ar' else "Mark Paid",
            callback_data=f"paid_{payment['id']}"
        )]])
        message += f"• {crop_name}: {quantity} kg - {amount} LBP\n  متوقع: {expected_date}\n"
        await update.message.reply_text(message, reply_markup=markup)
        message = ""
    return ConversationHandler.END

async def mark_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    payment_id = query.data.split('_')[1]  # UUID string
    context.user_data['payment_id'] = payment_id
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    await query.message.reply_text(
        "أدخل المبلغ المدفوع (LBP):" if lang == 'ar' else "Enter amount paid (LBP):"
    )
    await query.answer()
    return PAYMENT_AMOUNT

async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        amount = float(update.message.text)
        payment = farm_core.record_payment(
            payment_id=context.user_data['payment_id'],
            paid_amount=amount,
            paid_date=date.today()
        )
        if payment:
            await update.message.reply_text(
                "تم تسجيل الدفع! ✅" if lang == 'ar' else "Payment recorded! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ في تسجيل الدفع." if lang == 'ar' else "Error recording payment."
            )
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return PAYMENT_AMOUNT
    return ConversationHandler.END

# Treatment flow
async def add_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else "No crops found. Add a crop first."
        )
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول:" if lang == 'ar' else "Choose crop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_CROP

async def treatment_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text(
            "المحصول غير موجود." if lang == 'ar' else "Crop not found."
        )
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    await update.message.reply_text(
        "ما هو اسم المنتج؟ (مثال: مبيد، سماد)" if lang == 'ar' else "What's the product name? (e.g., pesticide, fertilizer)"
    )
    return TREATMENT_PRODUCT

async def treatment_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['product_name'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    keyboard = [["اليوم" if lang == 'ar' else "Today"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "متى تم العلاج؟" if lang == 'ar' else "When was the treatment applied?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_DATE

async def treatment_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return TREATMENT_DATE
    try:
        treatment_date = date.today() if text in ["اليوم", "Today"] else datetime.strptime(text, "%Y-%m-%d").date()
        context.user_data['treatment_date'] = treatment_date
        await update.message.reply_text(
            "التكلفة؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Cost? (optional, type 'Skip' to skip)"
        )
        return TREATMENT_COST
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return TREATMENT_DATE

async def treatment_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip']:
        cost = None
    else:
        try:
            cost = float(text)
        except ValueError:
            await update.message.reply_text(
                "أدخل رقمًا صحيحًا أو 'تخطي'." if lang == 'ar' else "Enter a valid number or 'Skip'."
            )
            return TREATMENT_COST
    context.user_data['treatment_cost'] = cost
    keyboard = [["تخطي" if lang == 'ar' else "Skip"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text(
        "التاريخ القادم للعلاج؟ (اختياري)" if lang == 'ar' else "Next treatment date? (optional)",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TREATMENT_NEXT_DATE

async def treatment_next_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip']:
        next_date = None
    else:
        try:
            next_date = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            await update.message.reply_text(
                "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
            )
            return TREATMENT_NEXT_DATE
    treatment = farm_core.add_treatment(
        crop_id=context.user_data['crop_id'],
        treatment_date=context.user_data['treatment_date'],
        product_name=context.user_data['product_name'],
        cost=context.user_data['treatment_cost'],
        next_due_date=next_date
    )
    if treatment:
        await update.message.reply_text(
            "تم تسجيل العلاج! ✅" if lang == 'ar' else "Treatment recorded! ✅",
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text(
            "خطأ في تسجيل العلاج." if lang == 'ar' else "Error recording treatment."
        )
    return ConversationHandler.END

# Expense flow
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    keyboard = [["بدون محصول" if lang == 'ar' else "No Crop"]] + [[crop['name']] for crop in crops]
    await update.message.reply_text(
        "اختر المحصول (اختياري):" if lang == 'ar' else "Choose crop (optional):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EXPENSE_CROP

async def expense_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if crop_name in ["بدون محصول", "No Crop"]:
        context.user_data['crop_id'] = None
    else:
        crop = next((c for c in crops if c['name'] == crop_name), None)
        if not crop:
            await update.message.reply_text(
                "المحصول غير موجود." if lang == 'ar' else "Crop not found."
            )
            return EXPENSE_CROP
        context.user_data['crop_id'] = crop['id']
    keyboard = [["بذور" if lang == 'ar' else "Seeds", "سماد" if lang == 'ar' else "Fertilizer", "نقل" if lang == 'ar' else "Transport"]]
    await update.message.reply_text(
        "اختر الفئة:" if lang == 'ar' else "Choose category:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EXPENSE_CATEGORY

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['category'] = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    await update.message.reply_text(
        "أدخل المبلغ (LBP):" if lang == 'ar' else "Enter amount (LBP):"
    )
    return EXPENSE_AMOUNT

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        keyboard = [["اليوم" if lang == 'ar' else "Today"], ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
        await update.message.reply_text(
            "تاريخ المصروف؟" if lang == 'ar' else "Expense date?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EXPENSE_DATE
    except ValueError:
        await update.message.reply_text(
            "أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number."
        )
        return EXPENSE_AMOUNT

async def expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text(
            "أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)"
        )
        return EXPENSE_DATE
    try:
        expense_date = date.today() if text in ["اليوم", "Today"] else datetime.strptime(text, "%Y-%m-%d").date()
        expense = farm_core.add_expense(
            farmer_id=farmer['id'],
            expense_date=expense_date,
            category=context.user_data['category'],
            amount=context.user_data['amount'],
            crop_id=context.user_data['crop_id']
        )
        if expense:
            await update.message.reply_text(
                "تم تسجيل المصروف! ✅" if lang == 'ar' else "Expense recorded! ✅",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                "خطأ في تسجيل المصروف." if lang == 'ar' else "Error recording expense."
            )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format."
        )
        return EXPENSE_DATE

# Record delivery for stored harvests
async def record_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return ConversationHandler.END
    lang = farmer['language']
    harvests = farm_core.get_stored_harvests(farmer['id'])
    if not harvests:
        await update.message.reply_text(
            "لا توجد حصادات مخزنة." if lang == 'ar' else "No stored harvests found."
        )
        return ConversationHandler.END
    keyboard = [[f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})"] for h in harvests]
    await update.message.reply_text(
        "اختر الحصاد للتسليم:" if lang == 'ar' else "Choose harvest to deliver:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DELIVERY_COLLECTOR

async def delivery_stored_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    harvests = farm_core.get_stored_harvests(farmer['id'])
    harvest = next((h for h in harvests if f"{h['crops']['name']} ({h['quantity']} kg, {h['harvest_date']})" == text), None)
    if not harvest:
        await update.message.reply_text(
            "الحصاد غير موجود." if lang == 'ar' else "Harvest not found."
        )
        return ConversationHandler.END
    context.user_data['harvest_id'] = harvest['id']
    await update.message.reply_text(
        "اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)"
    )
    return DELIVERY_COLLECTOR

# Market prices
async def market_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    prices = farm_core.get_market_prices()
    if not prices:
        await update.message.reply_text(
            "لا توجد أسعار سوق حاليًا." if lang == 'ar' else "No market prices available."
        )
        return
    message = "📈 أسعار السوق:\n\n" if lang == 'ar' else "📈 Market Prices:\n\n"
    for price in prices:
        message += f"• {price['crop_name']}: {price['price_per_kg']} LBP/kg ({price['price_date']})\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# Weekly summary
async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    summary = farm_core.get_weekly_summary(farmer['id'])
    message = "📊 ملخص الأسبوع:\n\n" if lang == 'ar' else "📊 Weekly Summary:\n\n"
    message += f"إجمالي الحصاد: {summary['total_harvest']} kg\n" if lang == 'ar' else f"Total Harvest: {summary['total_harvest']} kg\n"
    message += f"إجمالي المصاريف: {summary['total_expenses']} LBP\n" if lang == 'ar' else f"Total Expenses: {summary['total_expenses']} LBP\n"
    message += f"المدفوعات المعلقة: {summary['total_pending']} LBP\n" if lang == 'ar' else f"Pending Payments: {summary['total_pending']} LBP\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# My crops
async def my_crops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text(
            "ليس لديك محاصيل." if lang == 'ar' else "No crops found."
        )
        return
    message = "🌾 محاصيلك:\n\n" if lang == 'ar' else "🌾 Your Crops:\n\n"
    for crop in crops:
        message += f"• {crop['name']} (مزروع: {crop['planting_date']})\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# My account
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text(
            "يجب إنشاء حساب أولاً. اكتب /start" if farmer else "Create an account first. Use /start"
        )
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    help_text = (
        "❓ مساعدة:\n\n"
        "• 🇱🇧 حسابي: عرض معلومات الحساب\n"
        "• ➕ أضف محصول: إضافة محصول جديد\n"
        "• 🌾 محاصيلي: عرض جميع المحاصيل\n"
        "• 🧾 سجل الحصاد: تسجيل حصاد جديد\n"
        "• 🚚 سجل التسليم: تسليم المحصول إلى الجامع\n"
        "• 💵 المدفوعات المعلقة: عرض المدفوعات المتوقعة\n"
        "• 🗓️ التسميد/علاج: إضافة علاج أو تسميد\n"
        "• 💸 مصاريف: تسجيل المصاريف\n"
        "• 📈 الأسعار بالسوق: عرض أسعار السوق\n"
        "• 📊 ملخص الاسبوع: عرض ملخص الأسبوع\n"
    ) if lang == 'ar' else (
        "❓ Help:\n\n"
        "• 🇱🇧 My Account: View account information\n"
        "• ➕ Add Crop: Add a new crop\n"
        "• 🌾 My Crops: View all crops\n"
        "• 🧾 Record Harvest: Record a new harvest\n"
        "• 🚚 Record Delivery: Deliver to collector\n"
        "• 💵 Pending Payments: View expected payments\n"
        "• 🗓️ Fertilize & Treat: Add treatment or fertilization\n"
        "• 💸 Expenses: Record expenses\n"
        "• 📈 Market Prices: View market prices\n"
        "• 📊 Weekly Summary: View weekly summary\n"
    )
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    await update.message.reply_text(
        "تم الإلغاء." if lang == 'ar' else "Cancelled.",
        reply_markup=get_main_keyboard(lang)
    )
    return ConversationHandler.END

# Handle main menu selections
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    if text in ["🇱🇧 حسابي", "🇱🇧 My Account"]:
        await my_account(update, context)
    elif text in ["🌾 محاصيلي", "🌾 My Crops"]:
        await my_crops(update, context)
    elif text in ["📈 الأسعار بالسوق", "📈 Market Prices"]:
        await market_prices(update, context)
    elif text in ["📊 ملخص الاسبوع", "📊 Weekly Summary"]:
        await weekly_summary(update, context)
    elif text in ["❓مساعدة", "❓Help"]:
        await help_command(update, context)

def main() -> None:
    application = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    # Registration conversation handler
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, language_selection)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_village)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add crop conversation handler
    crop_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(➕ أضف محصول|Add Crop)$"), add_crop)],
        states={
            CROP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_name)],
            CROP_PLANTING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, crop_planting_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Record harvest conversation handler
    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|Record Harvest)$"), record_harvest)],
        states={
            HARVEST_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_crop)],
            HARVEST_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_date)],
            HARVEST_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_quantity)],
            HARVEST_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, harvest_delivery)],
            DELIVERY_COLLECTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_collector)],
            DELIVERY_MARKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_market)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Treatment conversation handler
    treatment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🗓️ التسميد/علاج|Fertilize & Treat)$"), add_treatment)],
        states={
            TREATMENT_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_crop)],
            TREATMENT_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_product)],
            TREATMENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_date)],
            TREATMENT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_cost)],
            TREATMENT_NEXT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, treatment_next_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Expense conversation handler
    expense_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|Expenses)$"), add_expense)],
        states={
            EXPENSE_CROP: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)],
            EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)],
            EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Payment conversation handler
    payment_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💵 المدفوعات المعلقة|Pending Payments)$"), pending_payments)],
        states={
            PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add handlers
    application.add_handler(reg_conv_handler)
    application.add_handler(crop_conv_handler)
    application.add_handler(harvest_conv_handler)
    application.add_handler(treatment_conv_handler)
    application.add_handler(expense_conv_handler)
    application.add_handler(payment_conv_handler)
    application.add_handler(MessageHandler(filters.Regex("^(🚚 سجل التسليم|Record Delivery)$"), record_delivery))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(mark_paid_callback))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() """
