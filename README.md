
<h1 align="center">
  <b>🚀 Advanced Auto Forward Bot</b>
</h1>

<p align="center">
  A powerful and fully asynchronous Telegram Bot written in Python using Hydrogram. <br>
  It can forward messages from <b>Public/Private Channels & Groups</b> to your target chats with advanced filtering, duplicate removal, and customization.
</p>

<p align="center">
  <a href="https://www.python.org">
    <img src="https://img.shields.io/badge/Python-3.11-blue?style=flat&logo=python&logoColor=white" alt="Python">
  </a>
  <a href="https://github.com/hydrogram/hydrogram">
    <img src="https://img.shields.io/badge/Hydrogram-Latest-orange?style=flat&logo=telegram&logoColor=white" alt="Hydrogram">
  </a>
  <a href="https://www.mongodb.com">
    <img src="https://img.shields.io/badge/Database-MongoDB-green?style=flat&logo=mongodb&logoColor=white" alt="MongoDB">
  </a>
</p>

---

## 🌟 Key Features

* **⚡ Ultra Fast Forwarding:** Optimized for speed with smart rate-limit handling.
* **🤖 Dual Client Support:** Supports both **Bot Token** and **Userbot (Session)**.
* **🔐 Private Chat Support:** Can forward from Private/Restricted Channels (using Userbot).
* **♻️ Smart De-Duplication:** Checks database to skip already forwarded files.
* **🧹 Unequify Feature:** Delete duplicate messages from any chat to clean it up.
* **🚫 Advanced Filters:**
    * **Content Type:** Toggle Text, Video, Document, Photo, Audio, etc.
    * **Link Filter:** Auto-block messages containing Hyperlinks or Ads.
    * **Extension Filter:** Allow only specific files (e.g., `mkv`, `mp4`).
    * **Size Filter:** Set Min/Max file size limits.
* **📝 Customization:** Replace captions and add custom buttons.
* **🛡️ Anti-Flood:** Intelligent delay system to prevent ban (28s Wait Error Fix).
* **📊 Live HUD:** Real-time progress bar with speed, ETA, and stats.

---

## 🛠️ Commands

| Command | Description |
| :--- | :--- |
| `/start` | Check if the bot is running. |
| `/settings` | Open the **Admin Panel** to configure Filters, Bots, and Database. |
| `/forward` | Start a new forwarding task (Supports Link or Forwarded msg). |
| `/unequify` | **De-Duplicate** a chat (Removes duplicate media files). |
| `/broadcast` | Broadcast a message to all bot users. |
| `/ping` | Check bot latency and uptime. |

---

## 🚀 Deployment

### Method 1: Deploy to Koyeb/Render/Heroku

<p align="left">
  <a href="https://app.koyeb.com/deploy?type=git&repository=github.com/YOUR_USERNAME/YOUR_REPO_NAME&branch=main&name=forward-bot">
    <img src="https://www.koyeb.com/static/images/deploy/button.svg" alt="Deploy to Koyeb" width="180">
  </a>
</p>

### Method 2: VPS / Local Run

1. **Clone the Repo**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
   cd YOUR_REPO_NAME
