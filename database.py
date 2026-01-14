"""
Database initialization and connection management for NewsieAI.
Uses SQLite for local storage of user profiles.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

# Get database path from environment or use default
BASE_DIR = Path(__file__).resolve().parent
DB_PATH_ENV = os.getenv("DATABASE_PATH")
if DB_PATH_ENV:
    DB_PATH = Path(DB_PATH_ENV)
else:
    # Default: store in backend/data directory
    DB_PATH = BASE_DIR / "data" / "newsieai.db"

# Ensure data directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_database():
    """
    Initialize the SQLite database and create tables if they don't exist.
    Enables WAL mode for better concurrent access.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    
    # Set other performance optimizations
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, still safe
    cursor.execute("PRAGMA cache_size=10000")  # Increase cache size
    cursor.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
    
    # Create user_profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            timezone TEXT DEFAULT 'UTC',
            preferred_notification_times TEXT,  -- JSON array as string
            content_preferences TEXT,  -- JSON array as string
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index on email for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_email ON user_profiles(email)
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH} (WAL mode enabled)")


def get_connection():
    """
    Get a database connection with WAL mode enabled for better concurrency.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    
    # Ensure WAL mode is enabled (in case it wasn't set during init)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass  # Ignore if already set or not supported
    
    return conn


def save_user_profile(profile: Dict[str, Any]) -> bool:
    """
    Save or update a user profile in the database.
    
    Args:
        profile: User profile dictionary with keys:
            - user_id: str
            - name: str
            - email: str
            - timezone: str (default: UTC)
            - preferred_notification_times: List[str]
            - content_preferences: List[str]
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convert lists to JSON strings
        notification_times_json = json.dumps(profile.get("preferred_notification_times", []))
        content_prefs_json = json.dumps(profile.get("content_preferences", []))
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM user_profiles WHERE user_id = ?", (profile["user_id"],))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing profile
            cursor.execute("""
                UPDATE user_profiles
                SET name = ?,
                    email = ?,
                    timezone = ?,
                    preferred_notification_times = ?,
                    content_preferences = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                profile["name"],
                profile["email"],
                profile.get("timezone", "UTC"),
                notification_times_json,
                content_prefs_json,
                profile["user_id"]
            ))
        else:
            # Insert new profile
            cursor.execute("""
                INSERT INTO user_profiles 
                (user_id, name, email, timezone, preferred_notification_times, content_preferences)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                profile["user_id"],
                profile["name"],
                profile["email"],
                profile.get("timezone", "UTC"),
                notification_times_json,
                content_prefs_json
            ))
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error saving profile: {e}")
        return False


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user profile by user_id.
    
    Args:
        user_id: User identifier
    
    Returns:
        Dict with user profile or None if not found
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM user_profiles WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Convert row to dictionary
            profile = dict(row)
            # Parse JSON strings back to lists
            profile["preferred_notification_times"] = json.loads(
                profile["preferred_notification_times"] or "[]"
            )
            profile["content_preferences"] = json.loads(
                profile["content_preferences"] or "[]"
            )
            return profile
        
        return None
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    except Exception as e:
        print(f"Error retrieving profile: {e}")
        return None


def get_user_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user profile by email.
    
    Args:
        email: User email address
    
    Returns:
        Dict with user profile or None if not found
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM user_profiles WHERE email = ?
        """, (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            profile = dict(row)
            profile["preferred_notification_times"] = json.loads(
                profile["preferred_notification_times"] or "[]"
            )
            profile["content_preferences"] = json.loads(
                profile["content_preferences"] or "[]"
            )
            return profile
        
        return None
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    except Exception as e:
        print(f"Error retrieving profile: {e}")
        return None


def list_all_profiles() -> List[Dict[str, Any]]:
    """
    List all user profiles in the database.
    
    Returns:
        List of user profile dictionaries
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_profiles ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        profiles = []
        for row in rows:
            profile = dict(row)
            profile["preferred_notification_times"] = json.loads(
                profile["preferred_notification_times"] or "[]"
            )
            profile["content_preferences"] = json.loads(
                profile["content_preferences"] or "[]"
            )
            profiles.append(profile)
        
        return profiles
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    except Exception as e:
        print(f"Error listing profiles: {e}")
        return []


if __name__ == "__main__":
    # Initialize database when run directly
    print("Initializing NewsieAI database...")
    init_database()
    print("Database initialization complete!")

