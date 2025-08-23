# aboutmoney.py
from venv import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date, timedelta
from core_singleton import farm_core
from keyboards import get_main_keyboard

EXPENSE_STATES = {
    'EXPENSE_CROP': 0,
    'EXPENSE_CATEGORY': 1,
    'EXPENSE_AMOUNT': 2,
    'EXPENSE_DATE': 3
}

PAYMENT_STATES = {
    'PAYMENT_AMOUNT': 0
}

# ----------------------
# Expenses (inline-first)
# ----------------------
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: show inline crop choices + 'No Crop'."""
    # message entry or callback entry:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send = query.message.reply_text
        uid = query.from_user.id
    else:
        send = update.message.reply_text
        uid = update.effective_user.id

    farmer = farm_core.get_farmer(uid)
    if not farmer:
        await send("Create an account first. Use /start")
        return ConversationHandler.END
    lang = farmer['language']

    crops = farm_core.get_farmer_crops(farmer['id'])
    kb = []
    kb.append([InlineKeyboardButton("بدون محصول" if lang == 'ar' else "No Crop", callback_data="expense_crop:None")])
    # show up to 8 crops inline (pagination could be added later)
    for c in crops:
        kb.append([InlineKeyboardButton(c['name'], callback_data=f"expense_crop:{c['id']}")])

    await send("اختر المحصول (اختياري):" if lang == 'ar' else "Choose crop (optional):", reply_markup=InlineKeyboardMarkup(kb))
    return EXPENSE_STATES['EXPENSE_CROP']

async def expense_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle crop chosen via inline button or typed (fallback)."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        _, val = data.split(":", 1)
        crop_id = None if val in (None, "None", "None") else val
        context.user_data['crop_id'] = crop_id
        farmer = farm_core.get_farmer(query.from_user.id)
        lang = farmer['language']
        # show category inline
        cats = [
            InlineKeyboardButton("بذور" if lang == 'ar' else "Seeds", callback_data="expense_cat:Seeds"),
            InlineKeyboardButton("سماد" if lang == 'ar' else "Fertilizer", callback_data="expense_cat:Fertilizer"),
            InlineKeyboardButton("نقل" if lang == 'ar' else "Transport", callback_data="expense_cat:Transport"),
            InlineKeyboardButton("أخرى" if lang == 'ar' else "Other", callback_data="expense_cat:Other"),
        ]
        await query.message.reply_text("اختر الفئة:" if lang == 'ar' else "Choose category:", reply_markup=InlineKeyboardMarkup([cats[:2], cats[2:]]))
        return EXPENSE_STATES['EXPENSE_CATEGORY']
    else:
        # typed fallback: match crop name to farmer crops
        text = update.message.text
        farmer = farm_core.get_farmer(update.effective_user.id)
        crops = farm_core.get_farmer_crops(farmer['id'])
        crop = next((c for c in crops if c['name'] == text), None)
        if crop:
            context.user_data['crop_id'] = crop['id']
        else:
            context.user_data['crop_id'] = None
        # now proceed to category step (typed)
        await update.message.reply_text("اختر الفئة أو اكتبها:" if farmer['language']=='ar' else "Choose category or type it:")
        return EXPENSE_STATES['EXPENSE_CATEGORY']

async def expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        _, cat = query.data.split(":", 1)
        context.user_data['category'] = cat
        farmer = farm_core.get_farmer(query.from_user.id)
        lang = farmer['language']
        await query.message.reply_text("أدخل المبلغ (LBP):" if lang == 'ar' else "Enter amount (LBP):")
        return EXPENSE_STATES['EXPENSE_AMOUNT']
    else:
        # typed category
        context.user_data['category'] = update.message.text
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language']
        await update.message.reply_text("أدخل المبلغ (LBP):" if lang == 'ar' else "Enter amount (LBP):")
        return EXPENSE_STATES['EXPENSE_AMOUNT']

async def expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        # Offer Today or pick date inline
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اليوم" if lang=='ar' else "Today", callback_data="expense_date:today"),
             InlineKeyboardButton("📅 اختر تاريخًا" if lang=='ar' else "📅 Pick Date", callback_data="expense_date:pick")]
        ])
        await update.message.reply_text("تاريخ المصروف؟" if lang == 'ar' else "Expense date?", reply_markup=kb)
        return EXPENSE_STATES['EXPENSE_DATE']
    except ValueError:
        await update.message.reply_text("أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number.")
        return EXPENSE_STATES['EXPENSE_AMOUNT']

async def expense_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # handles both inline callbacks and typed dates
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        farmer = farm_core.get_farmer(query.from_user.id)
        lang = farmer['language']
        if data.endswith(":today"):
            expense_date_val = date.today()
        elif data.endswith(":pick"):
            await query.message.reply_text("أدخل التاريخ (YYYY-MM-DD)" if lang=='ar' else "Enter date (YYYY-MM-DD)")
            return EXPENSE_STATES['EXPENSE_DATE']
        else:
            await query.message.reply_text("خيار غير معروف." if lang=='ar' else "Unknown option.")
            return EXPENSE_STATES['EXPENSE_DATE']
    else:
        # typed date handling
        text = update.message.text.strip()
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language']
        try:
            if text in ["اليوم", "Today"]:
                expense_date_val = date.today()
            else:
                expense_date_val = datetime.strptime(text, "%Y-%m-%d").date()
        except Exception:
            await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang=='ar' else "Invalid date format. Use YYYY-MM-DD")
            return EXPENSE_STATES['EXPENSE_DATE']

    # Save expense
    farmer = farm_core.get_farmer(update.effective_user.id if update.message else update.callback_query.from_user.id)
    expense = farm_core.add_expense(
        farmer_id=farmer['id'],
        expense_date=expense_date_val,
        category=context.user_data.get('category'),
        amount=context.user_data.get('amount'),
        crop_id=context.user_data.get('crop_id')
    )
    if expense:
        if update.callback_query:
            await update.callback_query.message.reply_text("تم تسجيل المصروف! ✅" if farmer['language']=='ar' else "Expense recorded! ✅", reply_markup=get_main_keyboard(farmer['language']))
        else:
            await update.message.reply_text("تم تسجيل المصروف! ✅" if farmer['language']=='ar' else "Expense recorded! ✅", reply_markup=get_main_keyboard(farmer['language']))
    else:
        if update.callback_query:
            await update.callback_query.message.reply_text("خطأ في تسجيل المصروف." if farmer['language']=='ar' else "Error recording expense.")
        else:
            await update.message.reply_text("خطأ في تسجيل المصروف." if farmer['language']=='ar' else "Error recording expense.")
    # cleanup
    for k in ("category", "amount", "crop_id"):
        context.user_data.pop(k, None)
    return ConversationHandler.END

# ----------------------
# Pending payments / Mark Paid
# ----------------------
async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show payments that are pending and any delivered harvests without delivery/payment."""
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return ConversationHandler.END
    lang = farmer['language']

    # 1) payments with status 'pending' (joined to deliveries/harvests)
    payments = farm_core.get_pending_payments(farmer['id'])

    if not payments:
        no_pay_msg = "لا توجد مدفوعات معلقة." if lang == 'ar' else "No pending payments."
        await update.message.reply_text(no_pay_msg, reply_markup=get_main_keyboard(lang))
    else:
        header = "💰 المدفوعات المعلقة:\n\n" if lang == 'ar' else "💰 Pending Payments:\n\n"
        # show each payment as its own message with inline Mark Paid button
        for payment in payments:
            # try safe navigation through nested join
            try:
                delivery = payment.get('deliveries') or {}
                harvest = delivery.get('harvests') if isinstance(delivery, dict) else None
                crop = harvest.get('crops') if harvest else None
                crop_name = crop.get('name') if crop else "Unknown"
                qty = harvest.get('quantity') if harvest else "?"
                expected_date = payment.get('expected_date', 'N/A')
                amount = payment.get('expected_amount', 'N/A')
            except Exception:
                crop_name = "Unknown"
                qty = "?"
                expected_date = payment.get('expected_date', 'N/A')
                amount = payment.get('expected_amount', 'N/A')

            text = f"• {crop_name}: {qty} kg - {amount} LBP\n  Expected: {expected_date}" if lang!='ar' else f"• {crop_name}: {qty} kg - {amount} LBP\n  متوقع: {expected_date}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("تسجيل الدفع" if lang == 'ar' else "Mark Paid", callback_data=f"paid_{payment['id']}")]
            ])
            await update.message.reply_text(text, reply_markup=kb)

    # 2) find delivered harvests that have no delivery row -> show as "delivered but no payment recorded"
    # (helpful for users who set harvest status to delivered but didn't run the delivery flow)
    delivered_resp = farm_core.supabase.table("harvests").select("*, crops!inner(*)").eq("status", "delivered").eq("crops.farmer_id", farmer['id']).execute()
    delivered = delivered_resp.data or []
    extra_count = 0
    for h in delivered:
        # check deliveries table for entries with this harvest id
        deliveries_resp = farm_core.supabase.table("deliveries").select("*").eq("harvest_id", h['id']).execute()
        deliveries = deliveries_resp.data or []
        if not deliveries:
            extra_count += 1
            crop_name = h.get('crops', {}).get('name', 'Unknown')
            qty = h.get('quantity', '?')
            harvest_date = h.get('harvest_date', '?')
            text = f"• {crop_name}: {qty} kg — delivered on {harvest_date}\n  (No payment/delivery recorded)" if lang != 'ar' else f"• {crop_name}: {qty} kg — تم الحصاد في {harvest_date}\n  (لم يتم تسجيل تسليم/دفع)"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("إنشاء مُنتظر" if lang=='ar' else "Create Pending", callback_data=f"create_pending:{h['id']}"),
                 InlineKeyboardButton("تسجيل الدفع" if lang=='ar' else "Mark Paid", callback_data=f"paid_direct:{h['id']}")]
            ])
            await update.message.reply_text(text, reply_markup=kb)

    if extra_count == 0 and not payments:
        # nothing to show
        await update.message.reply_text("لا توجد مدفوعات معلقة." if lang == 'ar' else "No pending payments.", reply_markup=get_main_keyboard(lang))
    return ConversationHandler.END

