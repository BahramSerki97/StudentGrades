import os
import time
import psycopg2
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]

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

# bootstrap super admin
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
        await update.message.reply_text("ثبت نام با موفقیت انجام شد ✅")
    except:
        await update.message.reply_text("این شماره دانشجویی قبلاً ثبت شده")
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
        if not rows:
            await update.message.reply_text("دانشجویی ثبت نشده")
        else:
            msg = "لیست دانشجوها:\n"
            for sid, n, f in rows:
                msg += f"{sid} - {n} {f}\n"
            await update.message.reply_text(msg)
        return ADMIN_MENU

    if text == "🗑 حذف دانشجو":
        await update.message.reply_text("شماره دانشجویی:")
        return DEL_STUDENT

# ================== ADMIN COMMANDS ==================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("دسترسی غیر مجاز")
        return

    try:
        new_admin_id = int(context.args[0])
        cursor.execute(
            "INSERT INTO admins VALUES (%s) ON CONFLICT DO NOTHING",
            (new_admin_id,)
        )
        conn.commit()
        await update.message.reply_text("ادمین جدید اضافه شد ✅")
    except:
        await update.message.reply_text("فرمت صحیح:\n/addadmin USER_ID")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("فقط سوپرادمین اجازه حذف ادمین دارد")
        return

    try:
        admin_id = int(context.args[0])
        if admin_id == SUPER_ADMIN_ID:
            await update.message.reply_text("سوپرادمین قابل حذف نیست")
            return

        cursor.execute(
            "DELETE FROM admins WHERE telegram_id=%s",
            (admin_id,)
        )
        conn.commit()
        await update.message.reply_text("ادمین حذف شد 🗑")
    except:
        await update.message.reply_text("فرمت صحیح:\n/removeadmin USER_ID")

# ================== GRADES ==================
async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["course"] = update.message.text
    context.user_data["count"] = 0
    await update.message.reply_text(
        "نمرات را ارسال کنید:\n"
        "هر خط: شماره_دانشجویی نمره\n"
        "برای پایان END را بفرستید"
    )
    return BULK_GRADES

async def bulk_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "END":
        await update.message.reply_text(
            f"پایان ثبت نمرات ✅\n"
            f"تعداد ثبت‌شده: {context.user_data['count']}"
        )
        return ConversationHandler.END

    for line in update.message.text.splitlines():
        try:
            sid, grade = line.split()
            cursor.execute(
                """
                INSERT INTO grades VALUES (%s,%s,%s)
                ON CONFLICT (student_id, course)
                DO UPDATE SET grade=EXCLUDED.grade
                """,
                (sid, context.user_data["course"], grade)
            )
            context.user_data["count"] += 1
        except:
            pass

    conn.commit()
    await update.message.reply_text("بخشی از نمرات ذخیره شد…")
    return BULK_GRADES

async def edit_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sid"] = update.message.text
    await update.message.reply_text("نام درس:")
    return EDIT_COURSE

async def edit_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["course"] = update.message.text
    await update.message.reply_text("نمره جدید:")
    return EDIT_GRADE

async def edit_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "UPDATE grades SET grade=%s WHERE student_id=%s AND course=%s",
        (update.message.text, context.user_data["sid"], context.user_data["course"])
    )
    conn.commit()
    await update.message.reply_text("نمره ویرایش شد ✅")
    return ConversationHandler.END

async def del_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sid"] = update.message.text
    await update.message.reply_text("نام درس:")
    return DEL_COURSE

async def del_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "DELETE FROM grades WHERE student_id=%s AND course=%s",
        (context.user_data["sid"], update.message.text)
    )
    conn.commit()
    await update.message.reply_text("نمره حذف شد 🗑")
    return ConversationHandler.END

async def del_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.message.text
    cursor.execute("DELETE FROM grades WHERE student_id=%s", (sid,))
    cursor.execute("DELETE FROM students WHERE student_id=%s", (sid,))
    conn.commit()
    await update.message.reply_text("دانشجو حذف شد 🗑")
    return ConversationHandler.END

async def del_whole_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "DELETE FROM grades WHERE course=%s",
        (update.message.text,)
    )
    conn.commit()
    await update.message.reply_text("درس و نمراتش حذف شد 🗑")
    return ConversationHandler.END

# ================== APP ==================
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

app.run_polling()
