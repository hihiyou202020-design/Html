import os
import sys
import re
import time
import base64
import sqlite3
import asyncio
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    Application
)
from telegram.error import BadRequest

# ================= Configuration =================
BOT_TOKEN = "8783295110:AAHDUliolZ07YZoCa7mGyXs1tCx5Ga5Q1Yk"
ADMIN_ID = 7151641035

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= Security & Encryption =================
SECRET_KEY = "premium_mail_bot_secret_2025"

def encrypt_password(text: str) -> str:
    xored = ''.join(chr(ord(c) ^ ord(SECRET_KEY[i % len(SECRET_KEY)])) for i, c in enumerate(text))
    return base64.b64encode(xored.encode()).decode()

def decrypt_password(text: str) -> str:
    decoded = base64.b64decode(text.encode()).decode()
    return ''.join(chr(ord(c) ^ ord(SECRET_KEY[i % len(SECRET_KEY)])) for i, c in enumerate(decoded))

# ================= Database Setup =================
def init_db():
    conn = sqlite3.connect("premium_bot.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_banned INTEGER DEFAULT 0
        )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except sqlite3.OperationalError:
        pass
        
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT,
            password TEXT
        )
    """)
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

def check_ban_and_register(user_id: int, username: str) -> bool:
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()
        return bool(row[0])
        
    cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    return False

# ================= FSM States =================
(
    GET_NEW_EMAIL, GET_NEW_PASS, 
    GET_UPDATE_PASS, 
    SEND_RECEIVER, SEND_SUBJECT, SEND_HTML, CONFIRM_EMAIL,
    ADMIN_BROADCAST, ADMIN_BAN, ADMIN_UNBAN
) = range(10)

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Send HTML Email", callback_data="menu_send")],
        [InlineKeyboardButton("📧 My Emails", callback_data="menu_myemails"),
         InlineKeyboardButton("➕ Add Email", callback_data="menu_addemail")]
    ])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]])

# ================= Email Logic =================
def verify_smtp_sync(email: str, password: str) -> bool:
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.login(email, password)
        return True
    except Exception:
        return False

async def verify_smtp(email: str, password: str) -> bool:
    return await asyncio.to_thread(verify_smtp_sync, email, password)

def send_email_sync(sender: str, pwd: str, to: str, sub: str, html: str) -> tuple:
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = sub
        msg['From'] = sender
        msg['To'] = to
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(sender, pwd)
            server.send_message(msg)
        return True, "✅ Email sent successfully!"
    except Exception as e:
        return False, f"❌ Failed to send email:\n{str(e)}"

async def send_email_async(sender: str, pwd: str, to: str, sub: str, html: str) -> tuple:
    return await asyncio.to_thread(send_email_sync, sender, pwd, to, sub, html)

# ================= Command Handlers =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    if check_ban_and_register(user.id, username):
        return await update.message.reply_text("🚫 You are banned from using this bot.")
    
    text = (
        "👋 Welcome to the <b>Premium HTML Mail Sender</b>!\n\n"
        "✨ <b>Features:</b>\n"
        "🔒 <b>Secure Storage:</b> Your passwords are fully encrypted\n"
        "⚡ <b>Fast Delivery:</b> High-speed email sending\n"
        "🎨 <b>Custom HTML:</b> Full support for HTML templates\n\n"
        "💡 <i>If you need help, type /help.</i>\n"
        "👨‍💻 <b>Bot Creator:</b> @Anik7660\n\n"
        "Select an option from the menu below:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_kb(), parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu_kb(), parse_mode='HTML')
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛠 <b>How to use the bot?</b>\n\n"
        "<b>1. How to get the App Password?</b>\n"
        "• Ensure <b>2-Step Verification</b> is enabled on your Gmail.\n"
        "• Go to Manage your Google Account -> Search 'App Password' -> Sign in with app password -> Click on 'Create and manage your app password'.\n"
        "• Log in to the Gmail account you want to use.\n"
        "• Enter your app name (e.g., 'My app') and click Create.\n"
        "• You will get a 16-digit App Password.\n"
        "<i>(Copy the password and send it to the bot without any spaces)</i>\n\n"
        "<b>2. How to send an email:</b>\n"
        "• Click ➕ Add Email to save your Gmail and App Password.\n"
        "• Click '🚀 Send HTML Email', then enter the recipient's email, subject, and your HTML code.\n\n"
        "📞 <b>For any support or help, contact:</b> @Anik7660"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Action cancelled.", reply_markup=main_menu_kb())
    context.user_data.clear()
    return ConversationHandler.END

# ================= Add Email Flow =================
async def menu_addemail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = f"@{user.username}" if user.username else user.first_name
    if check_ban_and_register(user.id, username): return
    
    await query.edit_message_text("📧 <b>Step 1/2:</b> Enter your <b>Gmail Address</b>:", reply_markup=cancel_kb(), parse_mode='HTML')
    return GET_NEW_EMAIL

async def get_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if not re.match(r'^[a-zA-Z0-9_.+-]+@gmail\.com$', email):
        await update.message.reply_text("⚠️ Please enter a valid @gmail.com address:", reply_markup=cancel_kb())
        return GET_NEW_EMAIL
    context.user_data['new_email'] = email
    await update.message.reply_text(
        "🔑 <b>Step 2/2:</b> Enter your <b>16-digit App Password</b>:\n"
        "<i>(For your security, this message will be deleted after you send it)</i>", 
        reply_markup=cancel_kb(), parse_mode='HTML'
    )
    return GET_NEW_PASS

async def get_new_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip().replace(" ", "")
    email = context.user_data.get('new_email')
    user_id = update.effective_user.id
    try: await update.message.delete()
    except BadRequest: pass

    wait_msg = await update.message.reply_text("⏳ <i>Verifying account...</i>", parse_mode='HTML')
    if await verify_smtp(email, password):
        enc_pass = encrypt_password(password)
        cursor.execute("INSERT INTO emails (user_id, email, password) VALUES (?, ?, ?)", (user_id, email, enc_pass))
        conn.commit()
        await wait_msg.edit_text(f"✅ <b>Success!</b> {email} has been saved.", reply_markup=main_menu_kb(), parse_mode='HTML')
    else:
        await wait_msg.edit_text("❌ <b>Login Failed!</b> Incorrect App Password.\n<i>(Type /help for instructions)</i>", reply_markup=cancel_kb(), parse_mode='HTML')
    return ConversationHandler.END

# ================= Update Password Flow =================
async def ask_update_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    em_id = query.data.split("_")[2]
    context.user_data['update_em_id'] = em_id
    await query.edit_message_text(
        "🔄 <b>Update Password:</b>\nEnter your <b>new 16-digit App Password</b> for this email:", 
        reply_markup=cancel_kb(), parse_mode='HTML'
    )
    return GET_UPDATE_PASS

async def do_update_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_pass = update.message.text.strip().replace(" ", "")
    em_id = context.user_data.get('update_em_id')
    user_id = update.effective_user.id
    try: await update.message.delete()
    except BadRequest: pass

    cursor.execute("SELECT email FROM emails WHERE id = ? AND user_id = ?", (em_id, user_id))
    row = cursor.fetchone()
    if not row:
        await update.message.reply_text("❌ Email not found!", reply_markup=main_menu_kb())
        return ConversationHandler.END
        
    email = row[0]
    wait_msg = await update.message.reply_text("⏳ <i>Verifying new password...</i>", parse_mode='HTML')
    if await verify_smtp(email, new_pass):
        enc_pass = encrypt_password(new_pass)
        cursor.execute("UPDATE emails SET password = ? WHERE id = ? AND user_id = ?", (enc_pass, em_id, user_id))
        conn.commit()
        await wait_msg.edit_text("✅ <b>Success!</b> Password has been updated.", reply_markup=main_menu_kb(), parse_mode='HTML')
    else:
        await wait_msg.edit_text("❌ <b>Login Failed!</b> Incorrect App Password.", reply_markup=cancel_kb(), parse_mode='HTML')
    return ConversationHandler.END

# ================= My Emails Flow =================
async def menu_myemails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cursor.execute("SELECT id, email FROM emails WHERE user_id = ?", (user_id,))
    emails = cursor.fetchall()
    if not emails:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add New Email", callback_data="menu_addemail")]])
        return await query.edit_message_text("You don't have any saved emails.", reply_markup=kb)
        
    buttons = [[InlineKeyboardButton(f"📧 {em[1]}", callback_data=f"manage_em_{em[0]}")] for em in emails]
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
    await query.edit_message_text("📋 <b>Your Saved Emails:</b>\n<i>Click an email to manage it</i>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

async def manage_single_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    em_id = query.data.split("_")[2]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Send Mail with this", callback_data=f"use_em_{em_id}")],
        [InlineKeyboardButton("🔄 Update Password", callback_data=f"update_pass_{em_id}")],
        [InlineKeyboardButton("❌ Remove Email", callback_data=f"del_em_{em_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_myemails")]
    ])
    await query.edit_message_text("⚙️ <b>Email Options:</b>", reply_markup=kb, parse_mode='HTML')

async def delete_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    em_id = query.data.split("_")[2]
    cursor.execute("DELETE FROM emails WHERE id = ? AND user_id = ?", (em_id, query.from_user.id))
    conn.commit()
    await query.answer("Email Removed!")
    await menu_myemails(update, context)

# ================= Send Email Flow =================
async def menu_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = f"@{user.username}" if user.username else user.first_name
    if check_ban_and_register(user.id, username): return
    
    cursor.execute("SELECT id, email FROM emails WHERE user_id = ?", (user.id,))
    emails = cursor.fetchall()
    if not emails:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add Email", callback_data="menu_addemail")]])
        await query.edit_message_text("⚠️ Please add an email account first.", reply_markup=kb)
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(f"[ {em[1]} ]", callback_data=f"use_em_{em[0]}")] for em in emails]
    buttons.append([InlineKeyboardButton("➕ Add New Email", callback_data="menu_addemail")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")])
    await query.edit_message_text("📧 <b>Select Sender:</b>\nChoose the email you want to send from:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')

async def use_email_for_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    em_id = query.data.split("_")[2]
    context.user_data['sender_id'] = em_id
    context.user_data['prompt_msg_id'] = query.message.message_id
    await query.edit_message_text("👤 <b>Receiver Email:</b>\nEnter the recipient's email address:", reply_markup=cancel_kb(), parse_mode='HTML')
    return SEND_RECEIVER

async def get_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    chat_id = update.effective_chat.id
    msg_id = context.user_data.get('prompt_msg_id')
    try: await update.message.delete()
    except: pass

    if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="⚠️ Please enter a valid email address:\n(e.g., user@example.com)", reply_markup=cancel_kb())
        return SEND_RECEIVER
    
    context.user_data['receiver'] = email
    await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="📝 <b>Subject:</b>\nEnter the email subject:", reply_markup=cancel_kb(), parse_mode='HTML')
    return SEND_SUBJECT

async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['subject'] = update.message.text
    chat_id = update.effective_chat.id
    msg_id = context.user_data.get('prompt_msg_id')
    try: await update.message.delete()
    except: pass

    # এখানে ফাইল আপলোড করার নির্দেশনা যোগ করা হয়েছে
    text = (
        "💻 <b>HTML Body:</b>\n"
        "Enter your HTML code directly <b>OR</b>\n"
        "📁 Upload a <code>.txt</code> or <code>.html</code> file for large templates:"
    )
    await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=cancel_kb(), parse_mode='HTML')
    return SEND_HTML

async def get_html_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg_id = context.user_data.get('prompt_msg_id')

    # যদি ইউজার ফাইল আপলোড করে (Document Handle)
    if update.message.document:
        doc = update.message.document
        if not (doc.file_name.endswith('.txt') or doc.file_name.endswith('.html')):
            await update.message.reply_text("⚠️ Invalid file! Please upload a .txt or .html file.", reply_markup=cancel_kb())
            return SEND_HTML
        
        wait_msg = await update.message.reply_text("⏳ <i>Reading your file...</i>", parse_mode='HTML')
        file = await context.bot.get_file(doc.file_id)
        
        # ফাইলটি পড়ে HTML টেক্সট বের করা হচ্ছে
        byte_array = await file.download_as_bytearray()
        html_content = byte_array.decode('utf-8')
        context.user_data['html'] = html_content
        
        try: await wait_msg.delete()
        except: pass

    # যদি ইউজার সরাসরি টেক্সট লিখে দেয়
    elif update.message.text:
        context.user_data['html'] = update.message.text

    else:
        return SEND_HTML # ছবি বা অন্য কিছু দিলে ইগনোর করবে

    try: await update.message.delete()
    except: pass
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])
    d = context.user_data
    summary = f"📋 <b>Summary:</b>\n\n<b>To:</b> {d['receiver']}\n<b>Sub:</b> {d['subject']}\n\n<i>Confirm to send:</i>"
    
    await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=summary, reply_markup=kb, parse_mode='HTML')
    return CONFIRM_EMAIL

async def confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    
    cursor.execute("SELECT email, password FROM emails WHERE id = ? AND user_id = ?", (d['sender_id'], query.from_user.id))
    row = cursor.fetchone()
    if not row:
        await query.edit_message_text("❌ Error: Sender not found.", reply_markup=main_menu_kb())
        return ConversationHandler.END
        
    sender_email, enc_pwd = row
    password = decrypt_password(enc_pwd)

    send_task = asyncio.create_task(send_email_async(sender_email, password, d['receiver'], d['subject'], d['html']))
    frames = ["[▒▒▒▒▒▒▒▒▒▒▒▒]", "[██▒▒▒▒▒▒▒▒▒▒]", "[████▒▒▒▒▒▒▒▒]", "[██████▒▒▒▒▒▒]", "[████████▒▒▒▒]", "[██████████▒▒]", "[████████████]"]
    i = 0
    
    while not send_task.done():
        frame = frames[i % len(frames)]
        try:
            await query.edit_message_text(
                f"🚀 <b>Sending Email...</b>\n\nPlease wait...\n{frame}", 
                parse_mode='HTML'
            )
        except BadRequest:
            pass 
        i += 1
        await asyncio.sleep(0.6)
        
    success, result = send_task.result()
    await query.edit_message_text(f"{result}", reply_markup=main_menu_kb())
    context.user_data.clear()
    return ConversationHandler.END

# ================= Admin Panel =================
async def menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.message: return await update.message.reply_text("⛔ Access Denied.")
        else:
            await update.callback_query.answer()
            return await update.callback_query.edit_message_text("⛔ Access Denied.")
        
    cursor.execute("SELECT COUNT(*) FROM users")
    u_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM emails")
    e_count = cursor.fetchone()[0]
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"), InlineKeyboardButton("✅ Unban", callback_data="admin_unban")],
        [InlineKeyboardButton("🔙 Back to Home", callback_data="back_home")]
    ])
    text = f"👑 <b>Admin Dashboard</b>\n\n👥 Total Users: {u_count}\n📧 Saved Emails: {e_count}\n\n<i>(To upgrade bot, simply send the new .py file here)</i>"
    
    if update.message: await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode='HTML')
    return ConversationHandler.END

async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT user_id, username, is_banned FROM users")
    users = cursor.fetchall()
    if not users:
        await query.edit_message_text("No users found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]))
        return

    text = "👥 <b>Users List:</b>\n\n"
    for idx, (uid, uname, banned) in enumerate(users, 1):
        status = "🚫 Banned" if banned else "✅ Active"
        display_name = uname if uname else "Unknown"
        text += f"{idx}. <code>{uid}</code> | {display_name} - {status}\n"
        
    if len(text) > 4000:
        file_path = "users_list.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            for idx, (uid, uname, banned) in enumerate(users, 1):
                status = "Banned" if banned else "Active"
                display_name = uname if uname else "Unknown"
                f.write(f"{idx}. ID: {uid} | Name: {display_name} | Status: {status}\n")
                
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, "rb"), caption="👥 Full Users List")
        os.remove(file_path)
        await query.edit_message_text("✅ User list is too long, so it has been sent as a document.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]))
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode='HTML')

async def ask_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("📢 Enter the broadcast message:", reply_markup=cancel_kb())
    return ADMIN_BROADCAST

async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    wait = await update.message.reply_text("⏳ Broadcasting...")
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    sent, fail = 0, 0
    for (uid,) in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode='HTML')
            sent += 1
        except: fail += 1
        await asyncio.sleep(0.05)
    await wait.edit_text(f"✅ Broadcast Complete!\nSuccess: {sent}\nFailed: {fail}", reply_markup=main_menu_kb())
    return ConversationHandler.END

async def ask_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("🚫 Enter the User ID to <b>Ban</b>:", reply_markup=cancel_kb(), parse_mode='HTML')
    return ADMIN_BAN

async def do_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = update.message.text.strip()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    await update.message.reply_text(f"✅ User <code>{target_id}</code> has been banned successfully!", reply_markup=main_menu_kb(), parse_mode='HTML')
    return ConversationHandler.END

async def ask_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("✅ Enter the User ID to <b>Unban</b>:", reply_markup=cancel_kb(), parse_mode='HTML')
    return ADMIN_UNBAN

async def do_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = update.message.text.strip()
    cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    await update.message.reply_text(f"✅ User <code>{target_id}</code> has been unbanned!", reply_markup=main_menu_kb(), parse_mode='HTML')
    return ConversationHandler.END

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    doc = update.message.document
    if doc.file_name.endswith('.py'):
        wait = await update.message.reply_text("⏳ Upgrading bot with new code...")
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(__file__)
        await wait.edit_text("✅ Upgrade complete! Restarting system...")
        os.execv(sys.executable, ['python'] + sys.argv)

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help and instructions")
    ])

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler('help', help_command))
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CommandHandler('addemail', menu_addemail),
            CommandHandler('send', menu_send),
            CommandHandler('admin', menu_admin),
            CallbackQueryHandler(menu_addemail, pattern="^menu_addemail$"),
            CallbackQueryHandler(menu_send, pattern="^menu_send$"),
            CallbackQueryHandler(use_email_for_send, pattern="^use_em_"),
            CallbackQueryHandler(ask_update_pass, pattern="^update_pass_"),
            CallbackQueryHandler(ask_broadcast, pattern="^admin_broadcast$"),
            CallbackQueryHandler(ask_ban, pattern="^admin_ban$"),
            CallbackQueryHandler(ask_unban, pattern="^admin_unban$")
        ],
        states={
            GET_NEW_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_email)],
            GET_NEW_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_pass)],
            GET_UPDATE_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_update_pass)],
            SEND_RECEIVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_receiver)],
            SEND_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            # এখানে Document Upload সাপোর্ট যুক্ত করা হয়েছে:
            SEND_HTML: [MessageHandler((filters.TEXT | filters.Document.ALL) & ~filters.COMMAND, get_html_body)],
            CONFIRM_EMAIL: [CallbackQueryHandler(confirm_send, pattern="^confirm_send$")],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_broadcast)],
            ADMIN_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_ban)],
            ADMIN_UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_unban)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_action, pattern="^cancel_action$"),
            CommandHandler('start', start_command)
        ],
        per_message=False
    )
    
    app.add_handler(conv_handler)
    
    app.add_handler(CallbackQueryHandler(start_command, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(menu_myemails, pattern="^menu_myemails$"))
    app.add_handler(CallbackQueryHandler(manage_single_email, pattern="^manage_em_"))
    app.add_handler(CallbackQueryHandler(delete_email, pattern="^del_em_"))
    app.add_handler(CallbackQueryHandler(admin_users_list, pattern="^admin_users$"))
    
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("✅ Premium Bot is running successfully!")
    app.run_polling()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
