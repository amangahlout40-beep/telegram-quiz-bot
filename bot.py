
import os
import sqlite3
import pandas as pd
import asyncio
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = "7986638145:AAGlVgu88PNVO-_cXSYP4ufq7PPDyx4czwY"  # BotFather token
ADMIN_ID = 5325051912
DATA_DIR = "files"
QUESTION_GAP = 5  # Har 5 question ke baad official message

os.makedirs(DATA_DIR, exist_ok=True)

# ================= OFFICIAL MESSAGE =================
OFFICIAL_MESSAGE = """✨━━━━━━━━━━━━━━━━━━✨
🎓💀🔥 STUDENTS’ UNION | OFFICIAL 🔥💀🎓
✨━━━━━━━━━━━━━━━━━━✨

⚠️ WARNING: This is NOT for time-pass students!

🎯 SSC • Railway • Banking
💣 One-Liners | Concept MCQs | PYQ Level
👉 Practice here or watch others crack the exam.

🚀 ENTER TOPPER ZONE ⬇️
▶️ YouTube — Free Classes • Killer Tricks
🔴 https://youtube.com/@students_union108

📢 Telegram — Daily Targets • PDFs • Tests
🔵 https://t.me/Students_union108

📸 Instagram | Short Tricks • Motivation
🟣 https://www.instagram.com/students_union108

💬 WhatsApp Channel | Instant Exam Alerts
🟢 https://whatsapp.com/channel/0029VbC2Une9WtC84XKJpt2O

🔥 Average minds skip. Toppers repeat.
🏆 JOIN • PRACTICE • DOMINATE
✨ STUDENTS’ UNION (OFFICIAL) ✨
"""

# Escape special characters for Telegram
OFFICIAL_MESSAGE = html.escape(OFFICIAL_MESSAGE)

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

# Channels table
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT,
    user_id INTEGER
)
""")

# Users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")
conn.commit()

# Ensure required columns exist
for col in ["first_name", "last_name", "username"]:
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
    except sqlite3.OperationalError:
        pass
conn.commit()

# ================= USER TRACKING =================
async def track_user(update: Update):
    user = update.effective_user
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (user_id, first_name, last_name, username)
        VALUES (?, ?, ?, ?)
        """, (user.id, user.first_name, user.last_name, user.username))
        conn.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    await update.message.reply_text(
        "👋 MCQ Quiz Bot Ready\n\n"
        "/setchannel <group_id>\n"
        "/channels\n"
        "/uploadcsv"
    )

# ================= CHANNEL HANDLERS =================
async def setchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    if not context.args:
        await update.message.reply_text("Usage: /setchannel -100xxxxxxxxxx")
        return
    cursor.execute(
        "INSERT INTO channels VALUES (?,?)",
        (context.args[0], update.effective_user.id)
    )
    conn.commit()
    await update.message.reply_text(f"✅ Channel added: {context.args[0]}")

async def channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    cursor.execute(
        "SELECT channel_id FROM channels WHERE user_id=?",
        (update.effective_user.id,)
    )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("❌ No channels found")
        return
    msg = "📢 Your Channels:\n" + "\n".join(f"- {r[0]}" for r in rows)
    await update.message.reply_text(msg)

# ================= CSV UPLOAD =================
async def uploadcsv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    await update.message.reply_text("📤 Please upload CSV file")

async def handle_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_user(update)
    doc = update.message.document
    if not doc.file_name.endswith(".csv"):
        await update.message.reply_text("❌ Only CSV allowed")
        return
    file = await doc.get_file()
    path = f"{DATA_DIR}/{update.effective_user.id}.csv"
    await file.download_to_drive(path)
    df = pd.read_csv(path)
    context.user_data["mcqs"] = df.to_dict("records")
    keyboard = [[InlineKeyboardButton("📢 Channel", callback_data="send_channel")]]
    await update.message.reply_text(
        f"✅ CSV uploaded successfully.\n📊 {len(df)} MCQs detected.\n\nWhere do you want to send quizzes?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await track_user(update)

    if query.data == "send_channel":
        cursor.execute("SELECT channel_id FROM channels WHERE user_id=?", (query.from_user.id,))
        rows = cursor.fetchall()
        keyboard = [[InlineKeyboardButton(r[0], callback_data=f"channel_{r[0]}")] for r in rows]
        await query.message.reply_text("Select channel to send quizzes:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("channel_"):
        channel_id = query.data.replace("channel_", "")
        mcqs = context.user_data.get("mcqs", [])
        count = 0

        for q in mcqs:
            options = [
                html.escape(str(q["option_a"])),
                html.escape(str(q["option_b"])),
                html.escape(str(q["option_c"])),
                html.escape(str(q["option_d"])),
            ]
            try:
                await context.bot.send_poll(
                    chat_id=channel_id,
                    question=html.escape(str(q["question"])),
                    options=options,
                    type="quiz",
                    correct_option_id=options.index(html.escape(str(q["correct"]))),
                    is_anonymous=False,
                )
            except Exception as e:
                print("❌ Error sending poll:", e)

            count += 1
            await asyncio.sleep(2)  # Flood control

            # Send official message every QUESTION_GAP questions
            if count % QUESTION_GAP == 0:
                await context.bot.send_message(chat_id=channel_id, text=OFFICIAL_MESSAGE, parse_mode="HTML")
                await asyncio.sleep(2)

        # Send official message at the end if last question didn't align with QUESTION_GAP
        if count % QUESTION_GAP != 0:
            await context.bot.send_message(chat_id=channel_id, text=OFFICIAL_MESSAGE, parse_mode="HTML")

        await query.message.reply_text("✅ Quizzes sent successfully")

# ================= APP =================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setchannel", setchannel))
app.add_handler(CommandHandler("channels", channels))
app.add_handler(CommandHandler("uploadcsv", uploadcsv_command))
app.add_handler(MessageHandler(filters.Document.FileExtension("csv"), handle_csv))
app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    print("🤖 Bot running...")
    app.run_polling()

