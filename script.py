class Script:
    START_TXT = """<b>👋 Hi {},

I am an Advanced Forward Bot.
I can forward messages from one channel to another with advanced filters and customization.</b>

**Click the buttons below to know more.**"""

    HELP_TXT = """<b><u>🔆 Help Menu</u></b>

<b>📚 Available Commands:</b>
⏣ <b>/start</b> - Check if I am alive
⏣ <b>/forward</b> - Start forwarding messages
⏣ <b>/settings</b> - Configure bot settings
⏣ <b>/stop</b> - Stop ongoing tasks
⏣ <b>/reset</b> - Reset settings to default

<b>💢 Features:</b>
► Forward from Public/Private Channels
► Custom Captions & Buttons
► Skip Duplicate Messages
► Media & Extension Filters
► Clone/Forward Support
"""

    HOW_USE_TXT = """<b><u>⚠️ How to Use?</u></b>

<b>1. Add Account:</b>
   ► Use <b>/settings</b> to add a Bot or Userbot (Session).
   
<b>2. Permissions:</b>
   ► <b>Bot:</b> Must be Admin in the Target Channel.
   ► <b>Userbot:</b> Must be a member of the Source Channel (if private).

<b>3. Start Forwarding:</b>
   ► Send <b>/forward</b> and follow the instructions.
"""

    ABOUT_TXT = """<b>
╔════❰ ABOUT ME ❱═❍⊱❁۪۪
║╭━━━━━━━━━━━━━━━➣
║┣⪼ 🤖 <b>Bot:</b> <a href='https://t.me/VJ_Botz'>Advanced Forwarder</a>
║┣⪼ 📡 <b>Language:</b> Python 3
║┣⪼ 📚 <b>Library:</b> Hydrogram (Latest)
║┣⪼ 🧑‍💻 <b>Developer:</b> <a href='https://t.me/KingVJ01'>VJ Botz</a>
║╰━━━━━━━━━━━━━━━➣
╚══════════════════❍⊱❁۪۪
</b>"""

    STATUS_TXT = """
╔════❰ SERVER STATUS ❱═❍⊱❁۪۪
║╭━━━━━━━━━━━━━━━➣
║┣⪼ <b>⏳ Uptime:</b> <code>{}</code>
║┣⪼ <b>👱 Users:</b> <code>{}</code>
║┣⪼ <b>🤖 Bots:</b> <code>{}</code>
║┣⪼ <b>🔃 Tasks:</b> <code>{}</code>
║╰━━━━━━━━━━━━━━━➣
╚══════════════════❍⊱❁۪۪
"""

    # --- Prompt Messages ---
    FROM_MSG = "<b>❪ SOURCE CHAT ❫\n\nForward the last message from the Source Channel or send its Link.\n\n/cancel - To Stop</b>"
    
    TO_MSG = "<b>❪ TARGET CHAT ❫\n\nSelect the Target Chat from the buttons below.\n\n/cancel - To Stop</b>"
    
    SKIP_MSG = "<b>❪ SKIP MESSAGES ❫\n\nEnter the number of messages to skip from the start.\nExample: <code>100</code> (Skips first 100 messages).\n\nDefault: 0\n/cancel - To Stop</b>"
    
    CANCEL = "<b>✅ Process Cancelled Successfully.</b>"
    
    BOT_DETAILS = "<b><u>📄 BOT DETAILS</u></b>\n\n<b>➣ Name:</b> <code>{}</code>\n<b>➣ ID:</b> <code>{}</code>\n<b>➣ Username:</b> @{}"
    
    USER_DETAILS = "<b><u>📄 USERBOT DETAILS</u></b>\n\n<b>➣ Name:</b> <code>{}</code>\n<b>➣ ID:</b> <code>{}</code>\n<b>➣ Username:</b> @{}"

    # --- Ultra Advanced HUD Design ---
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
<b>  ♻️ ᴅᴜᴘ:</b> <code>{}</code> <b>| 🗑️ ᴅᴇʟ:</b> <code>{}</code> <b>| 🚫 sᴋɪᴘ:</b> <code>{}</code>
"""

    DOUBLE_CHECK = """<b><u>⚠️ DOUBLE CHECK</u></b>

Please verify the details before starting:

<b>★ Bot/Session:</b> [{botname}](t.me/{botuname})
<b>★ From:</b> `{from_chat}`
<b>★ To:</b> `{to_chat}`
<b>★ Skip:</b> `{skip}`

<i>1. [{botname}](t.me/{botuname}) must be ADMIN in the Target Chat.</i>
<i>2. If Source is Private, the Account must be a member there.</i>

<b>Click 'Yes' to start forwarding.</b>"""

    SETTINGS_TXT = """<b>⚙️ Settings Menu</b>\nConfigure your bots and filters here."""