async def create_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create a delivery+payment for a harvest that was delivered but had no delivery recorded."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        _, harvest_id = data.split(":", 1)
    except Exception:
        await query.message.reply_text("Invalid selection." if lang != 'ar' else "اختيار غير صالح.")
        return ConversationHandler.END

    # call farm_core.record_delivery which will mark harvest as delivered and create a delivery + payment row
    delivery = farm_core.record_delivery(
        harvest_id=harvest_id,
        delivery_date=date.today(),
        collector_name=None,
        market=None
    )
    if delivery:
        await query.message.reply_text("تم إنشاء طلب الدفع المُعلق! ✅" if lang == 'ar' else "Pending payment entry created! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await query.message.reply_text("خطأ أثناء الإنشاء." if lang == 'ar' else "Error creating pending entry.")
    return ConversationHandler.END

# Mark Paid flow: two entry sources:
# - paid_{payment_id} (existing payment row)
# - paid_direct:{harvest_id} (delivered harvest without payment -> we'll create a payment record then mark paid)
async def mark_paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'

    # pattern: paid_<payment_id>  OR paid_direct:<harvest_id>
    if data.startswith("paid_"):
        payment_id = data.split("_", 1)[1]
        context.user_data['payment_id'] = payment_id
        context.user_data['payment_type'] = 'existing'
        await query.message.reply_text("أدخل المبلغ المدفوع (LBP):" if lang == 'ar' else "Enter amount paid (LBP):")
        return PAYMENT_STATES['PAYMENT_AMOUNT']
    if data.startswith("paid_direct:"):
        # create a payment row for the harvest first (we'll insert a payment with status 'pending' and then record amount)
        harvest_id = data.split(":", 1)[1]
        # create a delivery entry first (so payments can link to delivery) - minimal data
        delivery = farm_core.record_delivery(
            harvest_id=harvest_id,
            delivery_date=date.today(),
            collector_name=None,
            market=None
        )
        if not delivery:
            await query.message.reply_text("خطأ أثناء إنشاء الإدخال." if lang == 'ar' else "Error creating entry.")
            return ConversationHandler.END
        # find the payment created (assuming record_delivery inserted a payment row)
        # find payments where delivery_id == delivery['id'] and status == 'pending'
        resp = farm_core.supabase.table("payments").select("*").eq("delivery_id", delivery['id']).execute()
        payments = resp.data or []
        if not payments:
            # fallback: create a payment row manually
            pay_resp = farm_core.supabase.table("payments").insert({
                "delivery_id": delivery['id'],
                "expected_date": (date.today() + timedelta(days=7)).isoformat(),
                "status": "pending"
            }).execute()
            payments = pay_resp.data or []
        payment_id = payments[0]['id']
        context.user_data['payment_id'] = payment_id
        context.user_data['payment_type'] = 'existing'
        await query.message.reply_text("أدخل المبلغ المدفوع (LBP):" if lang == 'ar' else "Enter amount paid (LBP):")
        return PAYMENT_STATES['PAYMENT_AMOUNT']

    await query.message.reply_text("خيار غير معروف." if lang == 'ar' else "Unknown option.")
    return ConversationHandler.END

async def payment_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number.")
        return PAYMENT_STATES['PAYMENT_AMOUNT']

    payment_id = context.user_data.get('payment_id')
    if not payment_id:
        await update.message.reply_text("خطأ: لا يوجد معرف للدفع." if lang == 'ar' else "Error: no payment id.")
        return ConversationHandler.END

    # record payment using farm_core.record_payment (updates existing payment)
    payment = farm_core.record_payment(
        payment_id=payment_id,
        paid_amount=amount,
        paid_date=date.today()
    )
    if payment:
        await update.message.reply_text("تم تسجيل الدفع! ✅" if lang == 'ar' else "Payment recorded! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ في تسجيل الدفع." if lang == 'ar' else "Error recording payment.")
    # cleanup
    context.user_data.pop('payment_id', None)
    context.user_data.pop('payment_type', None)
    return ConversationHandler.END

# ----------------------
# Market prices
async def market_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    prices = farm_core.get_market_prices()
    if not prices:
        await update.message.reply_text("لا توجد أسعار سوق حاليًا." if lang == 'ar' else "No market prices available.")
        return
    message = "📈 أسعار السوق:\n\n" if lang == 'ar' else "📈 Market Prices:\n\n"
    for price in prices:
        message += f"• {price['crop_name']}: {price['price_per_kg']} LBP/kg ({price['price_date']})\n"
    await update.message.reply_text(message, reply_markup=get_main_keyboard(lang))

# aboutmoney.py - weekly_summary function
async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Robust weekly summary that tolerates missing fields / different nested shapes.
    Works with update.message or update.callback_query and always shows main keyboard.
    """
    # determine sender + reply function (support callback_query-based calls too)
    if getattr(update, "callback_query", None):
        query = update.callback_query
        await query.answer()
        send = query.message.reply_text
        uid = query.from_user.id
    else:
        send = update.message.reply_text
        uid = update.effective_user.id

    farmer = farm_core.get_farmer(uid)
    if not farmer:
        await send("Create an account first. Use /start")
        return

    lang = farmer.get("language", "ar")

    # fetch summary, fail gracefully
    try:
        summary = farm_core.get_weekly_summary(farmer['id'])
    except Exception as e:
        logger.error(f"Error fetching weekly summary: {e}")
        await send(
            ("حدث خطأ أثناء جلب الملخص. حاول مرة أخرى لاحقًا." if lang == 'ar'
             else "Failed to fetch summary. Please try again later."),
            reply_markup=get_main_keyboard(lang)
        )
        return

    if not isinstance(summary, dict):
        summary = {}

    # safe numeric conversion
    def _to_num(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    total_harvest = _to_num(summary.get("total_harvest", 0))
    total_expenses = _to_num(summary.get("total_expenses", 0))
    total_pending = _to_num(summary.get("total_pending", 0))

    # header lines
    if lang == 'ar':
        parts = [
            "📊 ملخص الأسبوع:\n",
            f"إجمالي الحصاد: {total_harvest:.2f} kg",
            f"إجمالي المصاريف: {int(total_expenses)} LBP",
            f"المدفوعات المعلقة: {int(total_pending)} LBP",
            "",
            "تفاصيل الحصاد:"
        ]
    else:
        parts = [
            "📊 Weekly Summary:\n",
            f"Total Harvest: {total_harvest:.2f} kg",
            f"Total Expenses: {int(total_expenses)} LBP",
            f"Pending Payments: {int(total_pending)} LBP",
            "",
            "Harvest details:"
        ]

    # --- harvests: tolerate many shapes ---
    harvests = summary.get("harvests") or []
    if not isinstance(harvests, list):
        harvests = [harvests] if harvests else []

    def _crop_name_from_h(h):
        # try common nesting patterns more robustly
        try:
            if isinstance(h, dict):
                # Handle nested crops structure (both dict and list formats)
                crops_data = h.get("crops")
                if isinstance(crops_data, dict):
                    return crops_data.get("name", "Unknown")
                elif isinstance(crops_data, list) and crops_data:
                    # If crops is a list, take the first item
                    first_crop = crops_data[0]
                    if isinstance(first_crop, dict):
                        return first_crop.get("name", "Unknown")
                # Try direct field access
                return h.get("crop_name", h.get("name", "Unknown"))
            return "Unknown"
        except Exception:
            return "Unknown"

    for h in harvests[:12]:
        try:
            crop_name = _crop_name_from_h(h)
            qty = h.get("quantity", "?")
            hd = h.get("harvest_date", "-")
            parts.append(f"• {crop_name}: {qty} kg — {hd}")
        except Exception:
            # skip any malformed item
            continue

    # --- expenses ---
    expenses = summary.get("expenses") or []
    if not isinstance(expenses, list):
        expenses = [expenses] if expenses else []

    if expenses:
        parts.append("")
        parts.append("المصروفات:" if lang == 'ar' else "Expenses:")

    for e in expenses[:12]:
        try:
            if not isinstance(e, dict):
                continue
            cat = e.get("category", "—")
            amt = e.get("amount", 0)
            ed = e.get("expense_date", "-")
            parts.append(f"• {cat}: {int(_to_num(amt))} LBP — {ed}")
        except Exception:
            continue

    # --- pending payments (if provided in the summary) ---
    pending = summary.get("pending_payments") or []
    if not isinstance(pending, list):
        pending = [pending] if pending else []

    if pending:
        parts.append("")
        parts.append("المدفوعات المفصلة:" if lang == 'ar' else "Pending payments details:")

    for p in pending[:12]:
        try:
            crop_name = "Unknown"
            qty = "?"
            exp_amount = None
            exp_date = None

            if isinstance(p, dict):
                # attempt to extract nested delivery -> harvests -> crops
                deliveries = p.get("deliveries") or {}
                if isinstance(deliveries, dict):
                    harvest = deliveries.get("harvests") or {}
                    if isinstance(harvest, dict):
                        crop_data = harvest.get("crops") or {}
                        if isinstance(crop_data, dict):
                            crop_name = crop_data.get("name", "Unknown")
                        qty = harvest.get("quantity", qty)
                crop_name = p.get("crop_name", crop_name)
                exp_amount = p.get("expected_amount")
                exp_date = p.get("expected_date")

            amt_disp = int(_to_num(exp_amount)) if exp_amount is not None else "N/A"
            date_disp = exp_date or "-"
            if lang == 'ar':
                parts.append(f"• {crop_name}: {qty} kg - {amt_disp} LBP — متوقع: {date_disp}")
            else:
                parts.append(f"• {crop_name}: {qty} kg - {amt_disp} LBP — Expected: {date_disp}")
        except Exception:
            continue

    # minimal-content fallback
    if len(parts) <= 6:
        parts.append("")
        parts.append("لا توجد بيانات كافية لهذا الأسبوع." if lang == 'ar' else "No substantial data for this week.")

    # send message (try to avoid exceeding Telegram size; trimmed above)
    message_text = "\n".join(parts)
    try:
        await send(message_text, reply_markup=get_main_keyboard(lang))
    except Exception as e:
        logger.error(f"Error sending weekly summary: {e}")
        # last-resort short summary
        short = (
            f"📊 {'ملخص الأسبوع' if lang=='ar' else 'Weekly Summary'}\n"
            f"{'إجمالي الحصاد' if lang=='ar' else 'Total Harvest'}: {total_harvest:.2f} kg\n"
            f"{'إجمالي المصاريف' if lang=='ar' else 'Total Expenses'}: {int(total_expenses)} LBP\n"
            f"{'المدفوعات المعلقة' if lang=='ar' else 'Pending Payments'}: {int(total_pending)} LBP"
        )
        await send(short, reply_markup=get_main_keyboard(lang))