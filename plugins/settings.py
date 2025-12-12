import asyncio 
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from hydrogram.errors import MessageNotModified # Import added

# --- Custom Modules ---
from database import db
from script import Script
from .test import ClientManager, parse_buttons
from .db import connect_user_db

# Initialize Manager
client_manager = ClientManager()

# --- Constants for HUD Design ---
SETTINGS_HEADER = "<b>╭──⌬ ⚙️ sᴇᴛᴛɪɴɢs ᴍᴇɴᴜ</b>\n<b>│</b>\n"
SUB_HEADER = "<b>╭──⌬ 🛠 {}</b>\n<b>│</b>\n"

# ==============================================================================
#  Helper Functions
# ==============================================================================

async def get_configs(user_id):
    return await db.get_configs(user_id)

async def update_configs(user_id, key, value):
    current = await db.get_configs(user_id)
    TOP_LEVEL_KEYS = [
        'caption', 'duplicate', 'db_uri', 'forward_tag', 
        'protect', 'min_size', 'max_size', 'extension', 
        'keywords', 'button', 'filters'
    ]
    
    if key in TOP_LEVEL_KEYS:
        current[key] = value
    else:
        if 'filters' not in current:
            current['filters'] = {}
        current['filters'][key] = value
        
    await db.update_configs(user_id, current)

# --- Safe Edit Function (Fixes MessageNotModified Error) ---
async def safe_edit(message, text, reply_markup):
    """Edits message safely, ignoring if content is unchanged"""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass # Ignore error if message is same
    except Exception as e:
        print(f"Edit Error: {e}")

# ==============================================================================
#  Command: /settings
# ==============================================================================

@Client.on_message(filters.command('settings'))
async def settings_command(client, message):
   text = SETTINGS_HEADER + "<b>╰──╼ ᴄᴏɴғɪɢᴜʀᴇ ʏᴏᴜʀ ʙᴏᴛ</b>"
   await message.reply_text(text, reply_markup=main_buttons())

# ==============================================================================
#  Callback Query Handler
# ==============================================================================

