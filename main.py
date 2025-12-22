import os
import time
import psycopg2
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]

RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
PORT = int(os.environ.get("PORT", 10000))

WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

# ================== DATABASE ==================
def get_db(retries=5, delay=2):
    for i in range(retries):
        try:
            return psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                sslmode="require"
            )
        except Exception as e:
            print(f"DB connection failed ({i+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to database")

conn = get_db()
cursor = conn.cursor()

# ================== TABLES ==================
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id BIGINT PRIMARY KEY,
    name TEXT,
    family TEXT,
    student_id TEXT UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS grades (
    student_id TEXT,
    course TEXT,
    grade TEXT,
    UNIQUE(student_id, course)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    telegram_id BIGINT PRIMARY KEY
)
""")

cursor.execute(
    "INSERT INTO admins VALUES (%s) ON CONFLICT DO NOTHING",
    (SUPER_ADMIN_ID,)
)
conn.commit()

# ================== HELPERS ==================
def is_admin(user_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM admins WHERE telegram_id=%s",
        (user_id,)
    )
    return cursor.fetchone() is not None

# ================== STATES ==================
NAME, FAMILY, STUDENT_ID = range(3)
ADMIN_MENU, COURSE_NAME, BULK_GRADES = range(3, 6)
EDIT_SID, EDIT_COURSE, EDIT_GRADE = range(6, 9)
DEL_SID, DEL_COURSE = range(9, 11)
DEL_ONLY_COURSE = 11
DEL_STUDENT = 12

# ================== STUDENT ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋\n"
        "/register ثبت نام\n"
        "/mygrades مشاهده نمرات"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("نام:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("نام خانوادگی:")
    return FAMILY

async def get_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["family"] = update.message.text
    await update.message.reply_text("شماره دانشجویی:")
    return STUDENT_ID

async def get_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute(
            "INSERT INTO students VALUES (%s,%s,%s,%s)",
            (
                update.effective_user.id,
                context.user_data["name"],
                context.user_data["family"],
                update.message.text
            )
        )
        conn.commit()
        await update.message.reply_text("ثبت نام انجام شد ✅")
    except:
        await update.message.reply_text("شماره دانشجویی تکراری است")
    return ConversationHandler.END

async def my_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "SELECT student_id FROM students WHERE telegram_id=%s",
        (update.effective_user.id,)
    )
    row = cursor.fetchone()
    if not row:
        await update.message.reply_text("ابتدا ثبت نام کنید")
        return

    cursor.execute(
        "SELECT course, grade FROM grades WHERE student_id=%s",
        (row[0],)
    )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("نمره‌ای ثبت نشده")
        return

    msg = "نمرات شما:\n"
    for c, g in rows:
        msg += f"{c}: {g}\n"
    await update.message.reply_text(msg)

# ================== ADMIN ==================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("دسترسی غیر مجاز")
        return ConversationHandler.END

    keyboard = [
        ["➕ ثبت نمرات"],
        ["✏️ ویرایش نمره"],
        ["🗑 حذف نمره"],
        ["🗑 حذف درس"],
        ["👥 لیست دانشجوها"],
        ["🗑 حذف دانشجو"]
    ]

    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

# بقیه هندلرهای ادمین و نمرات بدون تغییر باقی می‌مانند
# (همان‌هایی که خودت نوشتی)

# ================== APP (WEBHOOK - CORRECT WAY) ==================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("register", register))
app.add_handler(CommandHandler("mygrades", my_grades))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("addadmin", add_admin))
app.add_handler(CommandHandler("removeadmin", remove_admin))

app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("register", register)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        FAMILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family)],
        STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)],
    },
    fallbacks=[]
))

app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("admin", admin)],
    states={
        ADMIN_MENU: [MessageHandler(filters.TEXT, admin_menu)],
        COURSE_NAME: [MessageHandler(filters.TEXT, get_course)],
        BULK_GRADES: [MessageHandler(filters.TEXT, bulk_grades)],
        EDIT_SID: [MessageHandler(filters.TEXT, edit_sid)],
        EDIT_COURSE: [MessageHandler(filters.TEXT, edit_course)],
        EDIT_GRADE: [MessageHandler(filters.TEXT, edit_grade)],
        DEL_SID: [MessageHandler(filters.TEXT, del_sid)],
        DEL_COURSE: [MessageHandler(filters.TEXT, del_course)],
        DEL_ONLY_COURSE: [MessageHandler(filters.TEXT, del_whole_course)],
        DEL_STUDENT: [MessageHandler(filters.TEXT, del_student)],
    },
    fallbacks=[]
))

print("✅ Setting webhook...")

app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    url_path=WEBHOOK_PATH,
    webhook_url=WEBHOOK_URL
)

