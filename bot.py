import os
import io
import json
import base64
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─── الإعدادات ───
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY")  # مستخدم أيضاً في HTTP مباشر
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

openai_client = OpenAI(api_key=OPENAI_KEY)
supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── المشاريع — تُحمَّل من Supabase ───
_projects_cache: list[dict] = []

_FALLBACK_PROJECTS = [
    {"name": "الظاهر 1",    "code": "MH-001"},
    {"name": "الظاهر 5",    "code": "MH-002"},
    {"name": "شعبة الوطاه", "code": "MH-003"},
]

def get_projects() -> list[dict]:
    return _projects_cache if _projects_cache else _FALLBACK_PROJECTS

async def refresh_projects() -> None:
    global _projects_cache
    try:
        result = supabase.table("projects").select("name, code").eq("status", "نشط").order("id").execute()
        if result.data:
            _projects_cache = result.data
    except Exception as e:
        logger.error(f"refresh_projects: {e}")

# ─── أدوات مساعدة ───
def clean_str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return None if s.lower() in ("none", "null", "") else s

def clean_float(val, default: float = 0.0) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return default

def escape_md(text: str | None) -> str:
    if not text:
        return ""
    for ch in ('*', '_', '`', '['):
        text = text.replace(ch, f'\\{ch}')
    return text

INVOICE_PROMPT = """
أنت محاسب خبير في شركة مقاولات إماراتية.
استخرج البيانات التالية بصيغة JSON فقط:
{
    "invoice_number": "رقم الفاتورة أو null",
    "vendor_name": "اسم المورد أو الشركة بالإنجليزي كما هو مكتوب أو null",
    "date": "التاريخ بصيغة YYYY-MM-DD أو null",
    "taxable_amount": رقم فقط بدون عملة أو null,
    "vat": رقم فقط قيمة الضريبة 5% أو null,
    "total": رقم فقط الإجمالي النهائي أو null
}
إذا لم تجد معلومة اكتب null فعلي وليس النص "null" أو "None".
أرجع JSON فقط بدون أي نص إضافي.
"""

# ─── عرض نتيجة التحليل وقائمة المشاريع (مشترك بين الصورة والـ PDF) ───
async def _show_invoice_result(update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict):
    context.user_data["pending_invoice"] = result

    inv_num   = clean_str(result.get("invoice_number")) or "غير متوفر"
    vendor    = escape_md(clean_str(result.get("vendor_name")) or "غير متوفر")
    inv_date  = result.get("date") or "غير متوفر"
    taxable   = result.get("taxable_amount") or 0
    vat_val   = result.get("vat") or 0
    total_val = result.get("total") or 0

    msg = (
        "✅ *تم تحليل الفاتورة بنجاح!*\n\n"
        f"📄 رقم الفاتورة: `{inv_num}`\n"
        f"🏢 المورد: {vendor}\n"
        f"📅 التاريخ: {inv_date}\n"
        f"💰 المبلغ الخاضع: {taxable} درهم\n"
        f"🏷️ الضريبة (5%): {vat_val} درهم\n"
        f"💵 الإجمالي: *{total_val} درهم*\n\n"
        "🏗 *اختر المشروع:*"
    )

    projects = get_projects()
    keyboard = [
        [InlineKeyboardButton(f"🏗 {p['name']}", callback_data=f"proj_{i}")]
        for i, p in enumerate(projects)
    ]
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /start ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await refresh_projects()
    welcome = (
        "🏗️ *مرحباً بك في نظام ماسترهيت للمقاولات*\n\n"
        "أنا بوت ذكي لإدارة الفواتير. إليك ما أقدر أسويه:\n\n"
        "📸 *إرسال فاتورة صورة* — JPG / PNG / WebP\n"
        "📄 *إرسال فاتورة PDF* — يُقرأ تلقائياً\n"
        "🤖 *المساعد الذكي* — اسألني عن فواتيرك\n"
        "📊 *التقرير الضريبي* — /vat\n"
        "📋 *آخر الفواتير* — /recent\n"
        "🏗 *مصروفات مشروع* — /project\n"
        "➕ *إضافة مشروع* — /addproject اسم المشروع\n\n"
        "ابدأ بإرسال صورة أو PDF فاتورة! 📸"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

# ─── /addproject ───
async def add_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "اكتب اسم المشروع بعد الأمر:\n`/addproject اسم المشروع`",
            parse_mode="Markdown"
        )
        return

    new_name = " ".join(context.args).strip()
    try:
        existing = supabase.table("projects").select("id").eq("name", new_name).execute()
        if existing.data:
            await update.message.reply_text("⚠️ هذا المشروع موجود مسبقاً.")
            return

        last = supabase.table("projects").select("id").order("id", desc=True).limit(1).execute()
        next_num = (last.data[0]["id"] + 1) if last.data else 1
        code = f"MH-{next_num:03d}"

        supabase.table("projects").insert({
            "name": new_name, "code": code,
            "status": "نشط", "client": "", "description": "",
        }).execute()

        await refresh_projects()
        await update.message.reply_text(
            f"✅ تم إضافة المشروع: *{escape_md(new_name)}* ({code})",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"add_project: {e}")
        await update.message.reply_text(f"❌ خطأ في إضافة المشروع:\n{e}")

