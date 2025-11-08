import os
import datetime
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---- تنظیمات ----
BOT_TOKEN = "8226892308:AAGxiXNSnhikdaR9xHhF0n4Sq4l2YxASJ34"
ADMIN_ID = 100724696  # 🔹 آیدی تلگرام ادمین را اینجا وارد کن
UPLOAD_DIR = "uploaded_excels"

# ---- متغیرهای سراسری ----
data_df = None
active_file = None  # نام فایل فعال فعلی

# ---- اطمینان از وجود پوشه ----
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- دستور شروع ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "👋 سلام ادمین عزیز!\n"
            "📤 فایل Excel بفرست تا ذخیره بشه.\n"
            "📂 /files → لیست فایل‌ها\n"
            "✅ /usefile filename.xlsx → فعال‌سازی فایل\n"
            "🔍 برای تست، عددی بفرست."
        )
    else:
        await update.message.reply_text(
            "👋 سلام! عدد مورد نظر خودت رو بفرست تا نتیجه از فایل فعال برات نمایش داده بشه."
        )


# --- آپلود فایل فقط توسط ادمین ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data_df, active_file

    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط ادمین اجازه آپلود فایل داره.")
        return

    document = update.message.document
    if not document.file_name.endswith((".xlsx", ".xls")):
        await update.message.reply_text("❌ لطفاً فقط فایل Excel بفرست (.xlsx یا .xls).")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"data_{timestamp}.xlsx"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    file = await document.get_file()
    await file.download_to_drive(file_path)

    data_df = pd.read_excel(file_path)
    active_file = file_path

    await update.message.reply_text(
        f"✅ فایل جدید `{new_filename}` ذخیره و به‌عنوان فایل فعال تنظیم شد."
    )


# --- نمایش لیست فایل‌ها فقط برای ادمین ---
async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند لیست فایل‌ها را ببیند.")
        return

    files = os.listdir(UPLOAD_DIR)
    if not files:
        await update.message.reply_text("📂 هنوز هیچ فایلی آپلود نشده.")
        return

    message = "📁 فایل‌های موجود:\n\n"
    for f in files:
        mark = "⭐" if active_file and f in active_file else "▫️"
        message += f"{mark} {f}\n"

    message += "\nبرای فعال کردن فایل بنویس:\n`/usefile filename.xlsx`"
    await update.message.reply_text(message, parse_mode="Markdown")


# --- انتخاب فایل فعال فقط برای ادمین ---
async def use_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data_df, active_file

    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط ادمین می‌تواند فایل فعال را تغییر دهد.")
        return

    if len(context.args) == 0:
        await update.message.reply_text("⚠️ لطفاً نام فایل را بنویسید.\nمثلاً: `/usefile data_20251109_235800.xlsx`", parse_mode="Markdown")
        return

    filename = context.args[0]
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        await update.message.reply_text("❌ این فایل وجود ندارد.")
        return

    data_df = pd.read_excel(file_path)
    active_file = file_path

    await update.message.reply_text(f"✅ فایل `{filename}` اکنون فعال شد.")


# --- جستجوی کاربر در فایل فعال ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global data_df, active_file

    text = update.message.text.strip()
    if data_df is None or active_file is None:
        await update.message.reply_text("⚠️ هنوز هیچ فایل فعالی تنظیم نشده است.")
        return

    try:
        query = float(text)
    except ValueError:
        await update.message.reply_text("❌ لطفاً فقط عدد ارسال کنید.")
        return

    search_col = data_df.columns[0]
    result_col = data_df.columns[1]

    matches = data_df[data_df[search_col] == query]

    if not matches.empty:
        result = str(matches.iloc[0][result_col])
        await update.message.reply_text(f"✅ نتیجه برای {query}: {result}")
    else:
        await update.message.reply_text("❌ هیچ نتیجه‌ای یافت نشد.")


# --- تابع اصلی ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("files", list_files))
    app.add_handler(CommandHandler("usefile", use_file))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
