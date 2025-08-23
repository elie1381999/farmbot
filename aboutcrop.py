# aboutcrop.py
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, date, timedelta
from core_singleton import farm_core
from keyboards import get_main_keyboard

# Conversation states
CROP_STATES = {
    'CROP_NAME': 0,
    'CROP_PLANTING_DATE': 1,
    'CROP_NOTES': 2
}

HARVEST_STATES = {
    'HARVEST_CROP': 0,
    'HARVEST_DATE': 1,
    'HARVEST_QUANTITY': 2,
    'HARVEST_DELIVERY': 3,
    'DELIVERY_COLLECTOR': 4,
    'DELIVERY_MARKET': 5
}

EDIT_STATES = {
    'CHOOSE_FIELD': 10,
    'EDIT_NAME': 11,
    'EDIT_PLANTING_DATE': 12,
    'EDIT_NOTES': 13
}

CROPS_PER_PAGE = 6

# ----------------------
# Helpers
# ----------------------
def _parse_date_input(text: str):
    """Try several date formats, return date or raise ValueError."""
    text = text.strip()
    lowers = text.lower()
    if lowers in ["today", "اليوم"]:
        return date.today()
    if lowers in ["yesterday", "أمس"]:
        return date.today() - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            pass
    raise ValueError("Invalid date")

def _format_crop_line(crop):
    name = crop.get('name') or "Unknown"
    plant_date = crop.get('planting_date') or "N/A"
    notes_preview = (crop.get('notes') or "")[:80]
    return f"• {name} — planted: {plant_date}" + (f"\n  notes: {notes_preview}" if notes_preview else "")