# ─── استقبال صورة الفاتورة ───
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 جارٍ تحليل الفاتورة بالذكاء الاصطناعي...")
    await refresh_projects()

    try:
        photo = update.message.photo[-1]
        file  = await context.bot.get_file(photo.file_id)
        image_bytes  = await file.download_as_bytearray()
        base64_image = base64.b64encode(bytes(image_bytes)).decode("utf-8")

        header = bytes(image_bytes[:4])
        if header[:4] == b'\x89PNG':
            mime = "image/png"
        elif header[:4] == b'RIFF':
            mime = "image/webp"
        else:
            mime = "image/jpeg"

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": INVOICE_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64_image}"}}
                ]
            }],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        await _show_invoice_result(update, context, result)

    except Exception as e:
        logger.error(f"handle_photo: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء تحليل الفاتورة:\n`{str(e)}`",
            parse_mode="Markdown"
        )

# ─── استقبال ملف PDF ───
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if doc.mime_type != "application/pdf":
        await update.message.reply_text("⚠️ أرسل الفاتورة كصورة (JPG/PNG) أو PDF فقط.")
        return

    await update.message.reply_text("📄 جارٍ قراءة الـ PDF وتحليل الفاتورة...")
    await refresh_projects()

    try:
        import fitz  # PyMuPDF

        tg_file   = await context.bot.get_file(doc.file_id)
        pdf_bytes = bytes(await tg_file.download_as_bytearray())

        # استخراج النص بـ PyMuPDF
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = ""
        for pg in pdf_doc:
            extracted_text += pg.get_text() or ""
        pdf_doc.close()

        if len(extracted_text.strip()) < 50:
            # PDF ممسوح ضوئياً — لا نص فيه
            await update.message.reply_text(
                "⚠️ الـ PDF ممسوح ضوئياً ولا يحتوي على نص قابل للقراءة.\n\n"
                "📸 من فضلك *التقط صورة* للفاتورة وأرسلها مباشرة.",
                parse_mode="Markdown"
            )
            return

        # استدعاء OpenAI مباشرة عبر HTTP — يتجنب تحويلات الـ SDK
        import httpx
        prompt = INVOICE_PROMPT + f"\n\nنص الفاتورة:\n{extracted_text[:4000]}"
        payload = {
            "model": "gpt-4o",
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]
        }
        async with httpx.AsyncClient(timeout=60) as client_http:
            resp = await client_http.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
        resp.raise_for_status()
        result = json.loads(resp.json()["choices"][0]["message"]["content"])
        await _show_invoice_result(update, context, result)

    except Exception as e:
        logger.error(f"handle_document: {e}")
        await update.message.reply_text(
            f"❌ خطأ في تحليل الملف:\n`{str(e)}`",
            parse_mode="Markdown"
        )