@Client.on_callback_query(filters.regex(r'^settings'))
async def settings_query(bot, query):
  user_id = query.from_user.id
  data_parts = query.data.split("#")
  action = data_parts[1]
  
  back_btn = [[InlineKeyboardButton('🔙 Back', callback_data="settings#main")]]

  # --- Main Menu ---
  if action == "main":
     text = SETTINGS_HEADER + "<b>╰──╼ ᴄᴏɴғɪɢᴜʀᴇ ʏᴏᴜʀ ʙᴏᴛ</b>"
     await safe_edit(query.message, text, main_buttons())

  # --- Extra Settings ---
  elif action == "extra":
       text = SUB_HEADER.format("ᴇxᴛʀᴀ sᴇᴛᴛɪɴɢs") + "<b>╰──╼ ᴀᴅᴠᴀɴᴄᴇᴅ ᴄᴏɴғɪɢs</b>"
       await safe_edit(query.message, text, extra_buttons())

  # --- Bots Management ---
  elif action == "bots":
     buttons = [] 
     _bot = await db.get_bot(user_id)
     usr_bot = await db.get_userbot(user_id)
     if _bot:
        buttons.append([InlineKeyboardButton(f"🤖 {_bot['name']}", callback_data="settings#editbot")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add Bot', callback_data="settings#addbot")])
     if usr_bot:
        buttons.append([InlineKeyboardButton(f"👤 {usr_bot['name']}", callback_data="settings#edituserbot")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add Userbot', callback_data="settings#adduserbot")])
     buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
     
     text = SUB_HEADER.format("ʙᴏᴛ ᴍᴀɴᴀɢᴇʀ") + "<b>╰──╼ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄʟɪᴇɴᴛs</b>"
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))

  elif action == "addbot":
     await query.message.delete()
     status = await client_manager.add_bot(bot, user_id) # Fixed: Passed user_id
     if status:
        await query.message.reply_text("<b>✅ Bot Token Successfully Added!</b>", reply_markup=InlineKeyboardMarkup(back_btn))

  elif action == "adduserbot":
     await query.message.delete()
     status = await client_manager.add_session(bot, user_id) # Fixed: Passed user_id
     if status:
        await query.message.reply_text("<b>✅ Userbot Session Added!</b>", reply_markup=InlineKeyboardMarkup(back_btn))

  # --- Channels ---
  elif action == "channels":
     buttons = []
     channels = await db.get_user_channels(user_id)
     for channel in channels:
        buttons.append([InlineKeyboardButton(f"📢 {channel['title']}", callback_data=f"settings#editchannels_{channel['chat_id']}")])
     buttons.append([InlineKeyboardButton('✚ Add Channel', callback_data="settings#addchannel")])
     buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
     text = SUB_HEADER.format("ᴄʜᴀɴɴᴇʟs") + "<b>╰──╼ ᴍᴀɴᴀɢᴇ ᴛᴀʀɢᴇᴛs</b>"
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))

  elif action == "addchannel":  
     await query.message.delete()
     prompt = await bot.ask(chat_id=user_id, text="<b>❪ SET TARGET CHAT ❫\n\nForward a message from your Target Channel.\n/cancel - To Cancel</b>")
     if prompt.text == "/cancel":
        return await prompt.reply_text("<b>❌ Process Cancelled</b>", reply_markup=InlineKeyboardMarkup(back_btn))
     if not prompt.forward_date:
        return await prompt.reply("<b>⚠️ Error: This is not a forwarded message.</b>")
     chat_id = prompt.forward_from_chat.id
     title = prompt.forward_from_chat.title
     username = f"@{prompt.forward_from_chat.username}" if prompt.forward_from_chat.username else "Private"
     chat = await db.add_channel(user_id, chat_id, title, username)
     msg = "<b>✅ Channel Added Successfully!</b>" if chat else "<b>⚠️ Channel Already Exists!</b>"
     await prompt.reply_text(msg, reply_markup=InlineKeyboardMarkup(back_btn))

  # --- Edit Bots ---
  elif action == "editbot": 
     bot_data = await db.get_bot(user_id)
     text = Script.BOT_DETAILS.format(bot_data['name'], bot_data['id'], bot_data['username'])
     buttons = [[InlineKeyboardButton('🗑 Remove', callback_data="settings#removebot")], [InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]]
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))
     
  elif action == "edituserbot": 
     bot_data = await db.get_userbot(user_id)
     text = Script.USER_DETAILS.format(bot_data['name'], bot_data['id'], bot_data['username'])
     buttons = [[InlineKeyboardButton('🗑 Remove', callback_data="settings#removeuserbot")], [InlineKeyboardButton('🔙 Back', callback_data="settings#bots")]]
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))
     
  elif action == "removebot":
     await db.remove_bot(user_id)
     await safe_edit(query.message, "<b>🗑 Bot Removed Successfully.</b>", InlineKeyboardMarkup(back_btn))
     
  elif action == "removeuserbot":
     await db.remove_userbot(user_id)
     await safe_edit(query.message, "<b>🗑 Userbot Removed Successfully.</b>", InlineKeyboardMarkup(back_btn))

  # --- Caption ---
  elif action == "caption":
     buttons = []
     data = await get_configs(user_id)
     if data['caption']:
        buttons.append([InlineKeyboardButton('👀 View', callback_data="settings#seecaption"), InlineKeyboardButton('🗑 Delete', callback_data="settings#deletecaption")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add Caption', callback_data="settings#addcaption")])
     buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
     text = SUB_HEADER.format("ᴄᴀᴘᴛɪᴏɴ") + "<b>│ Variables:</b>\n<b>│</b> <code>{filename}</code> : File Name\n<b>│</b> <code>{size}</code> : File Size\n<b>╰──╼</b> <code>{caption}</code> : Original Caption"
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))

  elif action == "addcaption":
     await query.message.delete()
     ask = await bot.ask(user_id, "<b>Send your Custom Caption:</b>\n\n/cancel - To Stop")
     if ask.text == "/cancel":
        return await ask.reply_text("Cancelled.", reply_markup=InlineKeyboardMarkup(back_btn))
     try:
         ask.text.format(filename='', size='', caption='')
     except KeyError as e:
         return await ask.reply_text(f"<b>⚠️ Error: Invalid placeholder {e}.</b>", reply_markup=InlineKeyboardMarkup(back_btn))
     await update_configs(user_id, 'caption', ask.text)
     await ask.reply_text("<b>✅ Caption Updated!</b>", reply_markup=InlineKeyboardMarkup(back_btn))

  elif action == "deletecaption":
     await update_configs(user_id, 'caption', None)
     await safe_edit(query.message, "<b>🗑 Caption Deleted.</b>", InlineKeyboardMarkup(back_btn))

  elif action == "seecaption":
      data = await get_configs(user_id)
      await safe_edit(query.message, f"<b>Your Caption:</b>\n\n<code>{data['caption']}</code>", InlineKeyboardMarkup(back_btn))

  # --- Database ---
  elif action == "database":
     buttons = []
     data = await get_configs(user_id)
     if data['db_uri']:
        buttons.append([InlineKeyboardButton('👀 View', callback_data="settings#seeurl"), InlineKeyboardButton('🗑 Delete', callback_data="settings#deleteurl")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add MongoDB', callback_data="settings#addurl")])
     buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
     text = SUB_HEADER.format("ᴅᴀᴛᴀʙᴀsᴇ") + "<b>╰──╼ ғᴏʀ ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴄʜᴇᴄᴋ</b>"
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))

  elif action == "addurl":
     await query.message.delete()
     ask = await bot.ask(user_id, "<b>Send your MongoDB URI:</b>\n\n/cancel - To Stop", disable_web_page_preview=True)
     if ask.text == "/cancel": return
     if not ask.text.startswith("mongodb"):
        return await ask.reply("<b>⚠️ Invalid URL format.</b>", reply_markup=InlineKeyboardMarkup(back_btn))
     connected, udb = await connect_user_db(user_id, ask.text, "test")
     if connected:
        await udb.drop_all()
        await udb.close()
        await update_configs(user_id, 'db_uri', ask.text)
        await ask.reply("<b>✅ Database Connected Successfully!</b>", reply_markup=InlineKeyboardMarkup(back_btn))
     else:
        await ask.reply("<b>❌ Connection Failed. Check your URL.</b>", reply_markup=InlineKeyboardMarkup(back_btn))
        
  elif action == "seeurl":
     data = await get_configs(user_id)
     await query.answer(f"URI: {data['db_uri']}", show_alert=True)
     
  elif action == "deleteurl":
     await update_configs(user_id, 'db_uri', None)
     await safe_edit(query.message, "<b>🗑 Database URI Deleted.</b>", InlineKeyboardMarkup(back_btn))

  # --- Filters ---
  elif action == "filters":
     await safe_edit(
        query.message,
        SUB_HEADER.format("ғɪʟᴛᴇʀs") + "<b>╰──╼ ᴛᴏɢɢʟᴇ ᴄᴏɴᴛᴇɴᴛ ᴛʏᴘᴇs</b>",
        await filters_buttons(user_id))

  elif action == "nextfilters":
     await safe_edit(
        query.message,
        SUB_HEADER.format("ᴀᴅᴠᴀɴᴄᴇᴅ ғɪʟᴛᴇʀs") + "<b>╰──╼ ᴍᴏʀᴇ ᴏᴘᴛɪᴏɴs</b>",
        await next_filters_buttons(user_id))

  elif action.startswith("updatefilter"):
     _, key, value = action.split('-')
     new_value = False if value == "True" else True
     await update_configs(user_id, key, new_value)
     
     page_2_keys = ['poll', 'protect', 'voice', 'animation', 'sticker', 'duplicate', 'link']
     if key in page_2_keys:
        await query.edit_message_reply_markup(reply_markup=await next_filters_buttons(user_id))
     else:
        await query.edit_message_reply_markup(reply_markup=await filters_buttons(user_id))

  # --- Size Limits ---
  elif action.startswith("file_size") or action.startswith("maxfile_size"):
     settings = await get_configs(user_id)
     is_max = "max" in action
     key = 'max_size' if is_max else 'min_size'
     size = settings.get(key, 0)
     text = SUB_HEADER.format("sɪᴢᴇ ʟɪᴍɪᴛ") + f"<b>╰──╼ {'Maximum' if is_max else 'Minimum'}:</b> <code>{size} MB</code>"
     markup = maxsize_button(size) if is_max else size_button(size)
     await safe_edit(query.message, text, markup)

  elif action.startswith("update_size") or action.startswith("maxupdate_size"):
     try:
         parts = action.split('-')
         base_action = parts[0]
         new_size = int(parts[1])
         if new_size < 0: new_size = 0
         if new_size > 4000: return await query.answer("Limit cannot exceed 4GB", show_alert=True)
         is_max = "max" in base_action
         config_key = 'max_size' if is_max else 'min_size'
         await update_configs(user_id, config_key, new_size)
         text = SUB_HEADER.format("sɪᴢᴇ ʟɪᴍɪᴛ") + f"<b>╰──╼ {'Maximum' if is_max else 'Minimum'}:</b> <code>{new_size} MB</code>"
         markup = maxsize_button(new_size) if is_max else size_button(new_size)
         await safe_edit(query.message, text, markup)
     except Exception as e:
         print(f"Size Error: {e}")

  # --- Keywords ---
  elif action == "get_keyword":
    keywords = (await get_configs(user_id))['keywords']
    text = SUB_HEADER.format("ᴋᴇʏᴡᴏʀᴅs")
    text += "\n".join([f"<code>• {k}</code>" for k in keywords]) if keywords else "<b>🚫 No Keywords Added</b>"
    btn = [[InlineKeyboardButton('✚ Add', 'settings#add_keyword'), InlineKeyboardButton('🗑 Clear All', 'settings#rmve_all_keyword')], [InlineKeyboardButton('🔙 Back', 'settings#extra')]]
    await safe_edit(query.message, text, InlineKeyboardMarkup(btn))

  elif action == "add_keyword":
    await query.message.delete()
    ask = await bot.ask(user_id, "**Send Keywords (separated by space):**")
    if ask.text == "/cancel": return
    new_keys = ask.text.split(" ")
    current = (await get_configs(user_id))['keywords'] or []
    current.extend(new_keys)
    await update_configs(user_id, 'keywords', current)
    await ask.reply_text("<b>✅ Keywords Added</b>", reply_markup=InlineKeyboardMarkup(back_btn))

  elif action == "rmve_all_keyword":
      await update_configs(user_id, 'keywords', None)
      await query.answer("All Keywords Removed", show_alert=True)
      await settings_query(bot, query)

  # --- Extensions ---
  elif action == "get_extension":
    extensions = (await get_configs(user_id))['extension']
    text = SUB_HEADER.format("ᴇxᴛᴇɴsɪᴏɴs")
    text += "\n".join([f"<code>• {k}</code>" for k in extensions]) if extensions else "<b>🚫 No Extensions Filtered</b>"
    btn = [[InlineKeyboardButton('✚ Add', 'settings#add_extension'), InlineKeyboardButton('🗑 Clear All', 'settings#rmve_all_extension')], [InlineKeyboardButton('🔙 Back', 'settings#extra')]]
    await safe_edit(query.message, text, InlineKeyboardMarkup(btn))

  elif action == "add_extension":
    await query.message.delete()
    ask = await bot.ask(user_id, "**Send Extensions:**")
    if ask.text == "/cancel": return
    new_keys = ask.text.split(" ")
    current = (await get_configs(user_id))['extension'] or []
    current.extend(new_keys)
    await update_configs(user_id, 'extension', current)
    await ask.reply_text("<b>✅ Extensions Added</b>", reply_markup=InlineKeyboardMarkup(back_btn))

  elif action == "rmve_all_extension":
      await update_configs(user_id, 'extension', None)
      await query.answer("All Extensions Removed", show_alert=True)
      await settings_query(bot, query)

  # --- Buttons ---
  elif action == "button":
     buttons = []
     data = await get_configs(user_id)
     if data['button']:
        buttons.append([InlineKeyboardButton('👀 View', callback_data="settings#seebutton"), InlineKeyboardButton('🗑 Delete', callback_data="settings#deletebutton")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add Button', callback_data="settings#addbutton")])
     buttons.append([InlineKeyboardButton('🔙 Back', callback_data="settings#main")])
     text = SUB_HEADER.format("ʙᴜᴛᴛᴏɴs") + "<b>╰──╼</b> <code>[Name][buttonurl:https://link.com]</code>"
     await safe_edit(query.message, text, InlineKeyboardMarkup(buttons))

  elif action == "addbutton":
     await query.message.delete()
     ask = await bot.ask(user_id, text="**Send your custom button:**")
     parsed = parse_buttons(ask.text)
     if not parsed: return await ask.reply("**❌ Invalid Format**", reply_markup=InlineKeyboardMarkup(back_btn))
     await update_configs(user_id, 'button', ask.text)
     await ask.reply("**✅ Button Added**", reply_markup=InlineKeyboardMarkup(back_btn))

  elif action == "seebutton":
      data = await get_configs(user_id)
      back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "settings#button")]])
      await safe_edit(query.message, f"<b>Preview:</b>\n{data['button']}", back)

  elif action == "deletebutton":
     await update_configs(user_id, 'button', None)
     await safe_edit(query.message, "**🗑 Button Deleted**", InlineKeyboardMarkup(back_btn))

  elif action.startswith("alert"):
    alert_text = action.split('_')[1]
    await query.answer(alert_text, show_alert=True)

