import os
import re
import time
import math
import random
import asyncio
import logging

# --- Hydrogram Imports ---
from hydrogram import Client, filters
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- Custom Modules ---
from config import Config, Temp
from script import Script
from database import db
from .utils import STS
from .test import get_client, iter_messages
from .db import connect_user_db

# Logger Setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Constants ---
TEXT = Script.TEXT

# ==============================================================================
#  Callback: Start Forwarding (Public/Button Click)
# ==============================================================================
@Client.on_callback_query(filters.regex(r'^start_public'))
async def start_public_forward(bot, query):
    user_id = query.from_user.id
    Temp.CANCEL[user_id] = False
    
    # 1. Check Lock
    if Temp.LOCK.get(user_id):
        return await query.answer("Please wait until previous task completes.", show_alert=True)

    # 2. Verify Data
    frwd_id = query.data.split("_")[2]
    sts = STS(frwd_id)
    if not sts.verify():
        await query.answer("This is an old button. Please create a new task.", show_alert=True)
        return await query.message.delete()

    task_info = sts.get(full=True)
    if task_info.TO in Temp.IS_FRWD_CHAT:
        return await query.answer("A task is already running in the target chat.", show_alert=True)

    # 3. Initialize Process
    m = await msg_edit(query.message, "<code>Verifying data, please wait...</code>")
    
    # Get configuration from STS
    _bot, caption, forward_tag, datas, protect, button = await sts.get_data(user_id)
    
    if not _bot:
        return await msg_edit(m, "<code>No bot added. Use /settings to add one!</code>", wait=True)

    # 4. Start the Client (Userbot or Bot)
    try:
        is_bot_client = _bot.get('is_bot', False)
        token_or_session = _bot['token'] if is_bot_client else _bot['session']
        
        client = await get_client(token_or_session, is_bot=is_bot_client)
        await client.start()
    except Exception as e:
        return await m.edit(f"Client Error: {e}")

    # 5. Handover to Core Logic
    await run_forward_logic(
        main_bot=bot,
        worker_client=client,
        user_id=user_id,
        status_msg=m,
        sts=sts,
        datas=datas,
        forward_tag=forward_tag,
        caption=caption,
        protect=protect,
        button=button,
        is_bot_client=is_bot_client,
        is_restart=False
    )


