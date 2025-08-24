from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date, timedelta
from core_singleton import get_farm_core
from keyboards import get_main_keyboard


TREATMENT_STATES = {
    'TREATMENT_CROP': 0,
    'TREATMENT_PRODUCT': 1,
    'TREATMENT_DATE': 2,
    'TREATMENT_COST': 3,
    'TREATMENT_NEXT_DATE': 4
}

# ----------------------
# Helpers
# ----------------------
def _parse_date_input(text: str):
    t = text.strip()
    lowers = t.lower()
    if lowers in ["today", "اليوم"]:
        return date.today()
    if lowers in ["yesterday", "أمس"]:
        return date.today() - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except Exception:
            pass
    raise ValueError("Invalid date")

# ----------------------
# Treatment flow (inline-first)
# ----------------------
async def add_treatment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # support called by message or callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send = query.message.reply_text
        uid = query.from_user.id
    else:
        send = update.message.reply_text
        uid = update.effective_user.id

    farm_core = get_farm_core()
    farmer = farm_core.get_farmer(uid)
    if not farmer:
        await send("Create an account first. Use /start")
        return ConversationHandler.END

    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await send("ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language']=='ar' else "No crops found. Add a crop first.")
        return ConversationHandler.END

    lang = farmer['language']
    kb = []
    # inline buttons, one crop per row
    for c in crops:
        kb.append([InlineKeyboardButton(c['name'], callback_data=f"treatment_crop:{c['id']}")])
    # back button
    kb.append([InlineKeyboardButton("🔙 " + ("العودة" if lang=='ar' else "Back"), callback_data="crop_page:0")])
    await send("اختر المحصول:" if lang=='ar' else "Choose crop:", reply_markup=InlineKeyboardMarkup(kb))
    return TREATMENT_STATES['TREATMENT_CROP']

async def treatment_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle crop selection (callback) or typed crop name (message)."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        try:
            crop_id = data.split(":", 1)[1]
        except Exception:
            await query.message.reply_text("اختيار غير صالح." if farm_core.get_farmer(query.from_user.id)['language']=='ar' else "Invalid selection.")
            return ConversationHandler.END
        context.user_data['crop_id'] = crop_id
        farmer = farm_core.get_farmer(query.from_user.id)
        lang = farmer['language']
        await query.message.reply_text("ما هو اسم المنتج؟ (مثال: مبيد، سماد)" if lang=='ar' else "What's the product name? (e.g., pesticide, fertilizer)")
        return TREATMENT_STATES['TREATMENT_PRODUCT']

    # message fallback (user typed crop name)
    crop_name = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text("المحصول غير موجود." if lang == 'ar' else "Crop not found.")
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    await update.message.reply_text("ما هو اسم المنتج؟ (مثال: مبيد، سماد)" if lang=='ar' else "What's the product name? (e.g., pesticide, fertilizer)")
    return TREATMENT_STATES['TREATMENT_PRODUCT']

async def treatment_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store product name and ask for treatment date via inline buttons."""
    context.user_data['product_name'] = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    date_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("اليوم" if lang=='ar' else "Today", callback_data="treatment_date:today"),
         InlineKeyboardButton("أمس" if lang=='ar' else "Yesterday", callback_data="treatment_date:yesterday")],
        [InlineKeyboardButton("📅 " + ("اختر تاريخًا" if lang=='ar' else "Pick Date"), callback_data="treatment_date:pick")]
    ])
    await update.message.reply_text("متى تم العلاج؟" if lang=='ar' else "When was the treatment applied?", reply_markup=date_kb)
    return TREATMENT_STATES['TREATMENT_DATE']

async def treatment_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline date choices."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'

    if data.endswith(":pick"):
        await query.message.reply_text("أدخل التاريخ (YYYY-MM-DD أو DD/MM/YYYY)" if lang=='ar' else "Enter date (YYYY-MM-DD or DD/MM/YYYY)")
        return TREATMENT_STATES['TREATMENT_DATE']

    tag = data.split(":", 1)[1]
    if tag == "today":
        treatment_dt = date.today()
    else:
        treatment_dt = date.today() - timedelta(days=1)
    context.user_data['treatment_date'] = treatment_dt
    # ask cost (optional) with inline Skip
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="treatment_skip:cost")]])
    await query.message.reply_text(f"{('التاريخ المحدد' if lang=='ar' else 'Selected date')}: {treatment_dt.isoformat()}")
    await query.message.reply_text("التكلفة؟ (اختياري)" if lang=='ar' else "Cost? (optional)", reply_markup=kb)
    return TREATMENT_STATES['TREATMENT_COST']

async def treatment_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle typed date input after user chose Pick Date."""
    text = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        d = _parse_date_input(text)
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD أو DD/MM/YYYY" if lang=='ar' else "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY")
        return TREATMENT_STATES['TREATMENT_DATE']
    context.user_data['treatment_date'] = d
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="treatment_skip:cost")]])
    await update.message.reply_text(f"{('التاريخ المحدد' if lang=='ar' else 'Selected date')}: {d.isoformat()}")
    await update.message.reply_text("التكلفة؟ (اختياري)" if lang=='ar' else "Cost? (optional)", reply_markup=kb)
    return TREATMENT_STATES['TREATMENT_COST']