# ==============================================================================
#  Button Generators
# ==============================================================================

def main_buttons():
  return InlineKeyboardMarkup([
       [InlineKeyboardButton('🦹 Bots', callback_data='settings#bots'), InlineKeyboardButton('🧑‍🤝‍🧑 Channels', callback_data='settings#channels')],
       [InlineKeyboardButton('🖍️ Caption', callback_data='settings#caption'), InlineKeyboardButton('🌩️ Database', callback_data='settings#database')],
       [InlineKeyboardButton('🎨 Filters', callback_data='settings#filters'), InlineKeyboardButton('🧩 Extra', callback_data='settings#extra')],
       [InlineKeyboardButton('🔙 Close', callback_data='close_btn')]
  ])

def extra_buttons():
   return InlineKeyboardMarkup([
       [InlineKeyboardButton('💾 Min Size', callback_data='settings#file_size'), InlineKeyboardButton('💾 Max Size', callback_data='settings#maxfile_size')],
       [InlineKeyboardButton('🚥 Keywords', callback_data='settings#get_keyword'), InlineKeyboardButton('🕹 Extensions', callback_data='settings#get_extension')],
       [InlineKeyboardButton('⚡ Button', callback_data='settings#button')],
       [InlineKeyboardButton('🔙 Back', callback_data='settings#main')]
   ])

