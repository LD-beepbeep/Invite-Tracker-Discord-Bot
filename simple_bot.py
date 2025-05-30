import discord
from discord.ext import commands
import os

# Simple bot to test connection
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds:')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id})')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

# Run the bot
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("DISCORD_BOT_TOKEN environment variable is required!")
        exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Invalid bot token provided!")
    except Exception as e:
        print(f"Failed to start bot: {e}")