# ----------------------
# Add-crop flow (inline-first)
# ----------------------
async def add_crop_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts add-crop flow (entry from inline button)."""
    query = update.callback_query
    await query.answer()
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await query.message.reply_text("Create an account first. Use /start")
        return -1
    lang = farmer['language']
    await query.message.reply_text(
        ("بدء إضافة محصول جديد — اكتب اسم المحصول أدناه." if lang == 'ar'
         else "Starting new crop — type the crop name below."),
        reply_markup=get_main_keyboard(lang)
    )
    suggestions = [
        InlineKeyboardButton("تفاح" if lang == 'ar' else "Apple", callback_data="prefcrop:Apple"),
        InlineKeyboardButton("طماطم" if lang == 'ar' else "Tomato", callback_data="prefcrop:Tomato"),
        InlineKeyboardButton("بطاطس" if lang == 'ar' else "Potato", callback_data="prefcrop:Potato"),
    ]
    await query.message.reply_text("أو اضغط على أحد الاقتراحات:" if lang == 'ar' else "Or tap a suggestion:", reply_markup=InlineKeyboardMarkup([suggestions[:2], suggestions[2:]]))
    return CROP_STATES['CROP_NAME']

async def add_crop_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data['crop_name'] = name
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    date_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("اليوم" if lang == 'ar' else "Today", callback_data="date:today"),
         InlineKeyboardButton("أمس" if lang == 'ar' else "Yesterday", callback_data="date:yesterday")],
        [InlineKeyboardButton("📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date", callback_data="date:pick")]
    ])
    await update.message.reply_text("متى تم زراعته؟" if lang == 'ar' else "When was it planted?", reply_markup=get_main_keyboard(lang))
    await update.message.reply_text("اختر طريقة الإدخال:" if lang == 'ar' else "Choose an option:", reply_markup=date_kb)
    return CROP_STATES['CROP_PLANTING_DATE']

async def add_crop_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # handles typed date or receives callback via crops_callback_handler for prefcrop/date
    text = update.message.text if update.message else ""
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        planting_date = _parse_date_input(text)
    except Exception:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD أو DD/MM/YYYY" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY", reply_markup=get_main_keyboard(lang))
        return CROP_STATES['CROP_PLANTING_DATE']
    context.user_data['planting_date'] = planting_date
    # ask notes (optional) with inline Skip
    kb_skip = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang == 'ar' else "Skip", callback_data="addcrop_skip_notes")]])
    await update.message.reply_text("ملاحظات (اختياري)" if lang == 'ar' else "Notes (optional)", reply_markup=kb_skip)
    return CROP_STATES['CROP_NOTES']

async def add_crop_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    notes = None if text.lower() in ['تخطي', 'skip'] else text.strip()
    crop = farm_core.add_crop(
        farmer_id=farmer['id'],
        name=context.user_data.get('crop_name'),
        planting_date=context.user_data.get('planting_date'),
        notes=notes
    )
    if crop:
        await update.message.reply_text("تم إضافة المحصول بنجاح! ✅" if lang == 'ar' else "Crop added successfully! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang == 'ar' else "Error adding crop. Please try again.", reply_markup=get_main_keyboard(lang))
    for k in ("crop_name", "planting_date"):
        context.user_data.pop(k, None)
    return -1  # ConversationHandler.END (used by main) — returning -1 is safe; main registered fallbacks handle ending

async def addcrop_skip_notes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    farmer = farm_core.get_farmer(query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'
    notes = None
    crop = farm_core.add_crop(
        farmer_id=farmer['id'],
        name=context.user_data.get('crop_name'),
        planting_date=context.user_data.get('planting_date'),
        notes=notes
    )
    if crop:
        await query.message.reply_text("تم إضافة المحصول بنجاح! ✅" if lang == 'ar' else "Crop added successfully! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await query.message.reply_text("خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang=='ar' else "Error adding crop. Please try again.", reply_markup=get_main_keyboard(lang))
    for k in ("crop_name", "planting_date"):
        context.user_data.pop(k, None)
    return -1

# ----------------------
# My Crops view: list + inline per-crop manage + pagination + Add inline
# ----------------------
async def _send_crops_page(update_or_query, context, page: int):
    crops = context.user_data.get('crops_list', [])
    if hasattr(update_or_query, "effective_user"):
        farmer = farm_core.get_farmer(update_or_query.effective_user.id)
    else:
        farmer = farm_core.get_farmer(context.user_data.get('caller_id') or 0)
    lang = farmer['language'] if farmer else 'ar'

    total = len(crops)
    start = page * CROPS_PER_PAGE
    end = start + CROPS_PER_PAGE
    page_crops = crops[start:end]

    header = "🌾 محاصيلك:\n\n" if lang == 'ar' else "🌾 Your Crops:\n\n"
    if not page_crops:
        text = header + ( "ليس لديك محاصيل." if lang=='ar' else "No crops found.")
    else:
        text = header + "\n\n".join(_format_crop_line(c) for c in page_crops)

    kb_rows = []
    for c in page_crops:
        kb_rows.append([InlineKeyboardButton(f"⚙️ {c.get('name', 'Crop')}", callback_data=f"crop_manage:{c['id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق" if lang == 'ar' else "⬅️ Prev", callback_data=f"crop_page:{page-1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("التالي ➡️" if lang == 'ar' else "Next ➡️", callback_data=f"crop_page:{page+1}"))
    nav_row.append(InlineKeyboardButton("➕ أضف محصول" if lang == 'ar' else "➕ Add Crop", callback_data="crop_add"))
    if nav_row:
        kb_rows.append(nav_row)

    markup = InlineKeyboardMarkup(kb_rows)

    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        query = update_or_query.callback_query
        await query.answer()
        await query.message.edit_text(text, reply_markup=markup)
    else:
        if hasattr(update_or_query, "message") and update_or_query.message:
            await update_or_query.message.reply_text(text, reply_markup=markup)
        else:
            to_id = update_or_query.effective_user.id if hasattr(update_or_query, "effective_user") else context._chat_id
            await context.bot.send_message(chat_id=to_id, text=text, reply_markup=markup)

async def my_crops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text("ليس لديك محاصيل." if lang == 'ar' else "No crops found.", reply_markup=get_main_keyboard(lang))
        return
    context.user_data['crops_list'] = crops
    await _send_crops_page(update, context, 0)

# callback for navigation (pages) and pref crop sugg. Also handle "crop_add" start here to keep UX simple
async def crops_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    if data.startswith("crop_page:"):
        try:
            page = int(data.split(":", 1)[1])
        except Exception:
            page = 0
        if 'crops_list' not in context.user_data:
            farmer = farm_core.get_farmer(update.effective_user.id)
            context.user_data['crops_list'] = farm_core.get_farmer_crops(farmer['id'])
        await _send_crops_page(update, context, page)
        return

    if data.startswith("prefcrop:"):
        _, name = data.split(":", 1)
        context.user_data['crop_name'] = name
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language'] if farmer else 'ar'
        date_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اليوم" if lang == 'ar' else "Today", callback_data="date:today"),
             InlineKeyboardButton("أمس" if lang == 'ar' else "Yesterday", callback_data="date:yesterday")],
            [InlineKeyboardButton("📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date", callback_data="date:pick")]
        ])
        await query.message.reply_text(f"{('تم اختيار' if lang=='ar' else 'Selected')}: {name}\n" + ("متى تم زراعته؟" if lang == 'ar' else "When was it planted?"), reply_markup=get_main_keyboard(lang))
        await query.message.reply_text("اختر طريقة الإدخال:" if lang == 'ar' else "Choose an option:", reply_markup=date_kb)
        return

    if data == "crop_add":
        await query.message.reply_text("Opening Add Crop form..." if farm_core.get_farmer(update.effective_user.id)['language']=='ar' else "Opening Add Crop form...")
        return

# ----------------------
# Manage / Edit / Delete callbacks
# ----------------------
async def crop_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    crops = context.user_data.get('crops_list') or []
    crop = next((c for c in crops if str(c.get('id')) == str(crop_id)), None)
    if not crop:
        farmer = farm_core.get_farmer(update.effective_user.id)
        all_crops = farm_core.get_farmer_crops(farmer['id'])
        crop = next((c for c in all_crops if str(c.get('id')) == str(crop_id)), None)
    if not crop:
        await query.message.reply_text("Crop not found.")
        return
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    text = f"🔎 {crop.get('name')}\n\n• planted: {crop.get('planting_date')}\n• notes: {crop.get('notes') or '—'}\n"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل" if lang == 'ar' else "✏️ Edit", callback_data=f"crop_edit:{crop_id}"),
         InlineKeyboardButton("🗑️ حذف" if lang == 'ar' else "🗑️ Delete", callback_data=f"crop_delete:{crop_id}")],
        [InlineKeyboardButton("🔙 العودة" if lang == 'ar' else "🔙 Back", callback_data="crop_page:0")]
    ])
    await query.message.edit_text(text, reply_markup=kb)

async def crop_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("نعم، احذف" if lang == 'ar' else "Yes, delete", callback_data=f"confirm_delete:{crop_id}"),
         InlineKeyboardButton("إلغاء" if lang == 'ar' else "Cancel", callback_data="crop_page:0")]
    ])
    await query.message.edit_text("هل أنت متأكد؟ حذف المحصول سيحذف بياناته." if lang == 'ar' else "Are you sure? Deleting a crop will remove its data.", reply_markup=kb)

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    success = farm_core.delete_crop(crop_id)
    if success:
        context.user_data.pop('crops_list', None)
        await query.message.edit_text("تم حذف المحصول." if lang == 'ar' else "Crop deleted.")
    else:
        await query.message.edit_text("خطأ: لم يتم الحذف." if lang == 'ar' else "Error: could not delete crop.")
    context.user_data['crops_list'] = farm_core.get_farmer_crops(farmer['id'])
    await _send_crops_page(update, context, 0)

# ----------------------
# Edit flow (starts from callback crop_edit:<id>)
# ----------------------
async def crop_edit_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return -1
    context.user_data['edit_crop_id'] = crop_id
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("الاسم" if lang == 'ar' else "Name", callback_data="edit_field:name"),
         InlineKeyboardButton("تاريخ الزراعة" if lang == 'ar' else "Planting Date", callback_data="edit_field:date")],
        [InlineKeyboardButton("ملاحظات" if lang == 'ar' else "Notes", callback_data="edit_field:notes"),
         InlineKeyboardButton("إلغاء" if lang == 'ar' else "Cancel", callback_data="crop_page:0")]
    ])
    await query.message.edit_text("اختر الحقل الذي تريد تعديله:" if lang == 'ar' else "Choose the field you want to edit:", reply_markup=kb)
    return EDIT_STATES['CHOOSE_FIELD']

async def edit_field_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    if not data.startswith("edit_field:"):
        await query.message.reply_text("Invalid selection.")
        return -1
    field = data.split(":", 1)[1]
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    if field == "name":
        await query.message.edit_text("أدخل الاسم الجديد:" if lang == 'ar' else "Enter new name:")
        return EDIT_STATES['EDIT_NAME']
    if field == "date":
        await query.message.edit_text("أدخل التاريخ الجديد (YYYY-MM-DD):" if lang == 'ar' else "Enter new planting date (YYYY-MM-DD):")
        return EDIT_STATES['EDIT_PLANTING_DATE']
    if field == "notes":
        await query.message.edit_text("أدخل الملاحظات الجديدة أو اكتب 'تخطي' للإزالة:" if lang == 'ar' else "Enter new notes or type 'Skip' to clear:")
        return EDIT_STATES['EDIT_NOTES']
    await query.message.reply_text("Invalid field.")
    return -1

async def edit_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    crops = farm_core.get_farmer_crops(farmer['id'])
    if any(c['name'].strip().lower() == new_name.lower() and str(c['id']) != str(crop_id) for c in crops):
        await update.message.reply_text("يوجد محصول بنفس الاسم. اختر اسمًا مختلفًا." if lang == 'ar' else "A crop with that name already exists. Pick a different name.")
        return EDIT_STATES['EDIT_NAME']
    updated = farm_core.update_crop(crop_id, name=new_name)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث اسم المحصول." if lang == 'ar' else "Crop name updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return -1

async def edit_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        new_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD")
        return EDIT_STATES['EDIT_PLANTING_DATE']
    updated = farm_core.update_crop(crop_id, planting_date=new_date)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث تاريخ الزراعة." if lang == 'ar' else "Planting date updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return -1

async def edit_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    if text.lower() in ['تخطي', 'skip']:
        notes = None
    else:
        notes = text.strip()
    updated = farm_core.update_crop(crop_id, notes=notes)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث الملاحظات." if lang == 'ar' else "Notes updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return -1

# ----------------------
# Harvest flows (inline-first)
# ----------------------
async def record_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: show inline list of crops (buttons inside the conversation)."""
    # handle whether called from message or callback_query
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send_method = query.message.reply_text
        uid = query.from_user.id
    else:
        send_method = update.message.reply_text
        uid = update.effective_user.id

    farmer = farm_core.get_farmer(uid)
    if not farmer:
        await send_method("Create an account first. Use /start")
        return -1
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await send_method("ليس لديك محاصيل. أضف محصولًا أولاً." if lang == 'ar' else "No crops found. Add a crop first.")
        return -1

    kb = []
    for c in crops:
        kb.append([InlineKeyboardButton(c['name'], callback_data=f"harvest_select:{c['id']}")])
    kb.append([InlineKeyboardButton("🔙 " + ("العودة" if lang == 'ar' else "Back"), callback_data="crop_page:0")])
    await send_method("اختر المحصول:" if lang == 'ar' else "Choose crop:", reply_markup=InlineKeyboardMarkup(kb))
    return HARVEST_STATES['HARVEST_CROP']

