import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class InviteDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table for tracking invite statistics
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS invite_stats (
                        user_id INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL,
                        total_invites INTEGER DEFAULT 0,
                        total_uses INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, guild_id)
                    )
                """)
                
                # Table for tracking individual invites
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS invites (
                        invite_code TEXT PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        inviter_id INTEGER NOT NULL,
                        uses INTEGER DEFAULT 0,
                        max_uses INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # Table for tracking daily statistics
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_stats (
                        user_id INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        invites_used INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, guild_id, date)
                    )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
    
    async def add_invite(self, invite_code: str, guild_id: int, inviter_id: int, 
                        max_uses: Optional[int] = None, expires_at: Optional[datetime] = None):
        """Add a new invite to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO invites 
                    (invite_code, guild_id, inviter_id, max_uses, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (invite_code, guild_id, inviter_id, max_uses, expires_at))
                conn.commit()
                logger.debug(f"Added invite {invite_code} for user {inviter_id}")
        except sqlite3.Error as e:
            logger.error(f"Error adding invite: {e}")
    
    async def update_invite_usage(self, invite_code: str, new_uses: int):
        """Update invite usage count"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invites SET uses = ? WHERE invite_code = ?
                """, (new_uses, invite_code))
                conn.commit()
                logger.debug(f"Updated invite {invite_code} usage to {new_uses}")
        except sqlite3.Error as e:
            logger.error(f"Error updating invite usage: {e}")
    
    async def remove_invite(self, invite_code: str):
        """Mark an invite as inactive"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invites SET is_active = FALSE WHERE invite_code = ?
                """, (invite_code,))
                conn.commit()
                logger.debug(f"Marked invite {invite_code} as inactive")
        except sqlite3.Error as e:
            logger.error(f"Error removing invite: {e}")
    
    async def record_invite_use(self, guild_id: int, inviter_id: int):
        """Record that an invite was used"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update total stats
                cursor.execute("""
                    INSERT OR IGNORE INTO invite_stats (user_id, guild_id, total_uses)
                    VALUES (?, ?, 0)
                """, (inviter_id, guild_id))
                
                cursor.execute("""
                    UPDATE invite_stats 
                    SET total_uses = total_uses + 1, last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ?
                """, (inviter_id, guild_id))
                
                # Update daily stats
                cursor.execute("""
                    INSERT OR IGNORE INTO daily_stats (user_id, guild_id, date, invites_used)
                    VALUES (?, ?, ?, 0)
                """, (inviter_id, guild_id, today))
                
                cursor.execute("""
                    UPDATE daily_stats 
                    SET invites_used = invites_used + 1
                    WHERE user_id = ? AND guild_id = ? AND date = ?
                """, (inviter_id, guild_id, today))
                
                conn.commit()
                logger.debug(f"Recorded invite use for user {inviter_id}")
        except sqlite3.Error as e:
            logger.error(f"Error recording invite use: {e}")
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Tuple[int, int, int]]:
        """Get invite leaderboard for a guild"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, total_invites, total_uses
                    FROM invite_stats
                    WHERE guild_id = ?
                    ORDER BY total_uses DESC, total_invites DESC
                    LIMIT ?
                """, (guild_id, limit))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    async def get_daily_leaderboard(self, guild_id: int, days: int = 7, limit: int = 10) -> List[Tuple[int, int]]:
        """Get daily invite leaderboard for specified number of days"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, SUM(invites_used) as recent_uses
                    FROM daily_stats
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY user_id
                    ORDER BY recent_uses DESC
                    LIMIT ?
                """, (guild_id, cutoff_date, limit))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting daily leaderboard: {e}")
            return []
    
    async def get_user_stats(self, guild_id: int, user_id: int) -> Optional[Tuple[int, int]]:
        """Get statistics for a specific user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_invites, total_uses
                    FROM invite_stats
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                result = cursor.fetchone()
                return result if result else (0, 0)
        except sqlite3.Error as e:
            logger.error(f"Error getting user stats: {e}")
            return (0, 0)
    
    async def update_invite_count(self, guild_id: int, user_id: int, invite_count: int):
        """Update the total invite count for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO invite_stats (user_id, guild_id, total_invites)
                    VALUES (?, ?, 0)
                """, (user_id, guild_id))
                
                cursor.execute("""
                    UPDATE invite_stats 
                    SET total_invites = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ?
                """, (invite_count, user_id, guild_id))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error updating invite count: {e}")
