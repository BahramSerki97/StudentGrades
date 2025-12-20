# main.py
# Telegram Bot with Supabase PostgreSQL (Persistent DB)
# python-telegram-bot==20.7
# psycopg2-binary required

import os
import psycopg2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ================== CONFIG ==================
TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {100724696}  # replace

DB_HOST = os.environ["SUPABASE_HOST"]
DB_NAME = os.environ["SUPABASE_DB"]
DB_USER = os.environ["SUPABASE_USER"]
DB_PASS = os.environ["SUPABASE_PASSWORD"]
DB_PORT = os.environ.get("SUPABASE_PORT", "5432")

# ================== DATABASE ==================
conn = psycopg2.connect(
    host=os.environ["SUPABASE_HOST"],
    port=os.environ["SUPABASE_PORT"],
    dbname=os.environ["SUPABASE_DB"],
    user=os.environ["SUPABASE_USER"],
    password=os.environ["SUPABASE_PASSWORD"],
    sslmode="require"
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id BIGINT PRIMARY KEY,
    name TEXT,
    family TEXT,
    student_id TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS grades (
    student_id TEXT REFERENCES students(student_id) ON DELETE CASCADE,
    course TEXT,
    grade TEXT,
    UNIQUE(student_id, course)
);
""")

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
        "سلام!\n/register ثبت نام\n/mygrades مشاهده نمرات"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("نام:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("نام خانوادگی:")
    return FAMILY

async def get_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['family'] = update.message.text
    await update.message.reply_text("شماره دانشجویی:")
    return STUDENT_ID

async def get_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute(
            "INSERT INTO students VALUES (%s,%s,%s,%s)",
            (update.effective_user.id,
             context.user_data['name'],
             context.user_data['family'],
             update.message.text)
        )
        await update.message.reply_text("ثبت نام انجام شد ✅")
    except Exception:
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
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("دسترسی غیر مجاز")
        return ConversationHandler.END

    keyboard = [["➕ ثبت نمرات"], ["✏️ ویرایش نمره"], ["🗑 حذف نمره"], ["🗑 حذف درس"], ["👥 لیست دانشجوها"], ["🗑 حذف دانشجو"]]
    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "➕ ثبت نمرات":
        await update.message.reply_text("نام درس:")
        return COURSE_NAME

    if text == "✏️ ویرایش نمره":
        await update.message.reply_text("شماره دانشجویی:")
        return EDIT_SID

    if text == "🗑 حذف نمره":
        await update.message.reply_text("شماره دانشجویی:")
        return DEL_SID

    if text == "🗑 حذف درس":
        await update.message.reply_text("نام درس:")
        return DEL_ONLY_COURSE

    if text == "👥 لیست دانشجوها":
        cursor.execute("SELECT student_id, name, family FROM students")
        rows = cursor.fetchall()
        msg = "لیست دانشجوها:\n"
        for sid, n, f in rows:
            msg += f"{sid} - {n} {f}\n"
        await update.message.reply_text(msg)
        return ADMIN_MENU

    if text == "🗑 حذف دانشجو":
        await update.message.reply_text("شماره دانشجویی:")
        return DEL_STUDENT

# -------- Bulk grades --------
async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['course'] = update.message.text
    context.user_data['count'] = 0
    await update.message.reply_text(
        "هر خط: شماره_دانشجویی نمره\nبرای پایان END"
    )
    return BULK_GRADES

async def bulk_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() == "END":
        await update.message.reply_text(f"پایان. ثبت شد: {context.user_data['count']}")
        return ConversationHandler.END

    for line in update.message.text.splitlines():
        try:
            sid, grade = line.split()
            cursor.execute(
                "INSERT INTO grades VALUES (%s,%s,%s) ON CONFLICT (student_id,course) DO UPDATE SET grade=EXCLUDED.grade",
                (sid, context.user_data['course'], grade)
            )
            context.user_data['count'] += 1
        except:
            pass

    await update.message.reply_text("ذخیره شد…")
    return BULK_GRADES

# -------- Edit / Delete --------
async def edit_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sid'] = update.message.text
    await update.message.reply_text("نام درس:")
    return EDIT_COURSE

async def edit_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['course'] = update.message.text
    await update.message.reply_text("نمره جدید:")
    return EDIT_GRADE

async def edit_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "UPDATE grades SET grade=%s WHERE student_id=%s AND course=%s",
        (update.message.text, context.user_data['sid'], context.user_data['course'])
    )
    await update.message.reply_text("ویرایش شد ✅")
    return ConversationHandler.END

async def del_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sid'] = update.message.text
    await update.message.reply_text("نام درس:")
    return DEL_COURSE

async def del_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "DELETE FROM grades WHERE student_id=%s AND course=%s",
        (context.user_data['sid'], update.message.text)
    )
    await update.message.reply_text("حذف شد 🗑")
    return ConversationHandler.END

async def del_whole_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("DELETE FROM grades WHERE course=%s", (update.message.text,))
    await update.message.reply_text("درس حذف شد 🗑")
    return ConversationHandler.END

async def del_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.message.text
    cursor.execute("DELETE FROM students WHERE student_id=%s", (sid,))
    await update.message.reply_text("دانشجو حذف شد 🗑")
    return ConversationHandler.END

# ================== APP ==================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mygrades", my_grades))

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

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=os.environ["WEBHOOK_URL"]
    )
