# 🧬 Genome Campaign Discord Bot

A Python-powered Discord bot tailored specifically for the **Genome campaign** on [Galxe](https://galxe.com/).  
This bot monitors the Galxe API for new Genome quests and announces them in real-time to a specified Discord channel.

---

## 🚀 Features

- ✅ Connects to the Galxe GraphQL API to fetch **Genome campaign** data
- ✅ Detects and announces **new Genome quests**
- ✅ Sends styled embed messages to a dedicated Discord channel
- ✅ Prevents duplicate announcements using a MySQL database
- ✅ Configurable via `.env` file

---

## ⚙️ Requirements

- Python 3.9+
- MySQL server
- Discord Bot Token
- Galxe API Access Token

---

## 📁 Project Structure

```
.
├── main.py                 # Main bot logic
├── .env                   # Environment variables
└── README.md              # You're here
```

---

## 🔧 Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/genome-discord-bot.git
cd genome-discord-bot
```

### 2. Create `.env` File

Create a `.env` file in the root directory:

```env
# Galxe GraphQL API
GALXE_API_URL=
GALXE_ACCESS_TOKEN=
SPACE_ID=

# Discord Bot
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
```

### 3. Run the Bot

```bash
python main.py
```

---

## 🧠 What Is Genome?

Genome is a community-driven quest campaign on Galxe. This bot focuses solely on monitoring the **Genome space** (SPACE_ID=35990) and automatically notifies users whenever a **new Genome quest** is published.

---

## 🧪 Example Output in Discord

> ✅ New Genome quest is live:  
> [**Quest Name**](https://app.galxe.com/quest/Genome/quest_id)

---

## 🛡️ Security Notes

- **Never share your `.env` file publicly** – it contains your Discord bot token and API secrets.
- Make sure `.env` is included in your `.gitignore`.

---

## 📄 License

MIT — use this freely and modify as needed.

---

## 🤝 Contributing

Pull requests and issues are welcome. If you find a bug or want a feature, open an issue or PR!