async def harvest_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped a crop inline button."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return -1
    context.user_data['crop_id'] = crop_id
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'

    date_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("اليوم" if lang == 'ar' else "Today", callback_data="harvest_date:today"),
         InlineKeyboardButton("أمس" if lang == 'ar' else "Yesterday", callback_data="harvest_date:yesterday")],
        [InlineKeyboardButton("📅 " + ("اختر تاريخًا" if lang == 'ar' else "Pick Date"), callback_data="harvest_date:pick")]
    ])
    await query.message.reply_text("متى تم الحصاد؟" if lang == 'ar' else "When was the harvest?", reply_markup=date_kb)
    return HARVEST_STATES['HARVEST_DATE']

async def harvest_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline date choices (today/yesterday/pick)."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(update.callback_query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'

    if data == "harvest_date:pick":
        await query.message.reply_text("أدخل التاريخ (YYYY-MM-DD أو DD/MM/YYYY)" if lang == 'ar' else "Enter date (YYYY-MM-DD or DD/MM/YYYY)")
        return HARVEST_STATES['HARVEST_DATE']

    if data.endswith(":today") or data.endswith(":yesterday"):
        tag = data.split(":", 1)[1]
        if tag == "today":
            harvest_date = date.today()
        else:
            harvest_date = date.today() - timedelta(days=1)
        context.user_data['harvest_date'] = harvest_date
        await query.message.reply_text(f"{('التاريخ المحدد' if lang=='ar' else 'Selected date')}: {harvest_date.isoformat()}")
        await query.message.reply_text("كم الكمية (كجم)؟" if lang == 'ar' else "Enter quantity (kg):")
        return HARVEST_STATES['HARVEST_QUANTITY']

    await query.message.reply_text("خيار غير معروف." if lang == 'ar' else "Unknown option.")
    return HARVEST_STATES['HARVEST_DATE']

