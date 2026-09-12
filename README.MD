# 🛰️ R0-U41 AI Gamemaster Discord Bot

R0-U41 is a fully modular, AI-powered Discord bot tailored for immersive Star Wars-themed roleplaying and economy gameplay. Packed with features like mission & bounty tracking, AI storytelling, and automated rewards—built to scale with your RP community.

Gamemaster avatars use the public `gm pics` directory. Set `AVATAR_BASE_URL` in `.env` to that directory's public URL when hosting the assets elsewhere; if omitted, the bot uses the current image repository.

Mission and bounty administration accepts the common moderator role names `Moderator`, `Mod`, `Mods`, and `Moderators` by default. For an exact permission boundary, set `MODERATOR_ROLE_IDS` in `.env` to a comma-separated list of trusted Discord role IDs; configured IDs take precedence over role names. `MODERATOR_ROLE_NAMES` can customize the name fallback when IDs are not configured.

---

## 🚀 Features

### 🧠 AI-Driven Experiences
- **AI Gamemaster:** Uses OpenAI and Gemini APIs to generate narrative-driven roleplaying scenes.
- **AI Chatbot:** Intelligent character-based replies in designated IC (in-character) or OOC channels.
- **AI Holo News Reports:** Scheduled galaxy-wide news broadcasts auto-generated and stylized in-universe.

### 📜 Mission & Bounty Tracking (SQL-Powered)
- Create, edit, and manage **missions and bounties** with factions, rewards, availability, and difficulty.
- SQLAlchemy-backed persistence for tracking active, completed, or failed objectives.
- Confirmation-based command interactions with Discord embeds and reactions.

### 💸 Game Features
- **🎲 Pod Racing (Mini-Game):** High-stakes racing game where users bet and win credits.
- **📈 Credit System Integration:** Seamless economy connection via **UnbelievaBoat's API**.
- **📢 Bump Tracker:** Detects `!d bump` and rewards bumpers with credits automatically.

### 📡 Webhook Immersion
- Multiple NPCs or GM voices simulated using Discord webhooks.
- Character image indexing system for dynamic RP scenes and role distinction.

---

## 🧩 Tech Stack

- **discord.py** (Hybrid & Application Commands)
- **SQLAlchemy** (Missions, Users, Economy)
- **OpenAI + Gemini API** (AI storytelling and chatbot)
- **UnbelievaBoat API** (Credit tracking and payouts)
- **AsyncIO + Schedulers** (For timeouts and holo-news posting)
- **Webhooks & Embeds** (RP display and formatting)

---

## 🧾 Commands Preview (Full List not Included)

| Command                | Description                             |
|------------------------| --------------------------------------- |
| `/add_mission`         | Create a new mission (Moderator role)   |
| `/edit_mission`        | Update mission title, reward, etc. (Moderator role) |
| `/mission_status`      | Toggle mission availability (Moderator role) |
| `/delete_mission`      | Delete a mission (Moderator role)       |
| `/add_bounty`          | Create a new bounty (Moderator role)    |
| `/delete_bounty`       | Delete a bounty (Moderator role)        |
| `/generate_missions`   | Generate missions (Moderator role)      |
| `/generate_bounties`   | Generate bounties (Moderator role)      |
| `/all_bounties`        | View or assign bounties by faction      |
| `/gamemaster_start`    | Start a new AI RP scene                 |
| `/gamemaster_continue` | Continue existing scene with prompt     |
| `/gamemaster_stop`     | Archive or end the RP session           |
| `/podrace`             | Start a Pod Racing economy game         |

---

## 📦 Folder Structure

```
├── bot.py
├── utils.py
├── cogs/
│   ├── bounty_cog.py
│   ├── chat_cog.py
│   ├── dev_cog.py
│   ├── econ_cog.py
│   ├── gm_cog.py
│   ├── mission_cog.py
│   └── news_cog.py
├── db/
│   ├── models.py
│   └── sessions.py
├── .env
├── requirements.txt
└── README.md
```

---

## 🛡️ Permissions

This bot uses **role-based access**:

* Users with `Moderator`, `Mod`, `Mods`, or `Moderators` can create, edit, change status, delete, and generate missions and bounties.
* Users with the `Game Master` role can trigger AI GM sessions and use Game Master session commands.

---

Made with ⚔️ by roleplayers, for roleplayers.

