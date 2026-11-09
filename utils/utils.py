import discord
from discord import app_commands, Embed
import pickle
import os
import json
import tempfile


# CONFIG VARS
NEWS_URL = os.getenv("NEWS_URL", "")
GUILD_ID = 1389425312915263509
ACCEPTED_CHANNEL = 1389426127998681098
CREDITS_EMOJI = "<:credits:1389546063131709470>"
WELCOME_CHANNEL = 1389427938801352877
GM_REPORT_CHANNEL = 1389427228156367008

FACTION_CHOICES = [
    app_commands.Choice(name="Rogue", value="Rogue"),
    app_commands.Choice(name="Imperial", value="Imperial"),
    app_commands.Choice(name="Rebel", value="Rebel"),
    app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    app_commands.Choice(name="CIS", value="CIS"),
]

FACTION_COLORS = {
    "Rogue": discord.Colour.from_rgb(220, 20, 60),
    "Imperial": discord.Colour.from_rgb(0, 0, 0),
    "Rebel": discord.Colour.from_rgb(255, 165, 0),
    "Mandalorian": discord.Colour.from_rgb(149, 0, 255),
    "CIS": discord.Colour.from_rgb(21, 20, 96)
}

FACTION_IMAGES = {
    "Rogue": "https://i.imgur.com/uCBMMIp.png",
    "Imperial": "https://i.imgur.com/KJTcuKs.png",
    "Rebel": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Resistance_Emblem_Star_Wars.svg/640px-Resistance_Emblem_Star_Wars.svg.png",
    "Mandalorian": "https://i.imgur.com/luSCnmV.png",
    "CIS": "https://i.imgur.com/vrvhYl4.png"
}


def get_nochat_channels():
    try:
        with open('nochat_channels.pkl', 'rb') as dbfile:
            no_chat_channels = pickle.load(dbfile)
    except (FileNotFoundError, EOFError):
        no_chat_channels = []
        with open('nochat_channels.pkl', 'wb') as dbfile:
            pickle.dump(no_chat_channels, dbfile)
    return no_chat_channels


def load_rp_sessions():
    """Return a list of active session IDs"""
    sessions_dir = "sessions"

    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir)
        return []

    session_ids = []
    for filename in os.listdir(sessions_dir):
        if filename.endswith('.json'):
            try:
                session_id = int(filename.replace('.json', ''))
                session_ids.append(session_id)
            except ValueError:
                continue

    return session_ids


def load_session(channel_id):
    """Load a specific session"""
    filepath = f"sessions/{channel_id}.json"

    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        restored_recent = []

        for msg in session_data.get("recent", []):
            if not isinstance(msg, dict):
                continue

            # Older files store message text under ``text``.  Keep every
            # other field (including turn message IDs) when normalizing so a
            # later save does not discard data added by newer versions.
            restored_msg = dict(msg)
            restored_msg["role"] = msg.get("role", "user")
            restored_msg["content"] = msg.get("content", msg.get("text", "")) or ""
            restored_recent.append(restored_msg)

        session_data["recent"] = restored_recent
        session_data.setdefault("scene_info", {})
        session_data.setdefault("summary", "")
        session_data.setdefault("char_list", {})

        return session_data

    except Exception as e:
        print(f"Error loading session {channel_id}: {e}")
        return None



def save_session(channel_id, session_data):
    """Save a specific session"""
    os.makedirs("sessions", exist_ok=True)
    filepath = f"sessions/{channel_id}.json"

    try:
        simplified_recent = []

        for msg in session_data.get("recent", []):
            if not msg:
                continue

            if isinstance(msg, dict) and "role" in msg:
                # Persist the legacy ``text`` shape, while retaining all
                # JSON-safe metadata used by current turns (for example the
                # exact Discord message IDs needed by undo).
                persisted_msg = dict(msg)
                content = persisted_msg.pop("content", persisted_msg.get("text", ""))
                persisted_msg["role"] = msg.get("role", "unknown")
                persisted_msg["text"] = content if isinstance(content, str) else ""
                simplified_recent.append(persisted_msg)
                continue

            if hasattr(msg, "role") and hasattr(msg, "parts"):
                text = ""

                if msg.parts and hasattr(msg.parts[0], "text"):
                    text = msg.parts[0].text or ""

                simplified_recent.append({
                    "role": msg.role,
                    "text": text
                })

        # Start from the complete session so fields from legacy/newer files
        # survive a write.  Only the in-memory recent-message representation
        # needs conversion for JSON storage.
        persisted_session = dict(session_data)
        persisted_session["scene_info"] = session_data.get("scene_info", {})
        persisted_session["summary"] = session_data.get("summary", "")
        persisted_session["char_list"] = session_data.get("char_list", {})
        persisted_session["recent"] = simplified_recent

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=f".{channel_id}.", suffix=".tmp", dir=os.path.dirname(filepath) or "."
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(persisted_session, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, filepath)
            temp_path = None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        print(f"Error saving session {channel_id}: {e}")


def delete_session(channel_id):
    """Delete a session file, returning whether an active file existed."""
    filepath = f"sessions/{channel_id}.json"
    try:
        os.remove(filepath)
        return True
    except FileNotFoundError:
        return False