async def harvest_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        harvest_date = _parse_date_input(text)
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD أو DD/MM/YYYY" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY")
        return HARVEST_STATES['HARVEST_DATE']
    context.user_data['harvest_date'] = harvest_date
    await update.message.reply_text(f"{('التاريخ المحدد' if lang=='ar' else 'Selected date')}: {harvest_date.isoformat()}")
    await update.message.reply_text("كم الكمية (كجم)؟" if lang == 'ar' else "Enter quantity (kg):")
    return HARVEST_STATES['HARVEST_QUANTITY']

async def harvest_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        quantity = float(update.message.text)
        context.user_data['harvest_quantity'] = quantity
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("نعم - تم التسليم" if lang == 'ar' else "Yes - Delivered", callback_data="harvest_delivery:delivered"),
             InlineKeyboardButton("لا - مخزون" if lang == 'ar' else "No - Stored", callback_data="harvest_delivery:stored")]
        ])
        await update.message.reply_text("هل تم تسليمه إلى الجامع؟" if lang == 'ar' else "Was it handed to the collector?", reply_markup=kb)
        return HARVEST_STATES['HARVEST_DELIVERY']
    except ValueError:
        await update.message.reply_text("أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number.")
        return HARVEST_STATES['HARVEST_QUANTITY']

async def harvest_delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(update.callback_query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'

    status = "delivered" if data.endswith(":delivered") else "stored"
    harvest = farm_core.record_harvest(
        crop_id=context.user_data['crop_id'],
        harvest_date=context.user_data.get('harvest_date', date.today()),
        quantity=context.user_data.get('harvest_quantity', 0),
        notes=None,
        status=status
    )
    if not harvest:
        await query.message.reply_text("خطأ في تسجيل الحصاد." if lang == 'ar' else "Error recording harvest.")
        return -1
    context.user_data['harvest_id'] = harvest['id']

    if status == "delivered":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="harvest_skip:collector")]])
        await query.message.reply_text("اسم الجامع؟ (اختياري)" if lang == 'ar' else "Collector's name? (optional)", reply_markup=kb)
        return HARVEST_STATES['DELIVERY_COLLECTOR']
    else:
        await query.message.reply_text(f"تم تسجيل الحصاد بنجاح! ✅ {context.user_data['harvest_quantity']} kg" if lang == 'ar' else f"Harvest recorded! ✅ {context.user_data['harvest_quantity']} kg", reply_markup=get_main_keyboard(lang))
        return -1

async def harvest_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    farmer = farm_core.get_farmer(update.callback_query.from_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        part = data.split(":", 1)[1]
    except Exception:
        part = None

    if part == "collector":
        context.user_data['collector_name'] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="harvest_skip:market")]])
        await query.message.reply_text("إلى أي سوق؟ (اختياري)" if lang == 'ar' else "Which market? (optional)", reply_markup=kb)
        return HARVEST_STATES['DELIVERY_MARKET']
    if part == "market":
        market = None
        delivery = farm_core.record_delivery(
            harvest_id=context.user_data['harvest_id'],
            delivery_date=date.today(),
            collector_name=context.user_data.get('collector_name'),
            market=market
        )
        if delivery:
            await query.message.reply_text("تم تسجيل التسليم! ✅ الدفع متوقع خلال 7 أيام" if lang == 'ar' else "Delivery recorded! ✅ Payment expected in 7 days", reply_markup=get_main_keyboard(lang))
        else:
            await query.message.reply_text("خطأ في تسجيل التسليم." if lang == 'ar' else "Error recording delivery.")
        return -1

async def harvest_delivery_collector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    context.user_data['collector_name'] = None if text.lower() in ["تخطي", "skip"] else text
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("تخطي" if lang=='ar' else "Skip", callback_data="harvest_skip:market")]])
    await update.message.reply_text("إلى أي سوق؟ (اختياري)" if lang == 'ar' else "Which market? (optional)", reply_markup=kb)
    return HARVEST_STATES['DELIVERY_MARKET']

