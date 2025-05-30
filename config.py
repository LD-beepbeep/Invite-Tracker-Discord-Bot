import os

# Bot configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
LEADERBOARD_TIME = os.getenv("LEADERBOARD_TIME", "09:00")  # 24-hour format
DATABASE_PATH = "invite_stats.db"

# Bot permissions required
REQUIRED_PERMISSIONS = [
    "view_channel",
    "send_messages",
    "embed_links",
    "manage_guild",
    "read_message_history"
]

# Embed colors
EMBED_COLOR = 0x5865F2  # Discord blurple
ERROR_COLOR = 0xED4245   # Discord red
SUCCESS_COLOR = 0x57F287 # Discord green
