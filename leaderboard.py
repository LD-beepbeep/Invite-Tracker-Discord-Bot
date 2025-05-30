import discord
from discord.ext import commands
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LeaderboardManager:
    def __init__(self, bot: commands.Bot, database):
        self.bot = bot
        self.db = database
    
    async def create_leaderboard_embed(self, guild: discord.Guild, leaderboard_type: str = "all") -> discord.Embed:
        """Create a leaderboard embed"""
        try:
            if leaderboard_type == "daily":
                data = await self.db.get_daily_leaderboard(guild.id, days=7, limit=10)
                title = "📊 Weekly Invite Leaderboard"
                description = "Top inviters from the past 7 days"
                value_label = "Recent Invites"
            else:
                data = await self.db.get_leaderboard(guild.id, limit=10)
                title = "🏆 All-Time Invite Leaderboard"
                description = "Top inviters of all time"
                value_label = "Total Invites Used"
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            if not data:
                embed.add_field(
                    name="No Data Available",
                    value="No invite statistics found for this server.",
                    inline=False
                )
                return embed
            
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]
            
            for i, entry in enumerate(data):
                if leaderboard_type == "daily":
                    user_id, invite_count = entry
                else:
                    user_id, total_invites, invite_count = entry
                
                # Get user object
                user = guild.get_member(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        username = f"{user.name} (Left Server)"
                    except:
                        username = f"Unknown User ({user_id})"
                else:
                    username = user.display_name
                
                # Add medal for top 3
                medal = medals[i] if i < 3 else f"{i + 1}."
                
                leaderboard_text += f"{medal} **{username}** - {invite_count} {value_label.lower()}\n"
            
            embed.add_field(
                name=value_label,
                value=leaderboard_text or "No data available",
                inline=False
            )
            
            embed.set_footer(
                text=f"Requested by {guild.name}",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating leaderboard embed: {e}")
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while generating the leaderboard.",
                color=0xED4245
            )
            return error_embed
    
    async def create_user_stats_embed(self, guild: discord.Guild, user: discord.Member) -> discord.Embed:
        """Create an embed showing individual user statistics"""
        try:
            total_invites, total_uses = await self.db.get_user_stats(guild.id, user.id)
            
            embed = discord.Embed(
                title=f"📈 Invite Statistics for {user.display_name}",
                color=0x5865F2,
                timestamp=datetime.now()
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            
            embed.add_field(
                name="Total Invites Created",
                value=str(total_invites),
                inline=True
            )
            
            embed.add_field(
                name="Total Successful Invites",
                value=str(total_uses),
                inline=True
            )
            
            # Calculate success rate
            if total_invites > 0:
                success_rate = (total_uses / total_invites) * 100
                embed.add_field(
                    name="Success Rate",
                    value=f"{success_rate:.1f}%",
                    inline=True
                )
            
            embed.set_footer(text=f"User ID: {user.id}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating user stats embed: {e}")
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while fetching user statistics.",
                color=0xED4245
            )
            return error_embed
    
    async def post_daily_leaderboard(self, channel: discord.TextChannel):
        """Post the daily leaderboard to a specific channel"""
        try:
            embed = await self.create_leaderboard_embed(channel.guild, "daily")
            
            # Add special daily message
            embed.description += f"\n\n*Automatically posted at {datetime.now().strftime('%H:%M')} UTC*"
            
            await channel.send(embed=embed)
            logger.info(f"Posted daily leaderboard to {channel.name} in {channel.guild.name}")
            
        except discord.Forbidden:
            logger.error(f"No permission to send messages in {channel.name}")
        except Exception as e:
            logger.error(f"Error posting daily leaderboard: {e}")
    
    async def send_leaderboard(self, ctx: commands.Context, leaderboard_type: str = "all"):
        """Send leaderboard in response to a command"""
        try:
            embed = await self.create_leaderboard_embed(ctx.guild, leaderboard_type)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending leaderboard: {e}")
            await ctx.send("❌ An error occurred while generating the leaderboard.")
    
    async def send_user_stats(self, ctx: commands.Context, user: discord.Member = None):
        """Send user statistics in response to a command"""
        try:
            if user is None:
                user = ctx.author
            
            embed = await self.create_user_stats_embed(ctx.guild, user)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending user stats: {e}")
            await ctx.send("❌ An error occurred while fetching user statistics.")