# ─── اختيار المشروع ثم النوع ثم الحفظ ───
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("proj_"):
        proj_index = int(data.replace("proj_", ""))
        projects   = get_projects()
        if proj_index >= len(projects):
            await query.edit_message_text("⚠️ المشروع غير موجود، أعد إرسال الفاتورة.")
            return

        proj = projects[proj_index]
        context.user_data["selected_project"]      = proj["name"]
        context.user_data["selected_project_code"] = proj.get("code", "")

        keyboard = [
            [
                InlineKeyboardButton("📤 مصروف", callback_data="save_expense"),
                InlineKeyboardButton("📥 إيراد",  callback_data="save_revenue"),
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        await query.edit_message_text(
            f"✅ المشروع: *{escape_md(proj['name'])}*\n\nهل هذه الفاتورة مصروف أم إيراد؟",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "cancel":
        context.user_data.pop("pending_invoice",       None)
        context.user_data.pop("selected_project",      None)
        context.user_data.pop("selected_project_code", None)
        await query.edit_message_text("❌ تم إلغاء الحفظ.")
        return

    invoice      = context.user_data.get("pending_invoice")
    project_name = context.user_data.get("selected_project",      "غير محدد")
    project_code = context.user_data.get("selected_project_code", "")

    if not invoice:
        await query.edit_message_text("⚠️ لا توجد فاتورة للحفظ.")
        return

    inv_type   = "revenue" if data == "save_revenue" else "expense"
    type_label = "إيراد"   if inv_type == "revenue"  else "مصروف"

    try:
        inv_date = clean_str(invoice.get("date"))
        if inv_date:
            try:
                datetime.strptime(inv_date, "%Y-%m-%d")
            except ValueError:
                inv_date = None

        record = {
            "invoice_number": clean_str(invoice.get("invoice_number")),
            "vendor_name":    clean_str(invoice.get("vendor_name")),
            "invoice_date":   inv_date,
            "taxable_amount": clean_float(invoice.get("taxable_amount")),
            "vat_amount":     clean_float(invoice.get("vat")),
            "total_amount":   clean_float(invoice.get("total")),
            "type":           inv_type,
            "project":        project_name,
            "project_code":   project_code,
            "project_name":   project_name,
        }

        supabase.table("invoices").insert(record).execute()
        context.user_data.pop("pending_invoice",       None)
        context.user_data.pop("selected_project",      None)
        context.user_data.pop("selected_project_code", None)

        await query.edit_message_text(
            f"🎉 *تم حفظ الفاتورة بنجاح!*\n\n"
            f"📄 الرقم: `{escape_md(record['invoice_number'] or '-')}`\n"
            f"🏢 المورد: {escape_md(record['vendor_name'] or '-')}\n"
            f"🏗 المشروع: *{escape_md(project_name)}*\n"
            f"📦 النوع: {type_label}\n"
            f"💵 الإجمالي: *{record['total_amount']:,.2f} درهم*",
            parse_mode="Markdown"
        )

    except Exception as e:
        error_msg = str(e)
        if "unique_invoice" in error_msg or "duplicate" in error_msg.lower():
            await query.edit_message_text("⚠️ هذه الفاتورة مسجلة مسبقاً في النظام!")
        else:
            logger.error(f"save invoice: {e}")
            await query.edit_message_text(
                f"❌ خطأ في الحفظ:\n`{error_msg}`",
                parse_mode="Markdown"
            )

# ─── /recent ───
async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = supabase.table("invoices") \
            .select("invoice_number, vendor_name, total_amount, type, project") \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute()

        if not result.data:
            await update.message.reply_text("📭 لا توجد فواتير مسجلة بعد.")
            return

        msg = "📋 *آخر 10 فواتير:*\n\n"
        for inv in result.data:
            icon   = "📥" if inv["type"] == "revenue" else "📤"
            vendor = (inv.get("vendor_name") or "-")[:18]
            amount = f"{clean_float(inv.get('total_amount')):,.0f}"
            proj   = (inv.get("project") or "-")[:16]
            msg   += f"{icon} `{inv.get('invoice_number') or '-'}` | {vendor} | {amount} AED | {proj}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

# ─── /project ───
async def project_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await refresh_projects()
    projects = get_projects()
    keyboard = [
        [InlineKeyboardButton(f"🏗 {p['name']}", callback_data=f"rpt_{i}")]
        for i, p in enumerate(projects)
    ]
    keyboard.append([InlineKeyboardButton("📊 كل المشاريع", callback_data="rpt_all")])
    await update.message.reply_text(
        "اختر المشروع لعرض تقريره:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── معالجة تقرير المشروع ───
async def handle_project_report(query, context):
    data = query.data
    try:
        if data == "rpt_all":
            result = supabase.table("invoices").select("*").eq("type", "expense").execute()
            title  = "كل المشاريع"
        else:
            proj_index   = int(data.replace("rpt_", ""))
            projects     = get_projects()
            if proj_index >= len(projects):
                await query.edit_message_text("⚠️ المشروع غير موجود.")
                return
            project_name = projects[proj_index]["name"]
            result = supabase.table("invoices").select("*") \
                .eq("type", "expense").eq("project", project_name).execute()
            title = project_name

        if not result.data:
            await query.edit_message_text(
                f"📭 لا توجد فواتير مسجلة لـ *{title}*",
                parse_mode="Markdown"
            )
            return

        total     = sum(clean_float(inv.get("total_amount"))  for inv in result.data)
        vat_total = sum(clean_float(inv.get("vat_amount"))     for inv in result.data)
        count     = len(result.data)

        vendors: dict[str, float] = {}
        for inv in result.data:
            v = inv.get("vendor_name") or "غير معروف"
            vendors[v] = vendors.get(v, 0) + clean_float(inv.get("total_amount"))

        top_vendors  = sorted(vendors.items(), key=lambda x: x[1], reverse=True)[:5]
        vendors_text = "\n".join([f"   • {v}: {a:,.2f} AED" for v, a in top_vendors])

        msg = (
            f"📊 *تقرير مصروفات: {title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📄 عدد الفواتير: {count}\n"
            f"💰 إجمالي المصروفات: *{total:,.2f} AED*\n"
            f"🏷️ إجمالي الضريبة: {vat_total:,.2f} AED\n\n"
            f"🏢 *أكبر الموردين:*\n{vendors_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(f"❌ خطأ: {e}")

# ─── /vat ───
async def vat_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 جارٍ إعداد التقرير الضريبي...")
    try:
        result = supabase.table("invoices") \
            .select("type, taxable_amount, vat_amount, total_amount") \
            .execute()

        if not result.data:
            await update.message.reply_text("📭 لا توجد فواتير لإعداد التقرير.")
            return

        revenues = [inv for inv in result.data if inv["type"] == "revenue"]
        expenses = [inv for inv in result.data if inv["type"] == "expense"]

        rev_amount = sum(clean_float(i.get("taxable_amount")) for i in revenues)
        rev_vat    = sum(clean_float(i.get("vat_amount"))      for i in revenues)
        rev_total  = sum(clean_float(i.get("total_amount"))    for i in revenues)
        exp_amount = sum(clean_float(i.get("taxable_amount")) for i in expenses)
        exp_vat    = sum(clean_float(i.get("vat_amount"))      for i in expenses)
        exp_total  = sum(clean_float(i.get("total_amount"))    for i in expenses)
        net_vat    = rev_vat - exp_vat

        report = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏗️ *MASTER HEAT*\n"
            "*للصيانة والمقاولات العامة*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ *VAT REPORT — التقرير الضريبي*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📥 *REVENUES (الإيرادات):*\n"
            f"   AMOUNT: {rev_amount:,.2f} AED\n"
            f"   VAT 5%: {rev_vat:,.2f} AED\n"
            f"   TOTAL:  {rev_total:,.2f} AED\n\n"
            "📤 *EXPENSES (المصروفات):*\n"
            f"   AMOUNT: {exp_amount:,.2f} AED\n"
            f"   VAT 5%: {exp_vat:,.2f} AED\n"
            f"   TOTAL:  {exp_total:,.2f} AED\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏛️ *ملخص الإقرار الضريبي:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"   VAT Output: *{rev_vat:,.2f}* AED\n"
            f"   (ضريبة المخرجات)\n\n"
            f"   VAT Input:  *{exp_vat:,.2f}* AED\n"
            f"   (ضريبة المدخلات)\n\n"
            f"   ─────────────────────\n"
            f"   💰 *Net VAT Payable:*\n"
            f"   *{net_vat:,.2f} AED*\n\n"
            f"📊 فواتير الإيرادات: {len(revenues)}\n"
            f"📊 فواتير المصروفات: {len(expenses)}\n"
            f"📅 تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "_الهيئة الاتحادية للضرائب — UAE FTA_"
        )
        await update.message.reply_text(report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"vat_report: {e}")
        await update.message.reply_text(f"❌ خطأ في إعداد التقرير: {e}")

# ─── المساعد الذكي ───
async def ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text
    try:
        result = supabase.table("invoices") \
            .select("invoice_number, vendor_name, type, project, total_amount, vat_amount, invoice_date") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()

        db_context    = "لا توجد فواتير مسجلة حالياً."
        if result.data:
            db_context = json.dumps(result.data, ensure_ascii=False, default=str)

        projects_list = ", ".join(p["name"] for p in get_projects())

        system_prompt = (
            "أنت مساعد مالي ذكي ومحترف لشركة 'ماسترهيت للصيانة والمقاولات العامة' في دولة الإمارات.\n"
            f"المشاريع الحالية: {projects_list}\n\n"
            f"آخر 100 فاتورة (JSON):\n{db_context}\n\n"
            "تعليمات:\n"
            "1. أجب باختصار واحترافية بالعربية.\n"
            "2. عند السؤال عن إجمالي، أعطِ الناتج مباشرة.\n"
            "3. العملة: الدرهم الإماراتي (AED)، الضريبة 5%.\n"
            "4. للتقرير الضريبي وجّه لـ /vat، لمصروفات مشروع وجّه لـ /project"
        )

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_question}
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"ai_assistant: {e}")
        await update.message.reply_text("❌ حدث خطأ في المساعد الذكي. حاول مرة أخرى.")

# ─── معالج الأزرار الرئيسي ───
async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    if data.startswith("rpt_"):
        await query.answer()
        await handle_project_report(query, context)
    else:
        await button_callback(update, context)

# ─── تشغيل البوت ───
async def post_init(application: Application) -> None:
    await refresh_projects()
    logger.info("✅ Projects loaded on startup")

def main():
    print("MasterHeat Bot is starting...")
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("recent",     recent))
    app.add_handler(CommandHandler("vat",        vat_report))
    app.add_handler(CommandHandler("project",    project_report))
    app.add_handler(CommandHandler("addproject", add_project))
    app.add_handler(MessageHandler(filters.PHOTO,        handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(CallbackQueryHandler(main_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_assistant))

    print("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
