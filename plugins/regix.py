
import os
import re
import time
import math
import random
import asyncio
import logging
from hydrogram import Client, filters
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config, Temp
from script import Script
from database import db
from .utils import STS
from .test import get_client, iter_messages
from .db import connect_user_db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TEXT = """
<b>╭──⌬ ⚡ ᴀᴄᴛɪᴠᴇ sᴇssɪᴏɴ</b>
<b>│</b>
<b>│</b>  {}
<b>│</b>  <code>{} %</code>
<b>│</b>
<b>├──╼ 📊 ʟɪᴠᴇ sᴛᴀᴛɪsᴛɪᴄs</b>
<b>│ 📂 ᴘʀᴏɢʀᴇss :</b> <code>{}</code>
<b>│ ⏳ ᴇᴛᴀ      :</b> <code>{}</code>
<b>│ 🚀 sᴘᴇᴇᴅ    :</b> <code>{}</code>
<b>│</b>
<b>╰──╼ 🛡️ ғɪʟᴛᴇʀ ʀᴇᴘᴏʀᴛ</b>
<b>  ♻️ ᴅᴜᴘ:</b> <code>{}</code> <b>| 🚫 ғɪʟᴛ:</b> <code>{}</code> <b>| 🗑️ sᴋɪᴘ:</b> <code>{}</code>
"""

@Client.on_callback_query(filters.regex(r'^start_public'))
async def start_public_forward(bot, query):
    user_id = query.from_user.id
    Temp.CANCEL[user_id] = False
    if Temp.LOCK.get(user_id): return await query.answer("Wait for current task!", show_alert=True)

    frwd_id = query.data.split("_")[2]
    sts = STS(frwd_id)
    if not sts.verify(): return await query.message.delete()

    m = await msg_edit(query.message, "<code>Verifying...</code>")
    _bot, caption, forward_tag, datas, protect, button = await sts.get_data(user_id)
    
    if not _bot: return await msg_edit(m, "<code>No Client Found!</code>", wait=True)

    try:
        is_bot_client = _bot.get('is_bot', False)
        client = await get_client(_bot['token'] if is_bot_client else _bot['session'], is_bot=is_bot_client)
        await client.start()
    except Exception as e: return await m.edit(f"Error: {e}")

    await run_forward_logic(bot, client, user_id, m, sts, datas, forward_tag, caption, protect, button, is_bot_client)