async def treatment_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle typed cost (or 'skip'). Then ask for next date (optional)."""
    text = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip']:
        context.user_data['treatment_cost'] = None
    else:
        try:
            cost = float(text)
            context.user_data['treatment_cost'] = cost
        except ValueError:
            await update.message.reply_text("أدخل رقمًا صحيحًا أو 'تخطي'." if lang=='ar' else "Enter a valid number or 'Skip'.")
            return TREATMENT_STATES['TREATMENT_COST']

    # ask next date with inline skip / pick
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="treatment_skip:next"),
         InlineKeyboardButton("📅 " + ("اختر تاريخًا" if lang=='ar' else "Pick Date"), callback_data="treatment_next:pick")]
    ])
    await update.message.reply_text("التاريخ القادم للعلاج؟ (اختياري)" if lang=='ar' else "Next treatment date? (optional)", reply_markup=kb)
    return TREATMENT_STATES['TREATMENT_NEXT_DATE']

async def treatment_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Skip inline for cost or next date; also handle pick next-date callback."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'

    # cost skip
    if data == "treatment_skip:cost":
        context.user_data['treatment_cost'] = None
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="treatment_skip:next"),
             InlineKeyboardButton("📅 " + ("اختر تاريخًا" if lang=='ar' else "Pick Date"), callback_data="treatment_next:pick")]
        ])
        await query.message.reply_text("التاريخ القادم للعلاج؟ (اختياري)" if lang=='ar' else "Next treatment date? (optional)", reply_markup=kb)
        return TREATMENT_STATES['TREATMENT_NEXT_DATE']

    # next-date pick handler (user pressed pick)
    if data == "treatment_next:pick":
        await query.message.reply_text("أدخل التاريخ التالي (YYYY-MM-DD أو DD/MM/YYYY)" if lang=='ar' else "Enter next date (YYYY-MM-DD or DD/MM/YYYY)")
        return TREATMENT_STATES['TREATMENT_NEXT_DATE']

    # next-date skip
    if data == "treatment_skip:next":
        next_date = None
        # save now
        farmer = farm_core.get_farmer(query.from_user.id)
        saved = farm_core.add_treatment(
            crop_id=context.user_data.get('crop_id'),
            treatment_date=context.user_data.get('treatment_date'),
            product_name=context.user_data.get('product_name'),
            cost=context.user_data.get('treatment_cost'),
            next_due_date=next_date
        )
        if saved:
            await query.message.reply_text("تم تسجيل العلاج! ✅" if farmer['language']=='ar' else "Treatment recorded! ✅", reply_markup=get_main_keyboard(farmer['language']))
        else:
            await query.message.reply_text("خطأ في تسجيل العلاج." if farmer['language']=='ar' else "Error recording treatment.")
        # cleanup
        for k in ("crop_id", "product_name", "treatment_date", "treatment_cost"):
            context.user_data.pop(k, None)
        return ConversationHandler.END

    # unknown
    await query.message.reply_text("خيار غير معروف." if lang=='ar' else "Unknown option.")
    return ConversationHandler.END

async def treatment_next_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle typed next date after pick or typed skip."""
    text = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text.lower() in ['تخطي', 'skip', '']:
        next_date = None
    else:
        try:
            next_date = _parse_date_input(text)
        except ValueError:
            await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD أو DD/MM/YYYY" if lang=='ar' else "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY")
            return TREATMENT_STATES['TREATMENT_NEXT_DATE']

    # save treatment
    saved = farm_core.add_treatment(
        crop_id=context.user_data.get('crop_id'),
        treatment_date=context.user_data.get('treatment_date'),
        product_name=context.user_data.get('product_name'),
        cost=context.user_data.get('treatment_cost'),
        next_due_date=next_date
    )
    if saved:
        await update.message.reply_text("تم تسجيل العلاج! ✅" if lang=='ar' else "Treatment recorded! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ في تسجيل العلاج." if lang=='ar' else "Error recording treatment.")

    # cleanup
    for k in ("crop_id", "product_name", "treatment_date", "treatment_cost"):
        context.user_data.pop(k, None)
    return ConversationHandler.END





