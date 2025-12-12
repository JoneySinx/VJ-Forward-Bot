import os
import sys
import time
import asyncio
import psutil
from os import environ, execle, system

# --- Hydrogram Imports ---
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Custom Modules ---
from database import db
from config import Config
from script import Script

# Start Time Record
START_TIME = time.time()

# --- Keyboards ---
main_buttons = [[
    InlineKeyboardButton('🦹 Help', callback_data='help'),
    InlineKeyboardButton('🚀 Settings', callback_data='settings#main')
]]

# --- Command Handlers ---

@Client.on_message(filters.private & filters.command(['start']))
async def start(client, message):
    user = message.from_user
    # Database handling
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
    
    reply_markup = InlineKeyboardMarkup(main_buttons)
    await client.send_message(
        chat_id=message.chat.id,
        text=Script.START_TXT.format(user.first_name),
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

@Client.on_message(filters.command(['restart']) & filters.user(Config.BOT_OWNER))
async def restart(client, message):
    msg = await message.reply_text("<i>Restarting Server...</i>")
    await asyncio.sleep(2)
    await msg.edit("<i>Server Restarted Successfully ✅</i>")
    
    # Git Pull और Pip Install (ताकि अपडेट हो जाए)
    os.system("git pull -f && pip3 install --no-cache-dir -r requirements.txt")
    
    # Script Restart
    args = [sys.executable, "main.py"]
    execle(sys.executable, *args, environ)

@Client.on_message(filters.command(['ping']))
async def ping_cmd(client, message):
    """Check Bot Latency (Advanced Feature)"""
    start = time.time()
    msg = await message.reply_text("Pong!")
    end = time.time()
    await msg.edit(f"<b>Pong!</b> ⚡\nLatency: `{round((end - start) * 1000)}ms`")

# --- Callback Query Handlers ---

@Client.on_callback_query(filters.regex(r'^help'))
async def help_cb(bot, query):
    buttons = [[
        InlineKeyboardButton('⚡ Status', callback_data='status'),
        InlineKeyboardButton('🚀 Settings', callback_data='settings#main')
    ],[
        InlineKeyboardButton('🏄 Back', callback_data='back')
    ]]
    await query.message.edit_text(
        text=Script.HELP_TXT,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r'^how_to_use'))
async def how_to_use_cb(bot, query):
    buttons = [[InlineKeyboardButton('• Back', callback_data='help')]]
    await query.message.edit_text(
        text=Script.HOW_USE_TXT,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r'^back'))
async def back_cb(bot, query):
    await query.message.edit_text(
        text=Script.START_TXT.format(query.from_user.first_name),
        reply_markup=InlineKeyboardMarkup(main_buttons)
    )

@Client.on_callback_query(filters.regex(r'^about'))
async def about_cb(bot, query):
    buttons = [[
         InlineKeyboardButton('🏄 Back', callback_data='back'),
         InlineKeyboardButton('⚡ Stats', callback_data='status')
    ]]
    await query.message.edit_text(
        text=Script.ABOUT_TXT,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r'^status'))
async def status_cb(bot, query):
    users_count, bots_count = await db.total_users_bots_count()
    forwardings = await db.forwad_count()
    upt = get_bot_uptime(START_TIME)
    
    buttons = [[
        InlineKeyboardButton('🏄 Back', callback_data='back'),
        InlineKeyboardButton('♻️ System Stats', callback_data='systm_sts'),
    ]]
    
    # Format में अगर कोई वेरिएबल कम है तो एरर न आए, इसलिए try/except नहीं लगाया 
    # पर ध्यान रहे Script.STATUS_TXT में {0}, {1} etc सही हों।
    await query.message.edit_text(
        text=Script.STATUS_TXT.format(upt, users_count, bots_count, forwardings),
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )

@Client.on_callback_query(filters.regex(r'^systm_sts'))
async def sys_status_cb(bot, query):
    ram = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent()
    disk_usage = psutil.disk_usage('/')
    
    total_space = disk_usage.total / (1024**3)  # GB
    used_space = disk_usage.used / (1024**3)    # GB
    free_space = disk_usage.free / (1024**3)    # GB
    
    text = (
        f"<b>╔════❰ SERVER STATS ❱═❍⊱❁۪۪</b>\n"
        f"<b>║╭━━━━━━━━━━━━━━━➣</b>\n"
        f"<b>║┣⪼ Total Disk Space:</b> <code>{total_space:.2f} GB</code>\n"
        f"<b>║┣⪼ Used:</b> <code>{used_space:.2f} GB</code>\n"
        f"<b>║┣⪼ Free:</b> <code>{free_space:.2f} GB</code>\n"
        f"<b>║┣⪼ CPU:</b> <code>{cpu}%</code>\n"
        f"<b>║┣⪼ RAM:</b> <code>{ram}%</code>\n"
        f"<b>║╰━━━━━━━━━━━━━━━➣</b>\n"
        f"<b>╚══════════════════❍⊱❁۪۪</b>"
    )
    
    buttons = [[InlineKeyboardButton('• Back', callback_data='status')]] # status pe wapas bhejna better hai
    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )

# --- Helper Function ---

def get_bot_uptime(start_time):
    """Calculates uptime in readable format"""
    seconds = int(time.time() - start_time)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    uptime_parts = []
    if days:
        uptime_parts.append(f"{days}d")
    if hours:
        uptime_parts.append(f"{hours}h")
    if minutes:
        uptime_parts.append(f"{minutes}m")
    uptime_parts.append(f"{seconds}s")
    
    return " ".join(uptime_parts)
