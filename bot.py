import os
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
DB_PATH = os.getenv("DB_PATH", "earnova.db")
MIN_WITHDRAW = Decimal(os.getenv("MIN_WITHDRAW", "500"))
WITHDRAW_METHODS = {"bkash", "nagad", "rocket"}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("earnova")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance TEXT NOT NULL DEFAULT '0',
            referred_by INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            amount TEXT NOT NULL,
            method TEXT NOT NULL,
            account TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            reward TEXT NOT NULL DEFAULT '0',
            active INTEGER NOT NULL DEFAULT 1
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO tasks(title, reward, active) VALUES (?, ?, 1)",
                [
                    ("Join our official channel (admin verification required)", "0"),
                    ("Read the task rules", "0"),
                ],
            )


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def ensure_user(tg_user, referrer_id=None):
    with connect() as db:
        row = db.execute(
            "SELECT telegram_id FROM users WHERE telegram_id=?",
            (tg_user.id,),
        ).fetchone()
        if row:
            db.execute(
                "UPDATE users SET username=?, first_name=? WHERE telegram_id=?",
                (tg_user.username or "", tg_user.first_name or "", tg_user.id),
            )
            return False
        if referrer_id == tg_user.id:
            referrer_id = None
        if referrer_id:
            valid = db.execute(
                "SELECT telegram_id FROM users WHERE telegram_id=?",
                (referrer_id,),
            ).fetchone()
            if not valid:
                referrer_id = None
        db.execute(
            """INSERT INTO users
               (telegram_id, username, first_name, balance, referred_by, created_at)
               VALUES (?, ?, ?, '0', ?, ?)""",
            (tg_user.id, tg_user.username or "", tg_user.first_name or "",
             referrer_id, now_iso()),
        )
        return True


