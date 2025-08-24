import os
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, Response
import uvicorn
import httpx

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import farmcore
from keyboards import get_main_keyboard
from onboarding import start, language_selection, get_name, get_phone, get_village, ONBOARD_STATES
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

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Helper command handlers
# -------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if farm_core is None:
        logger.error("FarmCore is not initialized in cancel function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return ConversationHandler.END
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    if update.message:
        await update.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    elif update.callback_query:
        await update.callback_query.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if farm_core is None:
        logger.error("FarmCore is not initialized in help_command function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return
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
    if update.message:
        await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))
    else:
        await update.callback_query.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if farm_core is None:
        logger.error("FarmCore is not initialized in my_account function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    if farm_core is None:
        logger.error("FarmCore is not initialized in handle_message function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return
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
        await add_expense(update, context)
    elif text in ["💵 المدفوعات المعلقة", "💵 Pending Payments"]:
        await pending_payments(update, context)
    elif text in ["🗓️ التسميد/علاج", "🗓️ Fertilize & Treat"]:
        await add_treatment(update, context)
    else:
        await update.message.reply_text("أمر غير معروف. استخدم /help" if lang == 'ar' else "Unknown command. Use /help", reply_markup=get_main_keyboard(lang))

# -------------------------
# Error handler
# -------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        lang = context.user_data.get('language', 'ar')
        await update.message.reply_text(
            "حدث خطأ، يرجى المحاولة لاحقًا." if lang == 'ar' else
            "An error occurred, please try again later."
        )

# -------------------------
# Handlers registration
# -------------------------
def register_handlers(application: Application):
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

    add_crop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_crop_start_callback, pattern=r"^crop_add$")],
        states={
            CROP_STATES['CROP_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_name_handler)],
            CROP_STATES['CROP_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_date_handler)],
            CROP_STATES['CROP_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$")],
        allow_reentry=True,
    )

    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|🧾 Record Harvest)$"), record_harvest)],
        states={
            HARVEST_STATES['HARVEST_CROP']: [
                CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"),
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

    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|💸 Expenses)$"), add_expense)],
        states={
            EXPENSE_STATES['EXPENSE_CROP']: [
                CallbackQueryHandler(expense_crop, pattern=r"^expense_crop:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)
            ],
            EXPENSE_STATES['EXPENSE_CATEGORY']: [
                CallbackQueryHandler(expense_category, pattern=r"^expense_cat:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)
            ],
            EXPENSE_STATES['EXPENSE_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_STATES['EXPENSE_DATE']: [
                CallbackQueryHandler(expense_date, pattern=r"^expense_date:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_")],
        states={
            PAYMENT_STATES['PAYMENT_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

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

    application.add_handler(reg_conv_handler)
    application.add_handler(add_crop_conv)
    application.add_handler(harvest_conv_handler)
    application.add_handler(edit_conv)
    application.add_handler(expense_conv)
    application.add_handler(payment_conv)
    application.add_handler(treatment_conv)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^crop_page:"))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^prefcrop:"))
    application.add_handler(CallbackQueryHandler(crop_manage_callback, pattern=r"^crop_manage:"))
    application.add_handler(CallbackQueryHandler(crop_delete_callback, pattern=r"^crop_delete:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete:"))
    application.add_handler(CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    application.add_handler(CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"))
    application.add_handler(CallbackQueryHandler(harvest_date_callback, pattern=r"^harvest_date:"))
    application.add_handler(CallbackQueryHandler(harvest_delivery_callback, pattern=r"^harvest_delivery:"))
    application.add_handler(CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:"))
    application.add_handler(CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$"))

    application.add_handler(CallbackQueryHandler(create_pending_callback, pattern=r"^create_pending:"))
    application.add_handler(CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_"))

    application.add_handler(CallbackQueryHandler(treatment_date_callback, pattern=r"^treatment_date:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_next:"))

    # Add error handler
    application.add_error_handler(error_handler)

# -------------------------
# FastAPI app + Telegram Application
# -------------------------
app = FastAPI()

telegram_app: Optional[Application] = None

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/")
async def webhook(request: Request):
    global telegram_app
    if telegram_app is None:
        logger.warning("Received webhook while telegram_app is not ready.")
        return Response(status_code=503, content="Telegram app not ready")

    try:
        data = await request.json()
    except Exception:
        logger.exception("Failed to parse JSON from request")
        return Response(status_code=400, content="Invalid JSON")

    try:
        update = Update.de_json(data, telegram_app.bot)
    except Exception:
        logger.exception("Failed to build Update from JSON")
        return Response(status_code=400, content="Invalid update")

    try:
        await telegram_app.update_queue.put(update)
    except Exception:
        logger.exception("Failed to enqueue update")
        return Response(status_code=500, content="Failed to process update")

    return {"ok": True}

# -------------------------
# Lifecycle: create/start/stop telegram_app
# -------------------------
@app.on_event("startup")
async def on_startup():
    global telegram_app

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_KEY environment variables")
        raise RuntimeError("Supabase configuration missing")

    logger.info("Initializing FarmCore...")
    try:
       farmcore.init_farm_core(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)
    if farmcore.farm_core is None:
          logger.error("FarmCore initialization failed: farmcore.farm_core is None")
    raise RuntimeError("Failed to initialize FarmCore")
        logger.info("FarmCore initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize FarmCore: {str(e)}")
        raise

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN environment variable")
        raise RuntimeError("Telegram bot token is required")

    logger.info("Creating Telegram Application...")
    try:
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to create Telegram Application: {str(e)}")
        raise

    logger.info("Registering handlers...")
    register_handlers(telegram_app)

    logger.info("Initializing Telegram Application...")
    await telegram_app.initialize()

    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.error("Missing WEBHOOK_URL environment variable")
        raise RuntimeError("Webhook URL is required")

    logger.info(f"Setting Telegram webhook to {WEBHOOK_URL}...")
    async with httpx.AsyncClient() as client:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                    json={"url": WEBHOOK_URL}
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram webhook set successfully")
                    break
                else:
                    logger.error(f"Failed to set webhook (attempt {attempt + 1}): {result}")
                    if attempt == max_retries - 1:
                        raise RuntimeError("Failed to set Telegram webhook after retries")
            except Exception as e:
                logger.error(f"Error setting Telegram webhook (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Webhook setup failed: {str(e)}")
            await asyncio.sleep(1)

    logger.info("Starting Telegram Application...")
    await telegram_app.start()
    logger.info("Telegram Application started.")

@app.on_event("shutdown")
async def on_shutdown():
    global telegram_app
    if telegram_app is None:
        return

    logger.info("Stopping Telegram Application...")
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
    except Exception:
        logger.exception("Error during Telegram application shutdown")
    finally:
        telegram_app = None
    logger.info("Telegram Application stopped.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")












'''import os
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, Response
import uvicorn
import httpx

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# core_singleton holds a module-level farm_core that will be initialized at startup
import core_singleton

from keyboards import get_main_keyboard
from onboarding import start, language_selection, get_name, get_phone, get_village, ONBOARD_STATES
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

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Helper command handlers
# -------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
    lang = farmer['language'] if farmer else 'ar'
    if update.message:
        await update.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    elif update.callback_query:
        await update.callback_query.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
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
    if update.message:
        await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))
    else:
        await update.callback_query.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if core_singleton.farm_core is None:
        logger.error("FarmCore is not initialized in my_account function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    if core_singleton.farm_core is None:
        logger.error("FarmCore is not initialized in handle_message function")
        await update.message.reply_text(
            "خطأ في الخادم، يرجى المحاولة لاحقًا." if context.user_data.get('language', 'ar') == 'ar' else
            "Server error, please try again later."
        )
        return
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id)
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
        await add_expense(update, context)
    elif text in ["💵 المدفوعات المعلقة", "💵 Pending Payments"]:
        await pending_payments(update, context)
    elif text in ["🗓️ التسميد/علاج", "🗓️ Fertilize & Treat"]:
        await add_treatment(update, context)
    else:
        await update.message.reply_text("أمر غير معروف. استخدم /help" if lang == 'ar' else "Unknown command. Use /help", reply_markup=get_main_keyboard(lang))

# -------------------------
# Error handler
# -------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        lang = context.user_data.get('language', 'ar')
        await update.message.reply_text(
            "حدث خطأ، يرجى المحاولة لاحقًا." if lang == 'ar' else
            "An error occurred, please try again later."
        )

# -------------------------
# Handlers registration
# -------------------------
def register_handlers(application: Application):
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

    add_crop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_crop_start_callback, pattern=r"^crop_add$")],
        states={
            CROP_STATES['CROP_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_name_handler)],
            CROP_STATES['CROP_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_date_handler)],
            CROP_STATES['CROP_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$")],
        allow_reentry=True,
    )

    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|🧾 Record Harvest)$"), record_harvest)],
        states={
            HARVEST_STATES['HARVEST_CROP']: [
                CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"),
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

    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|💸 Expenses)$"), add_expense)],
        states={
            EXPENSE_STATES['EXPENSE_CROP']: [
                CallbackQueryHandler(expense_crop, pattern=r"^expense_crop:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)
            ],
            EXPENSE_STATES['EXPENSE_CATEGORY']: [
                CallbackQueryHandler(expense_category, pattern=r"^expense_cat:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)
            ],
            EXPENSE_STATES['EXPENSE_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_STATES['EXPENSE_DATE']: [
                CallbackQueryHandler(expense_date, pattern=r"^expense_date:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_")],
        states={
            PAYMENT_STATES['PAYMENT_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

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

    application.add_handler(reg_conv_handler)
    application.add_handler(add_crop_conv)
    application.add_handler(harvest_conv_handler)
    application.add_handler(edit_conv)
    application.add_handler(expense_conv)
    application.add_handler(payment_conv)
    application.add_handler(treatment_conv)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^crop_page:"))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^prefcrop:"))
    application.add_handler(CallbackQueryHandler(crop_manage_callback, pattern=r"^crop_manage:"))
    application.add_handler(CallbackQueryHandler(crop_delete_callback, pattern=r"^crop_delete:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete:"))
    application.add_handler(CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    application.add_handler(CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"))
    application.add_handler(CallbackQueryHandler(harvest_date_callback, pattern=r"^harvest_date:"))
    application.add_handler(CallbackQueryHandler(harvest_delivery_callback, pattern=r"^harvest_delivery:"))
    application.add_handler(CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:"))
    application.add_handler(CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$"))

    application.add_handler(CallbackQueryHandler(create_pending_callback, pattern=r"^create_pending:"))
    application.add_handler(CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_"))

    application.add_handler(CallbackQueryHandler(treatment_date_callback, pattern=r"^treatment_date:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_next:"))

    # Add error handler
    application.add_error_handler(error_handler)

# -------------------------
# FastAPI app + Telegram Application
# -------------------------
app = FastAPI()

telegram_app: Optional[Application] = None

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/")
async def webhook(request: Request):
    global telegram_app
    if telegram_app is None:
        logger.warning("Received webhook while telegram_app is not ready.")
        return Response(status_code=503, content="Telegram app not ready")

    try:
        data = await request.json()
    except Exception:
        logger.exception("Failed to parse JSON from request")
        return Response(status_code=400, content="Invalid JSON")

    try:
        update = Update.de_json(data, telegram_app.bot)
    except Exception:
        logger.exception("Failed to build Update from JSON")
        return Response(status_code=400, content="Invalid update")

    try:
        await telegram_app.update_queue.put(update)
    except Exception:
        logger.exception("Failed to enqueue update")
        return Response(status_code=500, content="Failed to process update")

    return {"ok": True}

# -------------------------
# Lifecycle: create/start/stop telegram_app
# -------------------------
@app.on_event("startup")
async def on_startup():
    global telegram_app

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_KEY environment variables")
        raise RuntimeError("Supabase configuration missing")

    logger.info("Initializing FarmCore...")
    try:
        core_singleton.init_farm_core(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)
        if core_singleton.farm_core is None:
            logger.error("FarmCore initialization failed: farm_core is None")
            raise RuntimeError("Failed to initialize FarmCore")
        logger.info("FarmCore initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize FarmCore: {str(e)}")
        raise

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN environment variable")
        raise RuntimeError("Telegram bot token is required")

    logger.info("Creating Telegram Application...")
    try:
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to create Telegram Application: {str(e)}")
        raise

    logger.info("Registering handlers...")
    register_handlers(telegram_app)

    logger.info("Initializing Telegram Application...")
    await telegram_app.initialize()

    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.error("Missing WEBHOOK_URL environment variable")
        raise RuntimeError("Webhook URL is required")

    logger.info(f"Setting Telegram webhook to {WEBHOOK_URL}...")
    async with httpx.AsyncClient() as client:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                    json={"url": WEBHOOK_URL}
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram webhook set successfully")
                    break
                else:
                    logger.error(f"Failed to set webhook (attempt {attempt + 1}): {result}")
                    if attempt == max_retries - 1:
                        raise RuntimeError("Failed to set Telegram webhook after retries")
            except Exception as e:
                logger.error(f"Error setting Telegram webhook (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Webhook setup failed: {str(e)}")
            await asyncio.sleep(1)

    logger.info("Starting Telegram Application...")
    await telegram_app.start()
    logger.info("Telegram Application started.")

@app.on_event("shutdown")
async def on_shutdown():
    global telegram_app
    if telegram_app is None:
        return

    logger.info("Stopping Telegram Application...")
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
    except Exception:
        logger.exception("Error during Telegram application shutdown")
    finally:
        telegram_app = None
    logger.info("Telegram Application stopped.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
'''








'''import os
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, Request, Response
import uvicorn
import httpx

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)

# core_singleton holds a module-level farm_core that will be initialized at startup
import core_singleton

from keyboards import get_main_keyboard
from onboarding import start, language_selection, get_name, get_phone, get_village, ONBOARD_STATES
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

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Helper command handlers
# -------------------------
async def cancel(update: Update, context) -> int:
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
    lang = farmer['language'] if farmer else 'ar'
    if update.message:
        await update.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    elif update.callback_query:
        await update.callback_query.message.reply_text("تم الإلغاء." if lang == 'ar' else "Cancelled.", reply_markup=get_main_keyboard(lang))
    return ConversationHandler.END

async def help_command(update: Update, context) -> None:
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
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
    if update.message:
        await update.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))
    else:
        await update.callback_query.message.reply_text(help_text, reply_markup=get_main_keyboard(lang))

async def my_account(update: Update, context) -> None:
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    await update.message.reply_text(
        f"الاسم: {farmer['name']}\nالقرية: {farmer['village']}\nالهاتف: {farmer['phone']}" if lang == 'ar' else
        f"Name: {farmer['name']}\nVillage: {farmer['village']}\nPhone: {farmer['phone']}",
        reply_markup=get_main_keyboard(lang)
    )

async def handle_message(update: Update, context) -> None:
    text = update.message.text or ""
    farmer = core_singleton.farm_core.get_farmer(update.effective_user.id) if core_singleton.farm_core else None
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
        await add_expense(update, context)
    elif text in ["💵 المدفوعات المعلقة", "💵 Pending Payments"]:
        await pending_payments(update, context)
    elif text in ["🗓️ التسميد/علاج", "🗓️ Fertilize & Treat"]:
        await add_treatment(update, context)
    else:
        await update.message.reply_text("أمر غير معروف. استخدم /help" if lang == 'ar' else "Unknown command. Use /help", reply_markup=get_main_keyboard(lang))

# -------------------------
# Handlers registration
# -------------------------
def register_handlers(application: Application):
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

    add_crop_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_crop_start_callback, pattern=r"^crop_add$")],
        states={
            CROP_STATES['CROP_NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_name_handler)],
            CROP_STATES['CROP_PLANTING_DATE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_date_handler)],
            CROP_STATES['CROP_NOTES']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_crop_notes_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$")],
        allow_reentry=True,
    )

    harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🧾 سجل الحصاد|🧾 Record Harvest)$"), record_harvest)],
        states={
            HARVEST_STATES['HARVEST_CROP']: [
                CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"),
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

    expense_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💸 مصاريف|💸 Expenses)$"), add_expense)],
        states={
            EXPENSE_STATES['EXPENSE_CROP']: [
                CallbackQueryHandler(expense_crop, pattern=r"^expense_crop:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_crop)
            ],
            EXPENSE_STATES['EXPENSE_CATEGORY']: [
                CallbackQueryHandler(expense_category, pattern=r"^expense_cat:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_category)
            ],
            EXPENSE_STATES['EXPENSE_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amount)],
            EXPENSE_STATES['EXPENSE_DATE']: [
                CallbackQueryHandler(expense_date, pattern=r"^expense_date:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, expense_date)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_")],
        states={
            PAYMENT_STATES['PAYMENT_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_amount)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

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

    application.add_handler(reg_conv_handler)
    application.add_handler(add_crop_conv)
    application.add_handler(harvest_conv_handler)
    application.add_handler(edit_conv)
    application.add_handler(expense_conv)
    application.add_handler(payment_conv)
    application.add_handler(treatment_conv)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^crop_page:"))
    application.add_handler(CallbackQueryHandler(crops_callback_handler, pattern=r"^prefcrop:"))
    application.add_handler(CallbackQueryHandler(crop_manage_callback, pattern=r"^crop_manage:"))
    application.add_handler(CallbackQueryHandler(crop_delete_callback, pattern=r"^crop_delete:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete:"))
    application.add_handler(CallbackQueryHandler(crop_edit_entry_callback, pattern=r"^crop_edit:"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    application.add_handler(CallbackQueryHandler(harvest_select_callback, pattern=r"^harvest_select:"))
    application.add_handler(CallbackQueryHandler(harvest_date_callback, pattern=r"^harvest_date:"))
    application.add_handler(CallbackQueryHandler(harvest_delivery_callback, pattern=r"^harvest_delivery:"))
    application.add_handler(CallbackQueryHandler(harvest_skip_callback, pattern=r"^harvest_skip:"))
    application.add_handler(CallbackQueryHandler(addcrop_skip_notes_callback, pattern=r"^addcrop_skip_notes$"))

    application.add_handler(CallbackQueryHandler(create_pending_callback, pattern=r"^create_pending:"))
    application.add_handler(CallbackQueryHandler(mark_paid_callback, pattern=r"^paid_"))

    application.add_handler(CallbackQueryHandler(treatment_date_callback, pattern=r"^treatment_date:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_skip:"))
    application.add_handler(CallbackQueryHandler(treatment_skip_callback, pattern=r"^treatment_next:"))

# -------------------------
# FastAPI app + Telegram Application
# -------------------------
app = FastAPI()

telegram_app: Optional[Application] = None

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/")
async def webhook(request: Request):
    global telegram_app
    if telegram_app is None:
        logger.warning("Received webhook while telegram_app is not ready.")
        return Response(status_code=503, content="Telegram app not ready")

    try:
        data = await request.json()
    except Exception:
        logger.exception("Failed to parse JSON from request")
        return Response(status_code=400, content="Invalid JSON")

    try:
        update = Update.de_json(data, telegram_app.bot)
    except Exception:
        logger.exception("Failed to build Update from JSON")
        return Response(status_code=400, content="Invalid update")

    try:
        await telegram_app.update_queue.put(update)
    except Exception:
        logger.exception("Failed to enqueue update")
        return Response(status_code=500, content="Failed to process update")

    return {"ok": True}

# -------------------------
# Lifecycle: create/start/stop telegram_app
# -------------------------
@app.on_event("startup")
async def on_startup():
    global telegram_app

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Missing SUPABASE_URL or SUPABASE_KEY environment variables")
        raise RuntimeError("Supabase configuration missing")

    logger.info("Initializing FarmCore...")
    core_singleton.init_farm_core(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)
    logger.info("FarmCore initialized.")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN environment variable")
        raise RuntimeError("Telegram bot token is required")

    logger.info("Creating Telegram Application...")
    try:
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    except Exception as e:
        logger.exception(f"Failed to create Telegram Application: {str(e)}")
        raise

    logger.info("Registering handlers...")
    register_handlers(telegram_app)

    logger.info("Initializing Telegram Application...")
    await telegram_app.initialize()

    # Set webhook with retry
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.error("Missing WEBHOOK_URL environment variable")
        raise RuntimeError("Webhook URL is required")

    logger.info(f"Setting Telegram webhook to {WEBHOOK_URL}...")
    async with httpx.AsyncClient() as client:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                    json={"url": WEBHOOK_URL}
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram webhook set successfully")
                    break
                else:
                    logger.error(f"Failed to set webhook (attempt {attempt + 1}): {result}")
                    if attempt == max_retries - 1:
                        raise RuntimeError("Failed to set Telegram webhook after retries")
            except Exception as e:
                logger.exception(f"Error setting Telegram webhook (attempt {attempt + 1})")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Webhook setup failed: {str(e)}")
            await asyncio.sleep(1)  # Wait before retrying

    logger.info("Starting Telegram Application...")
    await telegram_app.start()
    logger.info("Telegram Application started.")

@app.on_event("shutdown")
async def on_shutdown():
    global telegram_app
    if telegram_app is None:
        return

    logger.info("Stopping Telegram Application...")
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
    except Exception:
        logger.exception("Error during Telegram application shutdown")
    finally:
        telegram_app = None
    logger.info("Telegram Application stopped.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

'''