# ==============================================================================
#  Core Forwarding Logic (Engine)
# ==============================================================================
async def run_forward_logic(main_bot, worker_client, user_id, status_msg, sts, datas, forward_tag, caption, protect, button, is_bot_client, is_restart=False):
    
    # --- Pre-Checks ---
    try:
        if not is_restart:
            await msg_edit(status_msg, "<code>Processing...</code>")
            # Verify Access to Source
            try:
                await worker_client.get_messages(sts.get("FROM"), sts.get("limit"))
            except Exception:
                await msg_edit(status_msg, f"**Cannot access Source Chat.** Make sure the {'Bot' if is_bot_client else 'Userbot'} is a member/admin there.", retry_btn(sts.id), True)
                return await stop_process(worker_client, user_id)

            # Verify Access to Target
            try:
                test_msg = await worker_client.send_message(sts.get("TO"), "Testing Permissions...")
                await test_msg.delete()
            except Exception:
                await msg_edit(status_msg, f"**Cannot send to Target Chat.** Make sure the {'Bot' if is_bot_client else 'Userbot'} is Admin.", retry_btn(sts.id), True)
                return await stop_process(worker_client, user_id)

    except Exception as e:
        logger.error(f"Pre-check error: {e}")
        return await stop_process(worker_client, user_id)

    # --- Database & Config Setup ---
    user_have_db = False
    user_db = None
    dup_files = []

    try:
        if datas['db_uri']:
            connected, user_db = await connect_user_db(user_id, datas['db_uri'], sts.get("TO"))
            if connected:
                user_have_db = True
                if datas.get('skip_duplicate'):
                    async for ofile in await user_db.get_all_files():
                        dup_files.append(ofile["file_id"])

        if not is_restart:
            Temp.FORWARDINGS += 1
            await db.add_frwd(user_id)
            await send_msg(main_bot, user_id, "<b>🔥 Forwarding Started</b>")
            sts.add(time=True)

        Temp.IS_FRWD_CHAT.append(sts.get("TO"))
        Temp.LOCK[user_id] = True
        
        sleep_time = 1 if is_bot_client else 10
        
        # --- Filters Preparation ---
        keywords = "|".join(datas['keywords']) if datas['keywords'] else None
        extensions = "|".join(datas['extensions']) if datas['extensions'] else None
        
        MSG_BATCH = []
        progress_counter = 0

        # Initial Status Update
        await edit_status(user_id, status_msg, 'Starting', 5, sts)

        # --- Main Loop ---
        async for message in iter_messages(
            worker_client, 
            chat_id=sts.get("FROM"), 
            limit=sts.get("limit"), 
            offset=sts.get("skip"), 
            filters=datas['filters'], 
            max_size=datas['max_size']
        ):
            # Check Cancellation
            if await is_cancelled(main_bot, user_id, status_msg, sts):
                break

            # Progress Update (Every 20 msgs)
            if progress_counter % 20 == 0:
                await edit_status(user_id, status_msg, 'Running', 5, sts)
            progress_counter += 1
            
            sts.add('fetched')

            # --- Filtering Logic ---
            if message == "DUPLICATE":
                sts.add('duplicate'); continue
            elif message == "FILTERED":
                sts.add('filtered'); continue
            elif not message or message.empty or message.service:
                sts.add('deleted'); continue
            
            # File Filters
            if message.document:
                if await extension_filter(extensions, message.document.file_name):
                    sts.add('filtered'); continue
                if await keyword_filter(keywords, message.document.file_name):
                    sts.add('filtered'); continue
                if await size_filter(datas['max_size'], datas['min_size'], message.document.file_size):
                    sts.add('filtered'); continue
                
                # Duplicate Check
                if message.document.file_id in dup_files:
                    sts.add('duplicate'); continue
                
                if datas['skip_duplicate']:
                    dup_files.append(message.document.file_id)
                    if user_have_db:
                        await user_db.add_file(message.document.file_id)

            # --- Action: Forward or Copy ---
            if forward_tag:
                # Batch Forwarding
                MSG_BATCH.append(message.id)
                pending = len(MSG_BATCH)
                completed_so_far = sts.get('total') - sts.get('fetched')
                
                if pending >= 100 or completed_so_far <= 100:
                    await forward_messages_safe(user_id, worker_client, MSG_BATCH, status_msg, sts, protect)
                    sts.add('total_files', pending)
                    await asyncio.sleep(10)
                    MSG_BATCH = []
            else:
                # Copy Message (No Tag)
                new_caption = custom_caption(message, caption)
                details = {
                    "msg_id": message.id, 
                    "media": get_media_id(message), 
                    "caption": new_caption, 
                    'button': button, 
                    "protect": protect
                }
                await copy_message_safe(user_id, worker_client, details, status_msg, sts)
                sts.add('total_files')
                await asyncio.sleep(sleep_time)

        # --- Completion ---
        if sts.get("TO") in Temp.IS_FRWD_CHAT:
             Temp.IS_FRWD_CHAT.remove(sts.get("TO"))
        
        await send_msg(main_bot, user_id, "<b>🎉 Forwarding Completed Successfully!</b>")
        await edit_status(user_id, status_msg, 'Completed', "completed", sts)

    except Exception as e:
        logger.error(f"Fatal Error in Loop: {e}", exc_info=True)
        await msg_edit(status_msg, f'<b>ERROR:</b>\n<code>{e}</code>', wait=True)
    
    finally:
        # --- Cleanup ---
        if user_have_db and user_db:
            try:
                await user_db.drop_all()
                await user_db.close()
            except: pass
        
        await stop_process(worker_client, user_id)


# ==============================================================================
#  Restart Logic
# ==============================================================================
async def restart_forwards(client):
    users = await db.get_all_frwd()
    tasks = []
    async for user in users:
        tasks.append(restart_single_user(client, user))
    
    if tasks:
        await asyncio.gather(*tasks)

