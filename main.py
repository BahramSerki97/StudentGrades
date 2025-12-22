import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

# ================== DB POOL ==================
db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=5,
    dsn=DATABASE_URL,
    sslmode="require"
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        telegram_id BIGINT PRIMARY KEY,
        name TEXT,
        student_id TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS grades (
        student_id TEXT,
        course TEXT,
        grade TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        telegram_id BIGINT PRIMARY KEY
    );
    """)

    conn.commit()
    cur.close()
    put_conn(conn)

# ================== ADMIN UTILS ==================
def is_admin(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE telegram_id=%s", (user_id,))
    result = cur.fetchone()
    cur.close()
    put_conn(conn)
    return result is not None

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ربات فعال است ✅")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ دسترسی نداری")

    if not context.args:
        return await update.message.reply_text("Usage: /addadmin TELEGRAM_ID")

    admin_id = int(context.args[0])
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admins (telegram_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (admin_id,)
    )
    conn.commit()
    cur.close()
    put_conn(conn)

    await update.message.reply_text("✅ ادمین اضافه شد")

async def del_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ دسترسی نداری")

    if not context.args:
        return await update.message.reply_text("Usage: /deladmin TELEGRAM_ID")

    admin_id = int(context.args[0])
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE telegram_id=%s", (admin_id,))
    conn.commit()
    cur.close()
    put_conn(conn)

    await update.message.reply_text("🗑 ادمین حذف شد")

# ================== TELEGRAM APP ==================
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("addadmin", add_admin))
application.add_handler(CommandHandler("deladmin", del_admin))

# ================== FLASK ==================
app = Flask(__name__)

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK"

@app.route("/")
def health():
    return "Bot is running"

# ================== MAIN ==================
if __name__ == "__main__":
    init_db()

    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL,
    )
