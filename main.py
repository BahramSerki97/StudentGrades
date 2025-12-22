import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request, abort

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])
DATABASE_URL = os.environ["DATABASE_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# ================== DB POOL ==================
db_pool = SimpleConnectionPool(
    1, 10,
    dsn=DATABASE_URL
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

# ================== INIT DB ==================
conn = get_conn()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id BIGINT PRIMARY KEY,
    name TEXT,
    family TEXT,
    student_id TEXT UNIQUE
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS grades (
    student_id TEXT,
    course TEXT,
    grade TEXT,
    UNIQUE(student_id, course)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS admins (
    telegram_id BIGINT PRIMARY KEY
)
""")

cur.execute(
    "INSERT INTO admins VALUES (%s) ON CONFLICT DO NOTHING",
    (SUPER_ADMIN_ID,)
)

conn.commit()
cur.close()
put_conn(conn)

# ================== HELPERS ==================
def is_admin(uid: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE telegram_id=%s", (uid,))
    res = cur.fetchone()
    cur.close()
    put_conn(conn)
    return res is not None

# ================== STATES ==================
NAME, FAMILY, STUDENT_ID = range(3)
ADMIN_MENU, COURSE_NAME, BULK_GRADES = range(3, 6)
EDIT_SID, EDIT_COURSE, EDIT_GRADE = range(6, 9)
DEL_SID, DEL_COURSE = range(9, 11)
DEL_ONLY_COURSE, DEL_STUDENT = 11, 12

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
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
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
        await update.message.reply_text("شماره دانشجویی تکراری است ❌")
    cur.close()
    put_conn(conn)
    return ConversationHandler.END

async def my_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT student_id FROM students WHERE telegram_id=%s",
        (update.effective_user.id,)
    )
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("ثبت نام نکرده‌اید")
        cur.close()
        put_conn(conn)
        return

    cur.execute(
        "SELECT course, grade FROM grades WHERE student_id=%s",
        (row[0],)
    )
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("نمره‌ای ثبت نشده")
    else:
        msg = "نمرات شما:\n"
        for c, g in rows:
            msg += f"{c}: {g}\n"
        await update.message.reply_text(msg)

    cur.close()
    put_conn(conn)

# ================== ADMIN ==================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("دسترسی غیرمجاز")
        return ConversationHandler.END

    kb = [
        ["➕ ثبت نمرات"],
        ["✏️ ویرایش نمره"],
        ["🗑 حذف نمره"],
        ["🗑 حذف درس"],
        ["👥 لیست دانشجوها"],
        ["🗑 حذف دانشجو"]
    ]
    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conn = get_conn()
    cur = conn.cursor()

    if text == "👥 لیست دانشجوها":
        cur.execute("SELECT student_id, name, family FROM students")
        rows = cur.fetchall()
        if not rows:
            await update.message.reply_text("دانشجویی ثبت نشده")
        else:
            msg = "دانشجوها:\n"
            for r in rows:
                msg += f"{r[0]} - {r[1]} {r[2]}\n"
            await update.message.reply_text(msg)
        cur.close()
        put_conn(conn)
        return ADMIN_MENU

    cur.close()
    put_conn(conn)
    return ConversationHandler.END

# ================== ADMIN COMMANDS ==================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(context.args[0])
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admins VALUES (%s) ON CONFLICT DO NOTHING",
            (uid,)
        )
        conn.commit()
        cur.close()
        put_conn(conn)
        await update.message.reply_text("ادمین اضافه شد ✅")
    except:
        await update.message.reply_text("فرمت: /addadmin USER_ID")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN_ID:
        return
    uid = int(context.args[0])
    if uid == SUPER_ADMIN_ID:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE telegram_id=%s", (uid,))
    conn.commit()
    cur.close()
    put_conn(conn)
    await update.message.reply_text("ادمین حذف شد 🗑")

# ================== APP ==================
app = Application.builder().token(BOT_TOKEN).build()

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

# ================== FLASK WEBHOOK ==================
flask_app = Flask(__name__)

@flask_app.route("/health")
def health():
    return "OK"

@flask_app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.json, app.bot)
    await app.process_update(update)
    return "OK"

if __name__ == "__main__":
    app.initialize()
    app.bot.set_webhook(
        url=f"https://YOUR-RENDER-URL.onrender.com/webhook/{WEBHOOK_SECRET}"
    )
    flask_app.run(host="0.0.0.0", port=10000)
