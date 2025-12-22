import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ================== CONFIG ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# ================== DATABASE ==================
db_pool = SimpleConnectionPool(
    1, 10,
    DATABASE_URL,
    sslmode="require"
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

# ================== TELEGRAM APP ==================
app_tg = Application.builder().token(BOT_TOKEN).build()

# ================== FLASK ==================
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Bot is running"

@flask_app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_tg.bot)
    app_tg.update_queue.put(update)
    return "ok"

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 لیست دانشجوها", callback_data="students")],
        [InlineKeyboardButton("📚 لیست درس‌ها", callback_data="courses")],
        [InlineKeyboardButton("📝 لیست نمره‌ها", callback_data="grades")]
    ]
    await update.message.reply_text(
        "انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== CALLBACKS ==================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "students":
        await show_students(query)
    elif data.startswith("del_student_"):
        await delete_student(query, int(data.split("_")[-1]))

    elif data == "courses":
        await show_courses(query)
    elif data.startswith("del_course_"):
        await delete_course(query, int(data.split("_")[-1]))

    elif data == "grades":
        await show_grades(query)
    elif data.startswith("del_grade_"):
        await delete_grade(query, int(data.split("_")[-1]))

# ================== STUDENTS ==================
async def show_students(query):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM students ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    put_conn(conn)

    if not rows:
        await query.edit_message_text("❌ هیچ دانشجویی ثبت نشده")
        return

    keyboard = [
        [InlineKeyboardButton(f"❌ حذف {name}", callback_data=f"del_student_{sid}")]
        for sid, name in rows
    ]

    await query.edit_message_text(
        "📋 لیست دانشجوها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_student(query, student_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
    conn.commit()
    cur.close()
    put_conn(conn)

    await query.edit_message_text("✅ دانشجو حذف شد")

# ================== COURSES ==================
async def show_courses(query):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM courses ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    put_conn(conn)

    if not rows:
        await query.edit_message_text("❌ هیچ درسی وجود ندارد")
        return

    keyboard = [
        [InlineKeyboardButton(f"❌ حذف {name}", callback_data=f"del_course_{cid}")]
        for cid, name in rows
    ]

    await query.edit_message_text(
        "📚 لیست درس‌ها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_course(query, course_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    conn.commit()
    cur.close()
    put_conn(conn)

    await query.edit_message_text("✅ درس حذف شد")

# ================== GRADES ==================
async def show_grades(query):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.id, s.name, c.name, g.grade
        FROM grades g
        JOIN students s ON g.student_id=s.id
        JOIN courses c ON g.course_id=c.id
        ORDER BY g.id
    """)
    rows = cur.fetchall()
    cur.close()
    put_conn(conn)

    if not rows:
        await query.edit_message_text("❌ نمره‌ای ثبت نشده")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"❌ {s}-{c} ({g})",
            callback_data=f"del_grade_{gid}"
        )]
        for gid, s, c, g in rows
    ]

    await query.edit_message_text(
        "📝 لیست نمره‌ها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_grade(query, grade_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM grades WHERE id=%s", (grade_id,))
    conn.commit()
    cur.close()
    put_conn(conn)

    await query.edit_message_text("✅ نمره حذف شد")

# ================== HANDLERS ==================
app_tg.add_handler(CommandHandler("start", start))
app_tg.add_handler(CallbackQueryHandler(callbacks))

# ================== RUN ==================
if __name__ == "__main__":
    app_tg.initialize()
    app_tg.start()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