async def run_forward_logic(main_bot, worker_client, user_id, status_msg, sts, datas, forward_tag, caption, protect, button, is_bot_client, is_restart=False):
    try:
        if not is_restart: await msg_edit(status_msg, "<code>Processing...</code>")
        
        user_have_db = False; user_db = None; dup_files = []
        if datas['db_uri']:
            connected, user_db = await connect_user_db(user_id, datas['db_uri'], sts.get("TO"))
            if connected:
                user_have_db = True
                if datas.get('skip_duplicate'):
                    async for ofile in await user_db.get_all_files(): dup_files.append(ofile["file_id"])

        if not is_restart:
            Temp.FORWARDINGS += 1
            await db.add_frwd(user_id)
            await send_msg(main_bot, user_id, "<b>🔥 Forwarding Started</b>")
            sts.add(time=True)

        Temp.IS_FRWD_CHAT.append(sts.get("TO"))
        Temp.LOCK[user_id] = True
        
        keywords = "|".join(datas['keywords']) if datas['keywords'] else None
        extensions = "|".join(datas['extensions']) if datas['extensions'] else None
        
        MSG_BATCH = []
        progress_counter = 0
        await edit_status(user_id, status_msg, 'Starting', 5, sts)

        async for message in iter_messages(worker_client, sts.get("FROM"), sts.get("limit"), sts.get("skip"), datas['filters'], datas['max_size']):
            if await is_cancelled(main_bot, user_id, status_msg, sts): break

            if progress_counter % 20 == 0: await edit_status(user_id, status_msg, 'Running', 5, sts)
            progress_counter += 1
            sts.add('fetched')

            if message in ["DUPLICATE", "FILTERED"]: sts.add(message.lower()); continue
            if not message or message.empty or message.service: sts.add('deleted'); continue
            
            if message.document:
                if await extension_filter(extensions, message.document.file_name): sts.add('filtered'); continue
                if await keyword_filter(keywords, message.document.file_name): sts.add('filtered'); continue
                if await size_filter(datas['max_size'], datas['min_size'], message.document.file_size): sts.add('filtered'); continue
                if message.document.file_id in dup_files: sts.add('duplicate'); continue
                if datas['skip_duplicate']:
                    dup_files.append(message.document.file_id)
                    if user_have_db: await user_db.add_file(message.document.file_id)

            if forward_tag:
                MSG_BATCH.append(message.id)
                if len(MSG_BATCH) >= 100:
                    await forward_messages_safe(user_id, worker_client, MSG_BATCH, status_msg, sts, protect)
                    sts.add('total_files', len(MSG_BATCH))
                    await asyncio.sleep(random.randint(10, 15)) # Batch ke baad 10-15s delay
                    MSG_BATCH = []
            else:
                new_caption = custom_caption(message, caption)
                details = {"msg_id": message.id, "media": get_media_id(message), "caption": new_caption, 'button': button, "protect": protect}
                await copy_message_safe(user_id, worker_client, details, status_msg, sts)
                sts.add('total_files')
                
                # --- ULTRA SAFE DELAY (Sending) ---
                # 4 se 10 second ka random delay har message ke baad
                await asyncio.sleep(random.uniform(4, 10)) 

        if MSG_BATCH:
             await forward_messages_safe(user_id, worker_client, MSG_BATCH, status_msg, sts, protect)
             sts.add('total_files', len(MSG_BATCH))

        await send_msg(main_bot, user_id, "<b>🎉 Completed!</b>")
        await edit_status(user_id, status_msg, 'Completed', "completed", sts)

    except Exception as e:
        logger.error(f"Loop Error: {e}")
        await msg_edit(status_msg, f'<b>ERROR:</b>\n<code>{e}</code>', wait=True)
    finally:
        if sts.get("TO") in Temp.IS_FRWD_CHAT: Temp.IS_FRWD_CHAT.remove(sts.get("TO"))
        if user_have_db and user_db:
            try: await user_db.close()
            except: pass
        await stop_process(worker_client, user_id)

async def restart_forwards(client):
    pass 

# --- Helpers ---
def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return ((str(days) + "d ") if days else "") + ((str(hours) + "h ") if hours else "") + ((str(minutes) + "m ") if minutes else "") + ((str(seconds) + "s") if seconds else "") or "0s"

async def edit_status(user, msg, title, status, sts):
    if not msg: return
    i = sts.get(full=True)
    try: percentage = int((i.fetched * 100) / i.total) if i.total > 0 else 0
    except: percentage = 0
    filled = int(percentage / 10)
    bar = f"{'▰' * filled}{'▱' * (10 - filled)}"
    speed = sts.divide(i.fetched, int(time.time() - i.start)) if (time.time() - i.start) > 0 else 0
    remaining = i.total - i.fetched
    eta = TimeFormatter(int(remaining / speed) * 1000) if speed > 0 else "Calc..."
    
    text = TEXT.format(bar, percentage, f"{i.fetched} / {i.total_files}", eta, f"{speed:.1f} msg/s", i.duplicate, i.filtered, i.deleted + i.skip)
    await update_forward_db(user, i)
    
    btn = [[InlineKeyboardButton(f"⚡ {percentage}% | {status}", 'fwrdstatus')]]
    if status in ["cancelled", "completed"]: btn.append([InlineKeyboardButton('✅ Done', url='https://t.me/VJ_Botz')])
    else: btn.append([InlineKeyboardButton('🛑 Stop', 'terminate_frwd')])
    await msg_edit(msg, text, InlineKeyboardMarkup(btn))