async def restart_single_user(bot, user_data):
    user_id = user_data['user_id']
    settings = await db.get_forward_details(user_id)
    
    try:
        forward_id = await store_vars(user_id)
        sts = STS(forward_id)
        
        if not settings.get('chat_id'):
            return await db.rmve_frwd(user_id)

        # Restore Counts
        sts.add('fetched', value=settings['fetched'] - settings['skip'])
        sts.add('duplicate', value=settings.get('duplicate', 0))
        sts.add('filtered', value=settings.get('filtered', 0))
        sts.add('deleted', value=settings.get('deleted', 0))
        sts.add('total_files', value=settings.get('total', 0))
        
        _bot, caption, forward_tag, datas, protect, button = await sts.get_data(user_id)
        
        try:
            m = await bot.get_messages(user_id, settings['msg_id'])
        except:
            m = None

        is_bot_client = _bot.get('is_bot', False)
        token = _bot['token'] if is_bot_client else _bot['session']
        
        worker = await get_client(token, is_bot=is_bot_client)
        await worker.start()
        
        Temp.FORWARDINGS += 1
        
        await run_forward_logic(
            main_bot=bot,
            worker_client=worker,
            user_id=user_id,
            status_msg=m,
            sts=sts,
            datas=datas,
            forward_tag=forward_tag,
            caption=caption,
            protect=protect,
            button=button,
            is_bot_client=is_bot_client,
            is_restart=True
        )

    except Exception as e:
        logger.error(f"Restart Error for {user_id}: {e}")
        await db.rmve_frwd(user_id)


# ==============================================================================
#  Helper Functions & Status Updates
# ==============================================================================

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d ") if days else "") + \
        ((str(hours) + "h ") if hours else "") + \
        ((str(minutes) + "m ") if minutes else "") + \
        ((str(seconds) + "s") if seconds else "")
    return tmp if tmp else "0s"

async def edit_status(user, msg, title, status, sts):
    if not msg: return
    
    i = sts.get(full=True)
    
    if status == 5:
        status_text = "Processing..."
    elif str(status).isnumeric():
        status_text = f"Sleeping ({status}s)"
    else:
        status_text = status

    # Percentage
    try:
        percentage = int((i.fetched * 100) / i.total) if i.total > 0 else 0
    except ZeroDivisionError:
        percentage = 0

    # Gradient Bar ▰▰▱▱
    filled_blocks = int(percentage / 10) 
    empty_blocks = 10 - filled_blocks
    progress_bar = f"{'▰' * filled_blocks}{'▱' * empty_blocks}"

    # Speed & ETA
    now = time.time()
    diff = int(now - i.start)
    speed_float = sts.divide(i.fetched, diff) if diff > 0 else 0
    speed_str = f"{speed_float:.1f} msg/s"
    
    remaining_files = i.total - i.fetched
    if speed_float > 0:
        eta_seconds = int(remaining_files / speed_float) * 1000 
        eta = TimeFormatter(eta_seconds)
    else:
        eta = "Calculating..."

    progress_str = f"{i.fetched} / {i.total_files}"

    text = TEXT.format(
        progress_bar,    # Bar
        percentage,      # %
        progress_str,    # Fetched/Total
        eta,             # ETA
        speed_str,       # Speed
        i.duplicate,     # Dup
        i.deleted,       # Del
        i.skip           # Skip
    )
    
    await update_forward_db(user, i)

    # Buttons
    btn_txt = f"⚡ {percentage}% | {status_text}"
    buttons = [[InlineKeyboardButton(btn_txt, f'fwrdstatus#{status}#{eta}#{percentage}#{i.id}')]]
    
    if status in ["cancelled", "completed"]:
        buttons.append([InlineKeyboardButton('✅ Task Completed', url='https://t.me/VJ_Botz')])
    else:
        buttons.append([InlineKeyboardButton('🛑 Terminate Process', 'terminate_frwd')])
    
    await msg_edit(msg, text, InlineKeyboardMarkup(buttons))

async def copy_message_safe(user, bot, msg, m, sts):
    try:
        chat_id = sts.get('TO')
        from_chat = sts.get('FROM')
        
        if msg.get("media") and msg.get("caption"):
            await bot.send_cached_media(
                chat_id=chat_id,
                file_id=msg.get("media"),
                caption=msg.get("caption"),
                reply_markup=msg.get('button'),
                protect_content=msg.get("protect")
            )
        else:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat,
                caption=msg.get("caption"),
                message_id=msg.get("msg_id"),
                reply_markup=msg.get('button'),
                protect_content=msg.get("protect")
            )
    except FloodWait as e:
        await edit_status(user, m, 'Running', e.value, sts)
        await asyncio.sleep(e.value)
        await copy_message_safe(user, bot, msg, m, sts)
    except Exception as e:
        logger.error(f"Copy Error: {e}")
        sts.add('deleted')

