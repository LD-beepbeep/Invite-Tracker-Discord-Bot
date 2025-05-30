import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, time
import os

from config import BOT_TOKEN, LEADERBOARD_CHANNEL_ID, LEADERBOARD_TIME, DATABASE_PATH
from database import InviteDatabase
from invite_tracker import InviteTracker
from leaderboard import LeaderboardManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InviteBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.invites = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # Initialize database and managers
        self.db = InviteDatabase(DATABASE_PATH)
        self.invite_tracker = InviteTracker(self, self.db)
        self.leaderboard_manager = LeaderboardManager(self, self.db)
        
        # Track initialization status
        self._is_ready = False
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Start the daily leaderboard task
        self.daily_leaderboard.start()
        logger.info("Daily leaderboard task started")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        if not self._is_ready:
            logger.info(f'{self.user} has connected to Discord!')
            logger.info(f'Bot is in {len(self.guilds)} guilds')
            
            # Log guild details
            for guild in self.guilds:
                logger.info(f'Connected to guild: {guild.name} (ID: {guild.id})')
                await self.invite_tracker.cache_invites(guild)
                await self.invite_tracker.update_invite_counts(guild)
            
            self._is_ready = True
        
        # Update activity status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="invite statistics | !help"
        )
        await self.change_presence(activity=activity)
    
    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        await self.invite_tracker.cache_invites(guild)
        await self.invite_tracker.update_invite_counts(guild)
    
    async def on_invite_create(self, invite):
        """Called when an invite is created"""
        await self.invite_tracker.on_invite_create(invite)
    
    async def on_invite_delete(self, invite):
        """Called when an invite is deleted"""
        await self.invite_tracker.on_invite_delete(invite)
    
    async def on_member_join(self, member):
        """Called when a member joins a guild"""
        await self.invite_tracker.on_member_join(member)
    
    @tasks.loop(time=time.fromisoformat(LEADERBOARD_TIME))
    async def daily_leaderboard(self):
        """Post daily leaderboard at scheduled time"""
        if not self._is_ready:
            return
        
        try:
            if LEADERBOARD_CHANNEL_ID:
                channel = self.get_channel(LEADERBOARD_CHANNEL_ID)
                if channel and hasattr(channel, 'send'):
                    await self.leaderboard_manager.post_daily_leaderboard(channel)
                else:
                    logger.warning(f"Leaderboard channel {LEADERBOARD_CHANNEL_ID} not found or not a text channel")
            else:
                logger.info("No leaderboard channel configured, skipping daily post")
                
        except Exception as e:
            logger.error(f"Error in daily leaderboard task: {e}")
    
    @daily_leaderboard.before_loop
    async def before_daily_leaderboard(self):
        """Wait until the bot is ready before starting the loop"""
        await self.wait_until_ready()

# Initialize the bot
bot = InviteBot()

@bot.event
async def on_message(message):
    """Log all messages for debugging"""
    if message.author == bot.user:
        return
    
    logger.info(f"Received message: '{message.content}' from {message.author} in {message.guild.name if message.guild else 'DM'}")
    await bot.process_commands(message)

@bot.command(name='help')
async def help_command(ctx):
    """Show help information"""
    logger.info(f"Help command called by {ctx.author} in {ctx.guild.name}")
    embed = discord.Embed(
        title="🤖 Invite Tracker Bot Commands",
        description="Track and display server invite statistics",
        color=0x5865F2
    )
    
    embed.add_field(
        name="📊 !leaderboard",
        value="Show all-time invite leaderboard",
        inline=False
    )
    
    embed.add_field(
        name="📅 !daily",
        value="Show weekly invite leaderboard",
        inline=False
    )
    
    embed.add_field(
        name="📈 !stats [@user]",
        value="Show invite statistics for yourself or mentioned user",
        inline=False
    )
    
    embed.add_field(
        name="🔄 !refresh",
        value="Refresh invite cache (Admin only)",
        inline=False
    )
    
    embed.set_footer(text="Use these commands to track invite performance!")
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard_command(ctx):
    """Show the all-time invite leaderboard"""
    async with ctx.typing():
        await bot.leaderboard_manager.send_leaderboard(ctx, "all")

@bot.command(name='daily', aliases=['weekly', 'recent'])
async def daily_leaderboard_command(ctx):
    """Show the weekly invite leaderboard"""
    async with ctx.typing():
        await bot.leaderboard_manager.send_leaderboard(ctx, "daily")

@bot.command(name='stats', aliases=['me', 'invites'])
async def stats_command(ctx, user: discord.Member = None):
    """Show invite statistics for a user"""
    async with ctx.typing():
        await bot.leaderboard_manager.send_user_stats(ctx, user)

@bot.command(name='refresh')
@commands.has_permissions(administrator=True)
async def refresh_command(ctx):
    """Refresh the invite cache (Admin only)"""
    try:
        async with ctx.typing():
            await bot.invite_tracker.cache_invites(ctx.guild)
            await bot.invite_tracker.update_invite_counts(ctx.guild)
        
        embed = discord.Embed(
            title="✅ Success",
            description="Invite cache has been refreshed!",
            color=0x57F287
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description="Failed to refresh invite cache. Check bot permissions.",
            color=0xED4245
        )
        await ctx.send(embed=embed)

@refresh_command.error
async def refresh_error(ctx, error):
    """Handle refresh command errors"""
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need Administrator permissions to use this command.",
            color=0xED4245
        )
        await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You don't have permission to use this command.",
            color=0xED4245
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ Invalid Argument",
            description="Please check your command arguments and try again.",
            color=0xED4245
        )
        await ctx.send(embed=embed)
    
    else:
        logger.error(f"Unhandled command error: {error}")
        embed = discord.Embed(
            title="❌ An Error Occurred",
            description="Something went wrong while processing your command.",
            color=0xED4245
        )
        await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN environment variable is required!")
        exit(1)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid bot token provided!")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