async def copy_message_safe(user, bot, msg, m, sts):
    try:
        if msg.get("media") and msg.get("caption"):
            await bot.send_cached_media(chat_id=sts.get('TO'), file_id=msg.get("media"), caption=msg.get("caption"), reply_markup=msg.get('button'), protect_content=msg.get("protect"))
        else:
            await bot.copy_message(chat_id=sts.get('TO'), from_chat_id=sts.get('FROM'), caption=msg.get("caption"), message_id=msg.get("msg_id"), reply_markup=msg.get('button'), protect_content=msg.get("protect"))
    except FloodWait as e:
        wait = e.value + random.randint(5, 10)
        await asyncio.sleep(wait)
        await copy_message_safe(user, bot, msg, m, sts)
    except Exception: sts.add('deleted')

async def forward_messages_safe(user, bot, msg_ids, m, sts, protect):
    try:
        await bot.forward_messages(chat_id=sts.get('TO'), from_chat_id=sts.get('FROM'), protect_content=protect, message_ids=msg_ids)
    except FloodWait as e:
        await asyncio.sleep(e.value + 5)
        await forward_messages_safe(user, bot, msg_ids, m, sts, protect)

async def is_cancelled(client, user, msg, sts):
    if Temp.CANCEL.get(user):
        if sts.get("TO") in Temp.IS_FRWD_CHAT: Temp.IS_FRWD_CHAT.remove(sts.get("TO"))
        if msg: await edit_status(user, msg, 'Cancelled', "cancelled", sts)
        await send_msg(client, user, "<b>❌ Cancelled</b>")
        await stop_process(client, user)
        return True
    return False

async def stop_process(client, user):
    try: await client.stop()
    except: pass
    await db.rmve_frwd(user)
    if Temp.FORWARDINGS > 0: Temp.FORWARDINGS -= 1
    Temp.LOCK[user] = False

# Filters & Utils
async def extension_filter(ext, fname): return bool(ext and re.search(ext, fname))
async def keyword_filter(keys, fname): return bool(keys and re.search(keys, fname))
async def size_filter(mx, mn, size):
    size_mb = size / (1024 * 1024)
    if mx == 0 and mn == 0: return False
    return not ((mn == 0 or size_mb >= mn) and (mx == 0 or size_mb <= mx))

def get_media_id(msg):
    if msg.media: return getattr(getattr(msg, msg.media.value, None), 'file_id', None)
    return None

def custom_caption(msg, caption):
    if not msg.media: return None
    media = getattr(msg, msg.media.value, None)
    fname = getattr(media, 'file_name', '')
    original = (getattr(msg, 'caption', '') or '')
    if hasattr(original, 'html'): original = original.html
    if caption: return caption.format(filename=fname, size=get_size(getattr(media, 'file_size', 0)), caption=original)
    return original

def get_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]; i = 0
    while size >= 1024.0 and i < len(units) - 1: i += 1; size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def update_forward_db(user_id, i):
    await db.update_forward(user_id, {'chat_id': i.FROM, 'toid': i.TO, 'forward_id': i.id, 'limit': i.limit, 'start_time': i.start, 'fetched': i.fetched, 'offset': i.fetched, 'deleted': i.deleted, 'total': i.total_files, 'duplicate': i.duplicate, 'skip': i.skip, 'filtered': i.filtered})

async def msg_edit(msg, text, button=None, wait=False):
    try: await msg.edit(text, reply_markup=button)
    except MessageNotModified: pass
    except FloodWait as e:
        if wait: await asyncio.sleep(e.value); await msg_edit(msg, text, button, wait)

async def send_msg(bot, user, text):
    try: await bot.send_message(user, text=text)
    except: pass

async def store_vars(user_id):
    s = await db.get_forward_details(user_id)
    fid = f'{user_id}-{s["fetched"]}'
    STS(id=fid).store(s['chat_id'], s['toid'], s['skip'], s['limit'])
    return fid

@Client.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def terminate_handler(bot, m):
    uid = m.from_user.id; Temp.LOCK[uid] = False; Temp.CANCEL[uid] = True
    await m.answer("Cancelling...", show_alert=True)
