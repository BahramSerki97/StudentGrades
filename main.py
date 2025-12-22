import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 10000))

# ================= DB =================
db_pool = SimpleConnectionPool(1, 5, DATABASE_URL, sslmode="require")

def db():
    return db_pool.getconn()

def db_close(conn):
    db_pool.putconn(conn)

# ================= SECURITY =================
def is_admin(user_id: int) -> bool:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id=%s", (user_id,))
    ok = cur.fetchone()
    cur.close()
    db_close(conn)
    return ok is not None

def admin_only(func):
    async def wrapper(update, context):
        uid = update.effective_user.id
        if not is_admin(uid):
            if update.callback_query:
                await update.callback_query.answer("دسترسی نداری ❌", show_alert=True)
            else:
                await update.message.reply_text("دسترسی نداری ❌")
            return
        return await func(update, context)
    return wrapper

# ================= MENUS =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 دانشجوها", callback_data="students")],
        [InlineKeyboardButton("📚 درس‌ها", callback_data="courses")],
        [InlineKeyboardButton("📝 نمرات", callback_data="grades")],
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="back")]])

# ================= START =================
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("پنل مدیریت", reply_markup=main_menu())

# ================= STUDENTS =================
@admin_only
async def students_menu(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "مدیریت دانشجو",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ثبت دانشجو", callback_data="add_student")],
            [InlineKeyboardButton("📋 لیست دانشجوها", callback_data="list_students:0")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="back")],
        ])
    )

@admin_only
async def list_students(update, context):
    q = update.callback_query
    await q.answer()

    page = int(q.data.split(":")[1])
    limit = 5
    offset = page * limit

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, student_id, name FROM students ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM students")
    total = cur.fetchone()[0]
    cur.close()
    db_close(conn)

    if not rows:
        return await q.edit_message_text("دانشجویی وجود ندارد", reply_markup=back_menu())

    text = "\n".join([f"{r[1]} - {r[2]}" for r in rows])

    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"list_students:{page-1}"))
    if offset + limit < total:
        buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"list_students:{page+1}"))

    buttons.append(InlineKeyboardButton("⬅️ بازگشت", callback_data="students"))

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([buttons]))

# ================= CALLBACK ROUTER =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    routes = {
        "students": students_menu,
        "back": lambda u, c: start(u, c),
    }

    if data.startswith("list_students"):
        return await list_students(update, context)

    if data in routes:
        return await routes[data](update, context)

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))

    await app.bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")

    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_path=f"/{BOT_TOKEN}",
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
