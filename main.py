import os
import time
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # full url: https://xxx.onrender.com/webhook/SECRET
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])

DATABASE_URL = os.environ["DATABASE_URL"]  # Neon connection string

# ================== DATABASE (POOL) ==================
db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=5,
    dsn=DATABASE_URL,
    sslmode="require"
)

def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)

# ================== INIT TABLES ==================
def init_db():
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
    release_conn(conn)

init_db()

# ================== HELPERS ==================
def is_admin(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE telegram_id=%s", (user_id,))
    ok = cur.fetchone() is not None
    cur.close()
    release_conn(conn)
    return ok

async def send_long_message(update: Update, text: str, chunk_size: int = 4000):
    for i in range(0, len(text), chunk_size):
        await update.message.reply_text(text[i:i + chunk_size])

# ================== STATES ==================
NAME, FAMILY, STUDENT_ID = range(3)
ADMIN_MENU, COURSE_NAME, BULK_GRADES = range(3, 6)
EDIT_SID, EDIT_COURSE, EDIT_GRADE = range(6, 9)
DEL_SID, DEL_COURSE = range(9, 11)
DEL_ONLY_COURSE = 11
DEL_STUDENT = 12

# ================== STUDENT ==================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد ❌")
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام دانشجوی عزیز\n"
        "به ربات اعلام نمرات بهمن 1403 خوش اومدی ❤️\n"
        "1️⃣ از طریق دستور /register و براساس نام و نام خانوادگی و شماره دانشجویی خودت در ربات ثبت نام کن.\n"
        "(شماره دانشجوییت حتما \"اعداد انگلیسی\" باشه)\n"
        "2️⃣ پس از ثبت نام، از طریق دستور /mygrades هر زمان که نمره جدیدی اعلام بشه، آن را مشاهده کنی.\n\n"
        "⛔️ حواست باشه هر فرد فقط میتونه با یک شماره دانشجویی در ربات ثبت نام کنه."
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
        await update.message.reply_text("شماره دانشجویی تکراری است")
    cur.close()
    release_conn(conn)
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
        await update.message.reply_text("ابتدا ثبت نام کنید")
        cur.close()
        release_conn(conn)
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
    release_conn(conn)

# ================== ADMIN ==================
ADMIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["➕ ثبت نمرات"],
        ["✏️ ویرایش نمره"],
        ["🗑 حذف نمره"],
        ["🗑 حذف درس"],
        ["👥 لیست دانشجوها"],
        ["🗑 حذف دانشجو"],
        ["🔙 بازگشت به پنل"],
    ],
    resize_keyboard=True
)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("دسترسی غیرمجاز ⛔️")
        return ConversationHandler.END

    await update.message.reply_text(
        "پنل ادمین 👇",
        reply_markup=ADMIN_MENU_KEYBOARD
    )
    return ADMIN_MENU

    
    await update.message.reply_text(
        "پنل ادمین:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به پنل ادمین برگشتید 👇",
        reply_markup=ADMIN_MENU_KEYBOARD
    )
    return ADMIN_MENU

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "عملیات لغو شد ❌",
        reply_markup=ADMIN_MENU_KEYBOARD
    )
    return ADMIN_MENU

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("دسترسی غیر مجاز ⛔️")
        return ConversationHandler.END

    await update.message.reply_text(
        "پنل ادمین 👇",
        reply_markup=ADMIN_MENU_KEYBOARD
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
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT student_id, name, family
            FROM students
            ORDER BY student_id
        """)
        rows = cur.fetchall()
        cur.close()
        release_conn(conn)

        if not rows:
            await update.message.reply_text("دانشجویی ثبت نشده")
            return ADMIN_MENU

        header = "👥 لیست دانشجوها:\n\n"
        lines = []
        for i, (sid, n, f) in enumerate(rows, start=1):
            lines.append(f"{i}. {sid} - {n} {f}")

        lines.append(f"\n📊 تعداد کل دانشجوها: {len(rows)} نفر")

        await send_student_list(update, header, lines)
        return ADMIN_MENU

    if text == "🗑 حذف دانشجو":
        await update.message.reply_text("شماره دانشجویی:")
        return DEL_STUDENT

    if text == "🔙 بازگشت به پنل":
        return ADMIN_MENU

    await update.message.reply_text("گزینه نامعتبر ❗")
    return ADMIN_MENU

# ================== GRADES ==================
async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["course"] = update.message.text
    context.user_data["count"] = 0
    await update.message.reply_text(
        "هر خط: شماره_دانشجویی نمره\n"
        "برای پایان END را بفرستید"
    )
    return BULK_GRADES

async def bulk_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "END":
        await update.message.reply_text(
            f"پایان ثبت نمرات ✅\n"
            f"تعداد: {context.user_data['count']}"
        )
        return ADMIN_MENU

    conn = get_conn()
    cur = conn.cursor()

    for line in update.message.text.splitlines():
        try:
            sid, grade = line.split()
            cur.execute(
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
    cur.close()
    release_conn(conn)

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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE grades SET grade=%s WHERE student_id=%s AND course=%s",
        (update.message.text, context.user_data["sid"], context.user_data["course"])
    )
    conn.commit()
    cur.close()
    release_conn(conn)

    await update.message.reply_text("نمره ویرایش شد ✅")
    return ADMIN_MENU

async def del_sid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sid"] = update.message.text
    await update.message.reply_text("نام درس:")
    return DEL_COURSE

async def del_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM grades WHERE student_id=%s AND course=%s",
        (context.user_data["sid"], update.message.text)
    )
    conn.commit()
    cur.close()
    release_conn(conn)

    await update.message.reply_text("نمره حذف شد 🗑")
    return ADMIN_MENU

async def del_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM grades WHERE student_id=%s", (update.message.text,))
    cur.execute("DELETE FROM students WHERE student_id=%s", (update.message.text,))
    conn.commit()
    cur.close()
    release_conn(conn)

    await update.message.reply_text("دانشجو حذف شد 🗑")
    return ADMIN_MENU

async def del_whole_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM grades WHERE course=%s", (update.message.text,))
    conn.commit()
    cur.close()
    release_conn(conn)

    await update.message.reply_text("درس حذف شد 🗑")
    return ADMIN_MENU

# ================== APP ==================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mygrades", my_grades))

# ❌ این خط حذف شد
# app.add_handler(CommandHandler("admin", admin))

# ---------- REGISTER ----------
register_conv = ConversationHandler(
    entry_points=[CommandHandler("register", register)],
    states={
        NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
        ],
        FAMILY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_family)
        ],
        STUDENT_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel)
    ],
)

# ---------- ADMIN PANEL ----------
admin_conv = ConversationHandler(
    entry_points=[CommandHandler("admin", admin)],
    states={
        ADMIN_MENU: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu),
        ],

        COURSE_NAME: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_course),
        ],

        BULK_GRADES: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_grades),
        ],

        EDIT_SID: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_sid),
        ],

        EDIT_COURSE: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course),
        ],

        EDIT_GRADE: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_grade),
        ],

        DEL_SID: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, del_sid),
        ],

        DEL_COURSE: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, del_course),
        ],

        DEL_ONLY_COURSE: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, del_whole_course),
        ],

        DEL_STUDENT: [
            MessageHandler(filters.Regex("^🔙 بازگشت به پنل$"), back_to_admin),
            MessageHandler(filters.TEXT & ~filters.COMMAND, del_student),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", admin_cancel),
        CommandHandler("start", admin_cancel),
    ],
)

app.add_handler(register_conv)
app.add_handler(admin_conv)

# ================== RUN WEBHOOK ==================
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
    )