def size_button(size):
  return generate_size_buttons(size, "settings#update_size")

def maxsize_button(size):
  return generate_size_buttons(size, "settings#maxupdate_size")

def generate_size_buttons(size, callback_base):
    return InlineKeyboardMarkup([
       [InlineKeyboardButton('+1', f'{callback_base}-{size + 1}'), InlineKeyboardButton('-1', f'{callback_base}-{size - 1}')],
       [InlineKeyboardButton('+10', f'{callback_base}-{size + 10}'), InlineKeyboardButton('-10', f'{callback_base}-{size - 10}')],
       [InlineKeyboardButton('+100', f'{callback_base}-{size + 100}'), InlineKeyboardButton('-100', f'{callback_base}-{size - 100}')],
       [InlineKeyboardButton('🔙 Back', callback_data="settings#extra")]
    ])

async def filters_buttons(user_id):
  data = await get_configs(user_id)
  f = data['filters']
  def btn(label, key, val):
      state = '✅' if val else '❌'
      return [InlineKeyboardButton(label, f'settings#alert_{label}'), InlineKeyboardButton(state, f'settings#updatefilter-{key}-{val}')]
  buttons = [
      btn('Forward Tag', 'forward_tag', data['forward_tag']),
      btn('Texts', 'text', f['text']),
      btn('Documents', 'document', f['document']),
      btn('Videos', 'video', f['video']),
      btn('Photos', 'photo', f['photo']),
      [InlineKeyboardButton('🔙 Back', 'settings#main'), InlineKeyboardButton('Next ⫸', 'settings#nextfilters')]
  ]
  return InlineKeyboardMarkup(buttons) 

async def next_filters_buttons(user_id):
  data = await get_configs(user_id)
  f = data['filters']
  def btn(label, key, val):
      state = '✅' if val else '❌'
      return [InlineKeyboardButton(label, f'settings#alert_{label}'), InlineKeyboardButton(state, f'settings#updatefilter-{key}-{val}')]
  buttons = [
      btn('Voices', 'voice', f['voice']),
      btn('Animations', 'animation', f['animation']),
      btn('Stickers', 'sticker', f['sticker']),
      btn('Skip Dup', 'duplicate', data['duplicate']),
      btn('Polls', 'poll', f['poll']),
      btn('Protect', 'protect', data['protect']),
      btn('Links', 'link', f.get('link', True)), # Link Filter
      [InlineKeyboardButton('⫷ Back', 'settings#filters'), InlineKeyboardButton('Home 🏠', 'settings#main')]
  ]
  return InlineKeyboardMarkup(buttons)