def get_user(user_id):
    with connect() as db:
        return db.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,)).fetchone()


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Wallet", callback_data="wallet"),
         InlineKeyboardButton("📋 Tasks", callback_data="tasks")],
        [InlineKeyboardButton("👥 Referral", callback_data="referral"),
         InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("📜 History", callback_data="history"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referrer = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_") and arg[4:].isdigit():
            referrer = int(arg[4:])
    ensure_user(update.effective_user, referrer)
    text = (
        f"স্বাগতম {update.effective_user.first_name or 'বন্ধু'}! 👋\n\n"
        "এটি Earnova bot-এর প্রাথমিক সংস্করণ।\n"
        "নিচের মেনু থেকে Wallet, Tasks, Referral ও Withdraw ব্যবহার করো।\n\n"
        "সতর্কতা: এখানে এখনো বাস্তব বিজ্ঞাপন-রিওয়ার্ড বা স্বয়ংক্রিয় পেমেন্ট চালু নেই।"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard())


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    ensure_user(q.from_user)

    if q.data == "wallet":
        user = get_user(user_id)
        await q.edit_message_text(
            f"💰 তোমার ব্যালেন্স: ৳{Decimal(user['balance']):.2f}\n\n"
            "এই বেসিক সংস্করণে কোনো ভুয়া reward যোগ করা হয় না।",
            reply_markup=main_keyboard()
        )
    elif q.data == "tasks":
        with connect() as db:
            rows = db.execute("SELECT id, title, reward FROM tasks WHERE active=1").fetchall()
        text = "📋 Available tasks:\n\n"
        text += "\n".join(f"{r['id']}. {r['title']} — reward ৳{Decimal(r['reward']):.2f}" for r in rows)
        text += "\n\nটাস্ক সম্পন্ন করলেই নিজে নিজে টাকা যোগ হবে না; admin verification পরে যুক্ত করতে হবে।"
        await q.edit_message_text(text, reply_markup=main_keyboard())
    elif q.data == "referral":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{user_id}"
        await q.edit_message_text(
            f"👥 তোমার referral link:\n{link}\n\n"
            "শুধু নতুন user /start করলে referral source সংরক্ষিত হয়। "
            "এখনো referral bonus চালু করা হয়নি।",
            reply_markup=main_keyboard()
        )
    elif q.data == "withdraw":
        user = get_user(user_id)
        await q.edit_message_text(
            f"💸 Minimum withdrawal: ৳{MIN_WITHDRAW:.2f}\n"
            f"তোমার balance: ৳{Decimal(user['balance']):.2f}\n\n"
            "আবেদন করতে লিখো:\n"
            "/withdraw 500 bkash 01XXXXXXXXX\n\n"
            "Method: bkash, nagad বা rocket। "
            "এটি শুধু pending request তৈরি করবে; টাকা পাঠাবে না।",
            reply_markup=main_keyboard()
        )
    elif q.data == "history":
        with connect() as db:
            rows = db.execute(
                "SELECT kind, amount, note, created_at FROM transactions "
                "WHERE telegram_id=? ORDER BY id DESC LIMIT 10", (user_id,)
            ).fetchall()
            withdrawals = db.execute(
                "SELECT amount, method, status, created_at FROM withdrawals "
                "WHERE telegram_id=? ORDER BY id DESC LIMIT 5", (user_id,)
            ).fetchall()
        text = "📜 Recent transactions:\n"
        text += "\n".join(
            f"{r['kind']} ৳{Decimal(r['amount']):.2f} — {r['note']}"
            for r in rows
        ) or "এখনো কোনো transaction নেই।"
        text += "\n\nWithdrawal requests:\n"
        text += "\n".join(
            f"#{r['created_at'][:10]} ৳{Decimal(r['amount']):.2f} {r['method']} — {r['status']}"
            for r in withdrawals
        ) or "এখনো কোনো withdrawal request নেই।"
        await q.edit_message_text(text, reply_markup=main_keyboard())
    else:
        await q.edit_message_text(
            "ℹ️ Help: /start, /wallet, /tasks, /withdraw, /cancel\n"
            "Admin: /admin এবং /pending (শুধু অনুমোদিত admin)",
            reply_markup=main_keyboard()
        )


async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Balance: ৳{Decimal(user['balance']):.2f}")


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    with connect() as db:
        rows = db.execute("SELECT id, title, reward FROM tasks WHERE active=1").fetchall()
    if not rows:
        await update.message.reply_text("এখন কোনো task নেই।")
        return
    text = "📋 Tasks:\n" + "\n".join(
        f"{r['id']}. {r['title']} — ৳{Decimal(r['reward']):.2f}" for r in rows
    )
    await update.message.reply_text(text)


async def withdraw_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    if len(context.args) != 3:
        await update.message.reply_text(
            "Format: /withdraw 500 bkash 01XXXXXXXXX\n"
            "Method: bkash, nagad, rocket"
        )
        return
    try:
        amount = Decimal(context.args[0])
        if not amount.is_finite() or amount <= 0 or amount.quantize(Decimal("0.01")) != amount:
            raise InvalidOperation
    except InvalidOperation:
        await update.message.reply_text("সঠিক amount দাও, যেমন: /withdraw 500 bkash 01XXXXXXXXX")
        return
    method = context.args[1].lower()
    account = context.args[2].strip()
    if method not in WITHDRAW_METHODS:
        await update.message.reply_text("Method শুধু bkash, nagad বা rocket হতে পারে।")
        return
    if not (account.isdigit() and 10 <= len(account) <= 15):
        await update.message.reply_text("Account number ঠিকভাবে দাও।")
        return
    with connect() as db:
        user = db.execute("SELECT balance FROM users WHERE telegram_id=?",
                          (update.effective_user.id,)).fetchone()
        balance = Decimal(user["balance"])
        if amount < MIN_WITHDRAW:
            await update.message.reply_text(f"Minimum withdrawal ৳{MIN_WITHDRAW:.2f}")
            return
        if amount > balance:
            await update.message.reply_text(f"পর্যাপ্ত balance নেই। তোমার balance ৳{balance:.2f}")
            return
        cur = db.execute(
            "INSERT INTO withdrawals(telegram_id, amount, method, account, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (update.effective_user.id, str(amount), method, account, now_iso()),
        )
        request_id = cur.lastrowid
    await update.message.reply_text(
        f"✅ Withdrawal request জমা হয়েছে। Request ID: #{request_id}\n"
        f"Amount: ৳{amount:.2f}\nStatus: pending\n"
        "Admin review না করা পর্যন্ত balance থেকে টাকা কাটা হবে না।"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"New withdrawal #{request_id}\nUser: {update.effective_user.id}\n"
                f"Amount: ৳{amount:.2f}\nMethod: {method}\nAccount: {account}\n"
                f"Approve: /approve {request_id}\nReject: /reject {request_id}"
            )
        except Exception:
            log.exception("Could not notify admin %s", admin_id)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("এই command শুধু admin-এর জন্য।")
        return
    await update.message.reply_text(
        "Admin commands:\n"
        "/pending — pending withdrawals\n"
        "/approve REQUEST_ID — approve and deduct balance\n"
        "/reject REQUEST_ID — reject request\n"
        "/credit TELEGRAM_ID AMOUNT NOTE — manual test/admin credit\n"
        "/stats — basic stats"
    )


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("শুধু admin ব্যবহার করতে পারবে।")
        return
    with connect() as db:
        rows = db.execute(
            "SELECT id, telegram_id, amount, method, account, created_at "
            "FROM withdrawals WHERE status='pending' ORDER BY id"
        ).fetchall()
    if not rows:
        await update.message.reply_text("কোনো pending request নেই।")
        return
    await update.message.reply_text("\n\n".join(
        f"#{r['id']} user={r['telegram_id']} ৳{Decimal(r['amount']):.2f} "
        f"{r['method']} {r['account']}\n/approve {r['id']} | /reject {r['id']}"
        for r in rows
    ))


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("শুধু admin ব্যবহার করতে পারবে।")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("ব্যবহার: /approve REQUEST_ID")
        return
    request_id = int(context.args[0])
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        req = db.execute("SELECT * FROM withdrawals WHERE id=?", (request_id,)).fetchone()
        if not req or req["status"] != "pending":
            await update.message.reply_text("Request পাওয়া যায়নি বা আগে process করা হয়েছে।")
            return
        user = db.execute("SELECT balance FROM users WHERE telegram_id=?",
                          (req["telegram_id"],)).fetchone()
        amount = Decimal(req["amount"])
        balance = Decimal(user["balance"])
        if balance < amount:
            await update.message.reply_text("User balance কম; request approve করা হয়নি।")
            return
        new_balance = balance - amount
        db.execute("UPDATE users SET balance=? WHERE telegram_id=?",
                   (str(new_balance), req["telegram_id"]))
        db.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (request_id,))
        db.execute(
            "INSERT INTO transactions(telegram_id, kind, amount, note, created_at) "
            "VALUES (?, 'withdrawal', ?, ?, ?)",
            (req["telegram_id"], str(amount), f"Withdrawal #{request_id} approved", now_iso())
        )
    await update.message.reply_text(f"Request #{request_id} approved. Balance deducted.")
    try:
        await context.bot.send_message(
            req["telegram_id"],
            f"Withdrawal request #{request_id} approved by admin. "
            "এটি টাকা পাঠানোর নিশ্চয়তা নয়; পেমেন্ট আলাদাভাবে পাঠাতে হবে।"
        )
    except Exception:
        pass


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("শুধু admin ব্যবহার করতে পারবে।")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("ব্যবহার: /reject REQUEST_ID")
        return
    request_id = int(context.args[0])
    with connect() as db:
        cur = db.execute(
            "UPDATE withdrawals SET status='rejected' "
            "WHERE id=? AND status='pending'", (request_id,)
        )
        if cur.rowcount == 0:
            await update.message.reply_text("Request পাওয়া যায়নি বা আগে process করা হয়েছে।")
            return
        req = db.execute("SELECT telegram_id FROM withdrawals WHERE id=?", (request_id,)).fetchone()
    await update.message.reply_text(f"Request #{request_id} rejected.")
    try:
        await context.bot.send_message(req["telegram_id"], f"Withdrawal request #{request_id} rejected.")
    except Exception:
        pass


async def credit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("শুধু admin ব্যবহার করতে পারবে।")
        return
    if len(context.args) < 3 or not context.args[0].isdigit():
        await update.message.reply_text("ব্যবহার: /credit TELEGRAM_ID AMOUNT NOTE")
        return
    target_id = int(context.args[0])
    try:
        amount = Decimal(context.args[1])
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except InvalidOperation:
        await update.message.reply_text("সঠিক positive amount দাও।")
        return
    note = " ".join(context.args[2:])[:200]
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        user = db.execute("SELECT balance FROM users WHERE telegram_id=?", (target_id,)).fetchone()
        if not user:
            await update.message.reply_text("User নেই। তাকে আগে /start করতে হবে।")
            return
        new_balance = Decimal(user["balance"]) + amount
        db.execute("UPDATE users SET balance=? WHERE telegram_id=?", (str(new_balance), target_id))
        db.execute(
            "INSERT INTO transactions(telegram_id, kind, amount, note, created_at) "
            "VALUES (?, 'admin_credit', ?, ?, ?)",
            (target_id, str(amount), note, now_iso())
        )
    await update.message.reply_text(f"Credit added: user {target_id}, ৳{amount:.2f}")
    try:
        await context.bot.send_message(target_id, f"Admin credit: ৳{amount:.2f}\nNote: {note}")
    except Exception:
        pass


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("শুধু admin ব্যবহার করতে পারবে।")
        return
    with connect() as db:
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pending = db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'").fetchone()[0]
        total_balance = sum(Decimal(r["balance"]) for r in db.execute("SELECT balance FROM users"))
    await update.message.reply_text(
        f"Users: {users}\nPending withdrawals: {pending}\n"
        f"Total displayed balance: ৳{total_balance:.2f}"
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("কোনো চলমান ধাপ নেই। Menu দেখতে /start দাও।")


async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "আমি এই মেসেজটি বুঝতে পারিনি। /start লিখে মেনু দেখো।"
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit("ERROR: BOT_TOKEN environment variable set করো।")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("withdraw", withdraw_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(CommandHandler("credit", credit_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CallbackQueryHandler(menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))
    log.info("Earnova bot starting with polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
