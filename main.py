# main.py
# Telegram Bot with Advanced Admin Panel
# Features:
# - Admin & Student panels
# - Multi-course support
# - Bulk grade entry in multiple messages
# - Edit grade, delete grade, delete course

import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {100724696}  # replace with real admin IDs

# ================== DATABASE ==================
conn = sqlite3.connect("grades.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
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
conn.commit()

# ================== STATES ==================
NAME, FAMILY, STUDENT_ID = range(3)
ADMIN_MENU, COURSE_NAME, BULK_GRADES = range(3, 6)
EDIT_SID, EDIT_COURSE, EDIT_GRADE = range(6, 9)
DEL_SID, DEL_COURSE = range(9, 11)
DEL_ONLY_COURSE = 11

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
            "INSERT INTO students VALUES (?,?,?,?)",
            (update.effective_user.id,
             context.user_data['name'],
             context.user_data['family'],
             update.message.text)
        )
        conn.commit()
        await update.message.reply_text("ثبت نام انجام شد ✅")
    except:
        await update.message.reply_text("شماره دانشجویی تکراری است")
    return ConversationHandler.END

async def my_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "SELECT student_id FROM students WHERE telegram_id=?",
        (update.effective_user.id,)
    )
    row = cursor.fetchone()
    if not row:
        await update.message.reply_text("ابتدا ثبت نام کنید")
        return

    cursor.execute(
        "SELECT course, grade FROM grades WHERE student_id=?",
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

    keyboard = [["➕ ثبت نمرات"], ["✏️ ویرایش نمره"], ["🗑 حذف نمره"], ["🗑 حذف درس"]]
    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ ثبت نمرات":
        await update.message.reply_text("نام درس را وارد کنید:")
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

# -------- Bulk grades (multi-message) --------
async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['course'] = update.message.text
    await update.message.reply_text(
        "نمرات را ارسال کنید (هر پیام می‌تواند چند خط باشد).\n"
        "فرمت هر خط: شماره_دانشجویی نمره\n"
        "برای پایان، کلمه END را بفرستید"
    )
    context.user_data['bulk_count'] = 0
    return BULK_GRADES

async def bulk_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "END":
        await update.message.reply_text(
            f"ثبت نمرات پایان یافت. مجموع ثبت‌شده: {context.user_data['bulk_count']}"
        )
        return ConversationHandler.END

    course = context.user_data['course']
    lines = update.message.text.splitlines()

    for line in lines:
        try:
            sid, grade = line.split()
            cursor.execute(
                "INSERT OR REPLACE INTO grades VALUES (?,?,?)",
                (sid, course, grade)
            )
            context.user_data['bulk_count'] += 1
        except:
            continue

    conn.commit()
    await update.message.reply_text("بخش دیگری از نمرات ذخیره شد…")
    return BULK_GRADES

# -------- Edit grade --------
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
        "UPDATE grades SET grade=? WHERE student_id=? AND course=?",
        (update.message.text, context.user_data['sid'], context.user_data['course'])
    )
    conn.commit()
    await update.message.reply_text("نمره ویرایش شد ✅")
    return ConversationHandler.END

# -------- Delete grade --------
async def del_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sid'] = update.message.text
    await update.message.reply_text("نام درس:")
    return DEL_COURSE

async def del_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "DELETE FROM grades WHERE student_id=? AND course=?",
        (context.user_data['sid'], update.message.text)
    )
    conn.commit()
    await update.message.reply_text("نمره حذف شد 🗑")
    return ConversationHandler.END

# -------- Delete whole course --------
async def del_whole_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "DELETE FROM grades WHERE course=?",
        (update.message.text,)
    )
    conn.commit()
    await update.message.reply_text("تمام نمرات این درس حذف شد 🗑")
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
    },
    fallbacks=[]
))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=os.environ["WEBHOOK_URL"]
    )