async def forward_messages_safe(user, bot, msg_ids, m, sts, protect):
    try:
        await bot.forward_messages(
            chat_id=sts.get('TO'),
            from_chat_id=sts.get('FROM'),
            protect_content=protect,
            message_ids=msg_ids
        )
    except FloodWait as e:
        await edit_status(user, m, 'Running', e.value, sts)
        await asyncio.sleep(e.value)
        await forward_messages_safe(user, bot, msg_ids, m, sts, protect)

async def is_cancelled(client, user, msg, sts):
    if Temp.CANCEL.get(user):
        if sts.get("TO") in Temp.IS_FRWD_CHAT:
            Temp.IS_FRWD_CHAT.remove(sts.get("TO"))
        
        if msg:
            await edit_status(user, msg, 'Cancelled', "cancelled", sts)
        
        await send_msg(client, user, "<b>❌ Forwarding Cancelled</b>")
        await stop_process(client, user)
        return True
    return False

async def stop_process(client, user):
    try:
        await client.stop()
    except:
        pass
    await db.rmve_frwd(user)
    if Temp.FORWARDINGS > 0:
        Temp.FORWARDINGS -= 1
    Temp.LOCK[user] = False

# --- Filters & Utils ---

async def extension_filter(extensions, file_name):
    return bool(extensions and re.search(extensions, file_name))

async def keyword_filter(keywords, file_name):
    return bool(keywords and re.search(keywords, file_name))

async def size_filter(max_size, min_size, file_size):
    size_mb = file_size / (1024 * 1024)
    if max_size == 0 and min_size == 0: return False
    if max_size == 0: return size_mb < min_size
    if min_size == 0: return size_mb > max_size
    return not (min_size <= size_mb <= max_size)

def get_media_id(msg):
    if msg.media:
        media_obj = getattr(msg, msg.media.value, None)
        return getattr(media_obj, 'file_id', None)
    return None

def custom_caption(msg, caption):
    if not msg.media: return None
    media_obj = getattr(msg, msg.media.value, None)
    file_name = getattr(media_obj, 'file_name', '')
    file_size = getattr(media_obj, 'file_size', 0)
    original_caption = getattr(msg, 'caption', '') or ''
    if hasattr(original_caption, 'html'): original_caption = original_caption.html
    
    if caption:
        return caption.format(
            filename=file_name, 
            size=get_size(file_size), 
            caption=original_caption
        )
    return original_caption

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def update_forward_db(user_id, i):
    details = {
        'chat_id': i.FROM,
        'toid': i.TO,
        'forward_id': i.id,
        'limit': i.limit,
        'msg_id': 0,
        'start_time': i.start,
        'fetched': i.fetched,
        'offset': i.fetched,
        'deleted': i.deleted,
        'total': i.total_files,
        'duplicate': i.duplicate,
        'skip': i.skip,
        'filtered': i.filtered
    }
    await db.update_forward(user_id, details)

# --- Small Utils ---
async def msg_edit(msg, text, button=None, wait=False):
    try:
        return await msg.edit(text, reply_markup=button)
    except MessageNotModified:
        pass
    except FloodWait as e:
        if wait:
            await asyncio.sleep(e.value)
            return await msg_edit(msg, text, button, wait)

async def send_msg(bot, user, text):
    try: await bot.send_message(user, text=text)
    except: pass

def retry_btn(id):
    return InlineKeyboardMarkup([[InlineKeyboardButton('♻️ RETRY ♻️', f"start_public_{id}")]])

async def store_vars(user_id):
    settings = await db.get_forward_details(user_id)
    fetch = settings['fetched']
    forward_id = f'{user_id}-{fetch}'
    STS(id=forward_id).store(settings['chat_id'], settings['toid'], settings['skip'], settings['limit'])
    return forward_id

@Client.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def terminate_handler(bot, m):
    user_id = m.from_user.id
    Temp.LOCK[user_id] = False
    Temp.CANCEL[user_id] = True
    await m.answer("Cancelling process...", show_alert=True)
