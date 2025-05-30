import discord
from discord.ext import commands
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class InviteTracker:
    def __init__(self, bot: commands.Bot, database):
        self.bot = bot
        self.db = database
        self.invite_cache: Dict[int, Dict[str, discord.Invite]] = {}
    
    async def cache_invites(self, guild: discord.Guild):
        """Cache all invites for a guild"""
        try:
            if not guild.me.guild_permissions.manage_guild:
                logger.warning(f"Missing manage_guild permission in {guild.name}")
                return
            
            invites = await guild.invites()
            self.invite_cache[guild.id] = {}
            
            for invite in invites:
                self.invite_cache[guild.id][invite.code] = invite
                
                # Store in database
                expires_at = invite.expires_at if invite.expires_at else None
                await self.db.add_invite(
                    invite.code,
                    guild.id,
                    invite.inviter.id if invite.inviter else 0,
                    invite.max_uses,
                    expires_at
                )
                
                # Update usage count
                await self.db.update_invite_usage(invite.code, invite.uses)
            
            logger.info(f"Cached {len(invites)} invites for guild {guild.name}")
            
        except discord.Forbidden:
            logger.warning(f"No permission to access invites in guild {guild.name}. Bot needs 'Manage Server' permission.")
        except Exception as e:
            logger.error(f"Error caching invites for guild {guild.name}: {e}")
    
    async def update_invite_counts(self, guild: discord.Guild):
        """Update invite counts for all members"""
        try:
            if guild.id not in self.invite_cache:
                await self.cache_invites(guild)
                return
            
            invite_counts = {}
            for invite in self.invite_cache[guild.id].values():
                if invite.inviter:
                    invite_counts[invite.inviter.id] = invite_counts.get(invite.inviter.id, 0) + 1
            
            # Update database with current invite counts
            for user_id, count in invite_counts.items():
                await self.db.update_invite_count(guild.id, user_id, count)
                
        except Exception as e:
            logger.error(f"Error updating invite counts: {e}")
    
    async def on_invite_create(self, invite: discord.Invite):
        """Handle invite creation"""
        try:
            guild = invite.guild
            if guild.id not in self.invite_cache:
                self.invite_cache[guild.id] = {}
            
            self.invite_cache[guild.id][invite.code] = invite
            
            # Store in database
            expires_at = invite.expires_at if invite.expires_at else None
            await self.db.add_invite(
                invite.code,
                guild.id,
                invite.inviter.id if invite.inviter else 0,
                invite.max_uses,
                expires_at
            )
            
            # Update invite count for the user
            await self.update_invite_counts(guild)
            
            logger.debug(f"Invite {invite.code} created by {invite.inviter}")
            
        except Exception as e:
            logger.error(f"Error handling invite creation: {e}")
    
    async def on_invite_delete(self, invite: discord.Invite):
        """Handle invite deletion"""
        try:
            guild = invite.guild
            if guild.id in self.invite_cache and invite.code in self.invite_cache[guild.id]:
                del self.invite_cache[guild.id][invite.code]
            
            # Mark as inactive in database
            await self.db.remove_invite(invite.code)
            
            # Update invite count for the user
            await self.update_invite_counts(guild)
            
            logger.debug(f"Invite {invite.code} deleted")
            
        except Exception as e:
            logger.error(f"Error handling invite deletion: {e}")
    
    async def on_member_join(self, member: discord.Member):
        """Handle member join and track which invite was used"""
        try:
            guild = member.guild
            
            if not guild.me.guild_permissions.manage_guild:
                logger.warning(f"Missing manage_guild permission to track invites in {guild.name}")
                return
            
            # Get current invites
            current_invites = await guild.invites()
            current_invite_dict = {invite.code: invite for invite in current_invites}
            
            # Compare with cached invites to find which one was used
            if guild.id in self.invite_cache:
                for code, old_invite in self.invite_cache[guild.id].items():
                    if code in current_invite_dict:
                        current_invite = current_invite_dict[code]
                        
                        # Check if usage increased
                        if current_invite.uses > old_invite.uses:
                            # This invite was used
                            inviter_id = old_invite.inviter.id if old_invite.inviter else 0
                            
                            if inviter_id:
                                await self.db.record_invite_use(guild.id, inviter_id)
                                logger.info(f"Member {member} joined using invite by {old_invite.inviter}")
                            
                            # Update cache
                            self.invite_cache[guild.id][code] = current_invite
                            await self.db.update_invite_usage(code, current_invite.uses)
                            break
                    else:
                        # Invite was deleted/expired, might have been a one-time use
                        if old_invite.max_uses == 1:
                            inviter_id = old_invite.inviter.id if old_invite.inviter else 0
                            
                            if inviter_id:
                                await self.db.record_invite_use(guild.id, inviter_id)
                                logger.info(f"Member {member} joined using one-time invite by {old_invite.inviter}")
                            
                            # Remove from cache
                            if code in self.invite_cache[guild.id]:
                                del self.invite_cache[guild.id][code]
                            break
            
            # Refresh cache with current invites
            await self.cache_invites(guild)
            
        except discord.Forbidden:
            logger.error(f"No permission to track invites in guild {guild.name}")
        except Exception as e:
            logger.error(f"Error tracking member join: {e}")
    
    async def get_invite_stats(self, guild: discord.Guild, user: discord.Member) -> tuple:
        """Get invite statistics for a user"""
        try:
            return await self.db.get_user_stats(guild.id, user.id)
        except Exception as e:
            logger.error(f"Error getting invite stats: {e}")
            return (0, 0)
