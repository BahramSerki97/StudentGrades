import os
import sqlite3
from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {100724696}

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
GRADE_STUDENT_ID, GRADE_COURSE, GRADE_VALUE = range(3, 6)

# ================== BOT LOGIC ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! برای ثبت نام /register را بزنید")

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
            "INSERT INTO students VALUES (?,?,?,?)",
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
        await update.message.reply_text("این شماره قبلاً ثبت شده")
    return ConversationHandler.END

async def add_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("دسترسی غیرمجاز")
        return ConversationHandler.END
    await update.message.reply_text("شماره دانشجویی:")
    return GRADE_STUDENT_ID

async def grade_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sid"] = update.message.text
    await update.message.reply_text("نام درس:")
    return GRADE_COURSE

async def grade_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["course"] = update.message.text
    await update.message.reply_text("نمره:")
    return GRADE_VALUE

async def grade_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "INSERT INTO grades VALUES (?,?,?)",
        (
            context.user_data["sid"],
            context.user_data["course"],
            update.message.text
        )
    )
    conn.commit()
    await update.message.reply_text("نمره ثبت شد ✅")
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

# ================== APPLICATION ==================
def build_app() -> Application:
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
        entry_points=[CommandHandler("addgrade", add_grade)],
        states={
            GRADE_STUDENT_ID: [MessageHandler(filters.TEXT, grade_student_id)],
            GRADE_COURSE: [MessageHandler(filters.TEXT, grade_course)],
            GRADE_VALUE: [MessageHandler(filters.TEXT, grade_value)],
        },
        fallbacks=[]
    ))

    return app

# ================== WEBHOOK RUN ==================
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    application = build_app()

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=os.environ["WEBHOOK_URL"]
    )
