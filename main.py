# main.py
# Telegram Bot with Admin Panel, Multi-course support, Bulk Grade Entry

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
    grade TEXT
)
""")
conn.commit()

# ================== STATES ==================
NAME, FAMILY, STUDENT_ID = range(3)
ADMIN_MENU, COURSE_NAME, BULK_GRADES = range(3, 6)

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

    keyboard = [["➕ ثبت نمرات گروهی"]]
    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "➕ ثبت نمرات گروهی":
        await update.message.reply_text("نام درس را وارد کنید:")
        return COURSE_NAME

async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['course'] = update.message.text
    await update.message.reply_text(
        "لیست نمرات را ارسال کنید به صورت:\n"
        "40123456 18\n40123457 16\n40123458 20"
    )
    return BULK_GRADES

async def bulk_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    course = context.user_data['course']
    lines = update.message.text.splitlines()
    saved = 0

    for line in lines:
        try:
            sid, grade = line.split()
            cursor.execute(
                "INSERT INTO grades VALUES (?,?,?)",
                (sid, course, grade)
            )
            saved += 1
        except:
            continue

    conn.commit()
    await update.message.reply_text(f"{saved} نمره ثبت شد ✅")
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
    },
    fallbacks=[]
))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=os.environ["WEBHOOK_URL"]
    )