async def harvest_delivery_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    market = None if text.lower() in ["تخطي", "skip"] else text
    delivery = farm_core.record_delivery(
        harvest_id=context.user_data['harvest_id'],
        delivery_date=date.today(),
        collector_name=context.user_data.get('collector_name'),
        market=market
    )
    if delivery:
        await update.message.reply_text("تم تسجيل التسليم! ✅ الدفع متوقع خلال 7 أيام" if lang == 'ar' else "Delivery recorded! ✅ Payment expected in 7 days", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ في تسجيل التسليم." if lang == 'ar' else "Error recording delivery.")
    return -1



















'''from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from datetime import datetime, date, timedelta
from core_singleton import farm_core
from keyboards import get_main_keyboard

# states for adding crop (used by ConversationHandler)
CROP_STATES = {
    'CROP_NAME': 0,
    'CROP_PLANTING_DATE': 1,
    'CROP_NOTES': 2
}

# harvest flow states
HARVEST_STATES = {
    'HARVEST_CROP': 0,
    'HARVEST_DATE': 1,
    'HARVEST_QUANTITY': 2,
    'HARVEST_DELIVERY': 3,
    'DELIVERY_COLLECTOR': 4,
    'DELIVERY_MARKET': 5
}

# edit flow states
EDIT_STATES = {
    'CHOOSE_FIELD': 10,
    'EDIT_NAME': 11,
    'EDIT_PLANTING_DATE': 12,
    'EDIT_NOTES': 13
}

CROPS_PER_PAGE = 6

# ----------------------
# Add-crop flow (started by inline "➕ Add Crop" in My Crops)
# - Entry: callback query with data "crop_add" -> add_crop_start_callback
# - States: CROP_NAME -> CROP_PLANTING_DATE -> CROP_NOTES
# The reply keyboard (main menu) is preserved by including get_main_keyboard on prompt messages.
# ----------------------
async def add_crop_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts add-crop flow (entry from inline button)."""
    query = update.callback_query
    await query.answer()
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await query.message.reply_text("Create an account first. Use /start")
        return ConversationHandler.END
    lang = farmer['language']
    # ensure main keyboard stays visible
    await query.message.reply_text(
        ("بدء إضافة محصول جديد — اكتب اسم المحصول أدناه." if lang == 'ar'
         else "Starting new crop — type the crop name below."),
        reply_markup=get_main_keyboard(lang)
    )
    # show a quick inline suggestions row (optional)
    suggestions = [
        InlineKeyboardButton("تفاح" if lang == 'ar' else "Apple", callback_data="prefcrop:Apple"),
        InlineKeyboardButton("طماطم" if lang == 'ar' else "Tomato", callback_data="prefcrop:Tomato"),
        InlineKeyboardButton("بطاطس" if lang == 'ar' else "Potato", callback_data="prefcrop:Potato"),
    ]
    # send inline suggestions (they simply fill the name when pressed)
    await query.message.reply_text("أو اضغط على أحد الاقتراحات:" if lang == 'ar' else "Or tap a suggestion:", reply_markup=InlineKeyboardMarkup([suggestions[:2], suggestions[2:]]))
    return CROP_STATES['CROP_NAME']

async def add_crop_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle typed name (or suggestion callback is handled in crops_callback_handler)."""
    name = update.message.text.strip()
    context.user_data['crop_name'] = name
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    # go to date step and present inline variants
    date_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("اليوم" if lang == 'ar' else "Today", callback_data="date:today"),
         InlineKeyboardButton("أمس" if lang == 'ar' else "Yesterday", callback_data="date:yesterday")],
        [InlineKeyboardButton("📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date", callback_data="date:pick")]
    ])
    # keep main keyboard visible by sending it (reply keyboard)
    await update.message.reply_text("متى تم زراعته؟" if lang == 'ar' else "When was it planted?", reply_markup=get_main_keyboard(lang))
    await update.message.reply_text("اختر طريقة الإدخال:" if lang == 'ar' else "Choose an option:", reply_markup=date_kb)
    return CROP_STATES['CROP_PLANTING_DATE']

async def add_crop_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle date typed after the user selected 'Pick Date' or typed directly."""
    text = update.message.text.strip()
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        planting_date = (
            date.today() if text in ["اليوم", "Today"]
            else date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"]
            else datetime.strptime(text, "%Y-%m-%d").date()
        )
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD", reply_markup=get_main_keyboard(lang))
        return CROP_STATES['CROP_PLANTING_DATE']
    context.user_data['planting_date'] = planting_date
    # ask notes (optional)
    await update.message.reply_text("ملاحظات (اختياري) — اكتب 'تخطي' للمتابعة." if lang == 'ar' else "Notes (optional) — type 'Skip' to continue.", reply_markup=get_main_keyboard(lang))
    return CROP_STATES['CROP_NOTES']

async def add_crop_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    notes = None if text.lower() in ['تخطي', 'skip'] else text.strip()
    # Save crop
    crop = farm_core.add_crop(
        farmer_id=farmer['id'],
        name=context.user_data.get('crop_name'),
        planting_date=context.user_data.get('planting_date'),
        notes=notes
    )
    if crop:
        await update.message.reply_text("تم إضافة المحصول بنجاح! ✅" if lang == 'ar' else "Crop added successfully! ✅", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء إضافة المحصول. حاول مرة أخرى." if lang == 'ar' else "Error adding crop. Please try again.", reply_markup=get_main_keyboard(lang))
    # cleanup
    for k in ("crop_name", "planting_date"):
        context.user_data.pop(k, None)
    return ConversationHandler.END

# ----------------------
# My Crops view: list + inline per-crop manage + pagination + Add inline
# ----------------------
def _format_crop_line(crop):
    name = crop.get('name') or "Unknown"
    plant_date = crop.get('planting_date') or "N/A"
    notes_preview = (crop.get('notes') or "")[:80]
    return f"• {name} — planted: {plant_date}" + (f"\n  notes: {notes_preview}" if notes_preview else "")

async def _send_crops_page(update_or_query, context, page: int):
    crops = context.user_data.get('crops_list', [])
    # determine lang from the user
    if hasattr(update_or_query, "effective_user"):
        farmer = farm_core.get_farmer(update_or_query.effective_user.id)
    else:
        farmer = farm_core.get_farmer(context.user_data.get('caller_id') or 0)
    lang = farmer['language'] if farmer else 'ar'

    total = len(crops)
    start = page * CROPS_PER_PAGE
    end = start + CROPS_PER_PAGE
    page_crops = crops[start:end]

    header = "🌾 محاصيلك:\n\n" if lang == 'ar' else "🌾 Your Crops:\n\n"
    if not page_crops:
        text = header + ( "ليس لديك محاصيل." if lang=='ar' else "No crops found.")
    else:
        text = header + "\n\n".join(_format_crop_line(c) for c in page_crops)

    kb_rows = []
    # one manage button per crop (inline, shown under the message)
    for c in page_crops:
        kb_rows.append([InlineKeyboardButton(f"⚙️ {c.get('name', 'Crop')}", callback_data=f"crop_manage:{c['id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق" if lang == 'ar' else "⬅️ Prev", callback_data=f"crop_page:{page-1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("التالي ➡️" if lang == 'ar' else "Next ➡️", callback_data=f"crop_page:{page+1}"))
    # inline Add button (no main-menu Add)
    nav_row.append(InlineKeyboardButton("➕ أضف محصول" if lang == 'ar' else "➕ Add Crop", callback_data="crop_add"))
    if nav_row:
        kb_rows.append(nav_row)

    markup = InlineKeyboardMarkup(kb_rows)

    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        query = update_or_query.callback_query
        await query.answer()
        await query.message.edit_text(text, reply_markup=markup)
    else:
        # ensure main keyboard remains visible (ReplyKeyboard)
        if hasattr(update_or_query, "message") and update_or_query.message:
            await update_or_query.message.reply_text(text, reply_markup=markup)
        else:
            to_id = update_or_query.effective_user.id if hasattr(update_or_query, "effective_user") else context._chat_id
            await context.bot.send_message(chat_id=to_id, text=text, reply_markup=markup)

async def my_crops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        # still show main keyboard
        await update.message.reply_text("ليس لديك محاصيل." if lang == 'ar' else "No crops found.", reply_markup=get_main_keyboard(lang))
        return
    context.user_data['crops_list'] = crops
    await _send_crops_page(update, context, 0)

# callback for navigation (pages) and pref crop sugg. Also handle "crop_add" start here to keep UX simple
async def crops_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    if data.startswith("crop_page:"):
        try:
            page = int(data.split(":", 1)[1])
        except Exception:
            page = 0
        if 'crops_list' not in context.user_data:
            farmer = farm_core.get_farmer(update.effective_user.id)
            context.user_data['crops_list'] = farm_core.get_farmer_crops(farmer['id'])
        await _send_crops_page(update, context, page)
        return

    # a pref crop button (from suggestions) - behaves like the user typed the name
    if data.startswith("prefcrop:"):
        _, name = data.split(":", 1)
        # emulate typed name: save to user_data and show date options (keeping main keyboard)
        context.user_data['crop_name'] = name
        farmer = farm_core.get_farmer(update.effective_user.id)
        lang = farmer['language'] if farmer else 'ar'
        date_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اليوم" if lang == 'ar' else "Today", callback_data="date:today"),
             InlineKeyboardButton("أمس" if lang == 'ar' else "Yesterday", callback_data="date:yesterday")],
            [InlineKeyboardButton("📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date", callback_data="date:pick")]
        ])
        await query.message.reply_text(f"{('تم اختيار' if lang=='ar' else 'Selected')}: {name}\n" + ("متى تم زراعته؟" if lang == 'ar' else "When was it planted?"), reply_markup=get_main_keyboard(lang))
        await query.message.reply_text("اختر طريقة الإدخال:" if lang == 'ar' else "Choose an option:", reply_markup=date_kb)
        return

    # start add-crop flow (entry handled by ConversationHandler in main)
    if data == "crop_add":
        # don't do the whole flow here; ConversationHandler entry point handles it.
        # However, the crops_callback_handler registration in main is set to only handle crop_page: pattern.
        # So when crop_add callback is received, the add_crop_start_callback (ConversationHandler entry) will be triggered.
        # We still answer the query here in case the fallback catches it.
        await query.message.reply_text("Opening Add Crop form..." if farm_core.get_farmer(update.effective_user.id)['language']=='ar' else "Opening Add Crop form...")
        return

# ----------------------
# Manage / Edit / Delete callbacks
# ----------------------
async def crop_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    crops = context.user_data.get('crops_list') or []
    crop = next((c for c in crops if str(c.get('id')) == str(crop_id)), None)
    if not crop:
        farmer = farm_core.get_farmer(update.effective_user.id)
        all_crops = farm_core.get_farmer_crops(farmer['id'])
        crop = next((c for c in all_crops if str(c.get('id')) == str(crop_id)), None)
    if not crop:
        await query.message.reply_text("Crop not found.")
        return
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    text = f"🔎 {crop.get('name')}\n\n• planted: {crop.get('planting_date')}\n• notes: {crop.get('notes') or '—'}\n"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل" if lang == 'ar' else "✏️ Edit", callback_data=f"crop_edit:{crop_id}"),
         InlineKeyboardButton("🗑️ حذف" if lang == 'ar' else "🗑️ Delete", callback_data=f"crop_delete:{crop_id}")],
        [InlineKeyboardButton("🔙 العودة" if lang == 'ar' else "🔙 Back", callback_data="crop_page:0")]
    ])
    await query.message.edit_text(text, reply_markup=kb)

async def crop_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("نعم، احذف" if lang == 'ar' else "Yes, delete", callback_data=f"confirm_delete:{crop_id}"),
         InlineKeyboardButton("إلغاء" if lang == 'ar' else "Cancel", callback_data="crop_page:0")]
    ])
    await query.message.edit_text("هل أنت متأكد؟ حذف المحصول سيحذف بياناته." if lang == 'ar' else "Are you sure? Deleting a crop will remove its data.", reply_markup=kb)

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    success = farm_core.delete_crop(crop_id)
    if success:
        context.user_data.pop('crops_list', None)
        await query.message.edit_text("تم حذف المحصول." if lang == 'ar' else "Crop deleted.")
    else:
        await query.message.edit_text("خطأ: لم يتم الحذف." if lang == 'ar' else "Error: could not delete crop.")
    # reload and show page 0
    context.user_data['crops_list'] = farm_core.get_farmer_crops(farmer['id'])
    await _send_crops_page(update, context, 0)

# ----------------------
# Edit flow (starts from callback crop_edit:<id>)
# ----------------------
async def crop_edit_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    try:
        crop_id = data.split(":", 1)[1]
    except Exception:
        await query.message.reply_text("Invalid selection.")
        return ConversationHandler.END
    context.user_data['edit_crop_id'] = crop_id
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("الاسم" if lang == 'ar' else "Name", callback_data="edit_field:name"),
         InlineKeyboardButton("تاريخ الزراعة" if lang == 'ar' else "Planting Date", callback_data="edit_field:date")],
        [InlineKeyboardButton("ملاحظات" if lang == 'ar' else "Notes", callback_data="edit_field:notes"),
         InlineKeyboardButton("إلغاء" if lang == 'ar' else "Cancel", callback_data="crop_page:0")]
    ])
    await query.message.edit_text("اختر الحقل الذي تريد تعديله:" if lang == 'ar' else "Choose the field you want to edit:", reply_markup=kb)
    return EDIT_STATES['CHOOSE_FIELD']

async def edit_field_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    if not data.startswith("edit_field:"):
        await query.message.reply_text("Invalid selection.")
        return ConversationHandler.END
    field = data.split(":", 1)[1]
    lang = farm_core.get_farmer(update.effective_user.id)['language']
    if field == "name":
        await query.message.edit_text("أدخل الاسم الجديد:" if lang == 'ar' else "Enter new name:")
        return EDIT_STATES['EDIT_NAME']
    if field == "date":
        await query.message.edit_text("أدخل التاريخ الجديد (YYYY-MM-DD):" if lang == 'ar' else "Enter new planting date (YYYY-MM-DD):")
        return EDIT_STATES['EDIT_PLANTING_DATE']
    if field == "notes":
        await query.message.edit_text("أدخل الملاحظات الجديدة أو اكتب 'تخطي' للإزالة:" if lang == 'ar' else "Enter new notes or type 'Skip' to clear:")
        return EDIT_STATES['EDIT_NOTES']
    await query.message.reply_text("Invalid field.")
    return ConversationHandler.END

async def edit_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    crops = farm_core.get_farmer_crops(farmer['id'])
    if any(c['name'].strip().lower() == new_name.lower() and str(c['id']) != str(crop_id) for c in crops):
        await update.message.reply_text("يوجد محصول بنفس الاسم. اختر اسمًا مختلفًا." if lang == 'ar' else "A crop with that name already exists. Pick a different name.")
        return EDIT_STATES['EDIT_NAME']
    updated = farm_core.update_crop(crop_id, name=new_name)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث اسم المحصول." if lang == 'ar' else "Crop name updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return ConversationHandler.END

async def edit_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    try:
        new_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD" if lang == 'ar' else "Invalid date format. Use YYYY-MM-DD")
        return EDIT_STATES['EDIT_PLANTING_DATE']
    updated = farm_core.update_crop(crop_id, planting_date=new_date)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث تاريخ الزراعة." if lang == 'ar' else "Planting date updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return ConversationHandler.END

async def edit_notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    crop_id = context.user_data.get('edit_crop_id')
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language'] if farmer else 'ar'
    if text.lower() in ['تخطي', 'skip']:
        notes = None
    else:
        notes = text.strip()
    updated = farm_core.update_crop(crop_id, notes=notes)
    if updated:
        context.user_data.pop('crops_list', None)
        await update.message.reply_text("تم تحديث الملاحظات." if lang == 'ar' else "Notes updated.", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ أثناء التحديث." if lang == 'ar' else "Error updating crop.")
    return ConversationHandler.END

# ----------------------
# Harvest flows
# ----------------------
async def record_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    if not farmer:
        await update.message.reply_text("Create an account first. Use /start")
        return ConversationHandler.END
    crops = farm_core.get_farmer_crops(farmer['id'])
    if not crops:
        await update.message.reply_text("ليس لديك محاصيل. أضف محصولًا أولاً." if farmer['language'] == 'ar' else "No crops found. Add a crop first.")
        return ConversationHandler.END
    lang = farmer['language']
    keyboard = [[crop['name']] for crop in crops]
    await update.message.reply_text("اختر المحصول:" if lang == 'ar' else "Choose crop:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return HARVEST_STATES['HARVEST_CROP']

async def harvest_crop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crop_name = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    crops = farm_core.get_farmer_crops(farmer['id'])
    crop = next((c for c in crops if c['name'] == crop_name), None)
    if not crop:
        await update.message.reply_text("المحصول غير موجود." if lang == 'ar' else "Crop not found.")
        return ConversationHandler.END
    context.user_data['crop_id'] = crop['id']
    keyboard = [["اليوم" if lang == 'ar' else "Today", "أمس" if lang == 'ar' else "Yesterday"],
                ["📅 اختر تاريخًا" if lang == 'ar' else "📅 Pick Date"]]
    await update.message.reply_text("متى تم الحصاد؟" if lang == 'ar' else "When was the harvest?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return HARVEST_STATES['HARVEST_DATE']

async def harvest_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    if text in ["📅 اختر تاريخًا", "📅 Pick Date"]:
        await update.message.reply_text("أدخل التاريخ (YYYY-MM-DD)" if lang == 'ar' else "Enter date (YYYY-MM-DD)")
        return HARVEST_STATES['HARVEST_DATE']
    try:
        harvest_date = date.today() if text in ["اليوم", "Today"] else date.today() - timedelta(days=1) if text in ["أمس", "Yesterday"] else datetime.strptime(text, "%Y-%m-%d").date()
        context.user_data['harvest_date'] = harvest_date
        await update.message.reply_text("كم الكمية (كجم)؟" if lang == 'ar' else "Enter quantity (kg):")
        return HARVEST_STATES['HARVEST_QUANTITY']
    except ValueError:
        await update.message.reply_text("صيغة التاريخ غير صحيحة." if lang == 'ar' else "Invalid date format.")
        return HARVEST_STATES['HARVEST_DATE']

async def harvest_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    try:
        quantity = float(update.message.text)
        context.user_data['harvest_quantity'] = quantity
        keyboard = [["نعم - تم التسليم" if lang == 'ar' else "Yes - Delivered", "لا - مخزون" if lang == 'ar' else "No - Stored"]]
        await update.message.reply_text("هل تم تسليمه إلى الجامع؟" if lang == 'ar' else "Was it handed to the collector?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return HARVEST_STATES['HARVEST_DELIVERY']
    except ValueError:
        await update.message.reply_text("أدخل رقمًا صحيحًا." if lang == 'ar' else "Enter a valid number.")
        return HARVEST_STATES['HARVEST_QUANTITY']

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
        await update.message.reply_text("خطأ في تسجيل الحصاد." if lang == 'ar' else "Error recording harvest.")
        return ConversationHandler.END
    context.user_data['harvest_id'] = harvest['id']
    if status == "delivered":
        await update.message.reply_text("اسم الجامع؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Collector's name? (optional, type 'Skip' to skip)")
        return HARVEST_STATES['DELIVERY_COLLECTOR']
    else:
        await update.message.reply_text(f"تم تسجيل الحصاد بنجاح! ✅ {context.user_data['harvest_quantity']} kg" if lang == 'ar' else f"Harvest recorded! ✅ {context.user_data['harvest_quantity']} kg", reply_markup=get_main_keyboard(lang))
        return ConversationHandler.END

async def harvest_delivery_collector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    context.user_data['collector_name'] = None if text.lower() in ["تخطي", "skip"] else text
    await update.message.reply_text("إلى أي سوق؟ (اختياري، اكتب 'تخطي' للتخطي)" if lang == 'ar' else "Which market? (optional, type 'Skip' to skip)")
    return HARVEST_STATES['DELIVERY_MARKET']

async def harvest_delivery_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    farmer = farm_core.get_farmer(update.effective_user.id)
    lang = farmer['language']
    market = None if text.lower() in ["تخطي", "skip"] else text
    delivery = farm_core.record_delivery(
        harvest_id=context.user_data['harvest_id'],
        delivery_date=date.today(),
        collector_name=context.user_data.get('collector_name'),
        market=market
    )
    if delivery:
        await update.message.reply_text("تم تسجيل التسليم! ✅ الدفع متوقع خلال 7 أيام" if lang == 'ar' else "Delivery recorded! ✅ Payment expected in 7 days", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text("خطأ في تسجيل التسليم." if lang == 'ar' else "Error recording delivery.")
    return ConversationHandler.END
'''



