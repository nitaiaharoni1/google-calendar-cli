"""Utility functions for Calendar CLI."""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from .shared_auth import (
    get_default_account as _get_default_account,
    set_default_account as _set_default_account,
    list_accounts as _list_accounts,
    remove_account as _remove_account,
    set_account_alias as _set_account_alias,
    remove_account_alias as _remove_account_alias,
    get_account_aliases as _get_account_aliases,
    resolve_account as _resolve_account,
    get_token_path as _get_token_path,
    get_credentials_path as _get_credentials_path,
    ensure_token_permissions as _ensure_token_permissions,
)


def get_default_account():
    """Get the default account name."""
    return _get_default_account("calendar")


def set_default_account(account_name):
    """Set the default account name."""
    _set_default_account(account_name)


def list_accounts():
    """List all configured accounts."""
    return _list_accounts()


def remove_account(account_name):
    """Remove an account and its token."""
    return _remove_account(account_name)


def set_account_alias(alias, account_email):
    """Set an alias for an account."""
    return _set_account_alias(alias, account_email)


def remove_account_alias(alias):
    """Remove an account alias."""
    return _remove_account_alias(alias)


def get_account_aliases():
    """Get all account aliases."""
    return _get_account_aliases()


def resolve_account(account_or_alias):
    """Resolve an account name or alias to the actual account email."""
    return _resolve_account(account_or_alias)


def get_token_path(account=None):
    """Get the path to the token file for a specific account."""
    return _get_token_path(account, "calendar")


def get_credentials_path():
    """Get the path to credentials.json file."""
    return _get_credentials_path()


def ensure_token_permissions(token_path):
    """Ensure token file has secure permissions (600)."""
    _ensure_token_permissions(token_path)


def parse_datetime(date_string):
    """Parse datetime string in various formats."""
    if not date_string:
        return None
    
    try:
        # Try parsing with dateutil
        return date_parser.parse(date_string)
    except:
        # Fallback to common formats
        try:
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        except:
            return None


def format_datetime(dt, include_time=True):
    """Format datetime for display, converting to user's timezone."""
    if not dt:
        return ""
    
    if isinstance(dt, str):
        dt = parse_datetime(dt)
    
    if not dt:
        return ""
    
    # Convert to user's timezone if datetime is timezone-aware
    if dt.tzinfo is not None:
        from .config import get_preference
        from zoneinfo import ZoneInfo
        user_tz_str = get_preference('timezone', 'UTC')
        try:
            user_tz = ZoneInfo(user_tz_str)
            dt = dt.astimezone(user_tz)
        except Exception:
            # If timezone conversion fails, use as-is
            pass
    
    if include_time:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return dt.strftime("%Y-%m-%d")


def get_today_start():
    """Get start of today in user's timezone, returned as UTC naive datetime for API compatibility."""
    from .config import get_preference
    from zoneinfo import ZoneInfo
    from datetime import timezone as tz_module
    
    user_tz_str = get_preference('timezone', 'UTC')
    try:
        user_tz = ZoneInfo(user_tz_str)
        # Get current time in user's timezone
        now = datetime.now(user_tz)
        # Get start of today in user's timezone
        today_start_local = datetime(now.year, now.month, now.day, tzinfo=user_tz)
        # Convert to UTC and return as naive datetime (API expects UTC)
        today_start_utc = today_start_local.astimezone(tz_module.utc)
        return today_start_utc.replace(tzinfo=None)
    except Exception:
        # Fallback to UTC
        now = datetime.utcnow()
        return datetime(now.year, now.month, now.day)


def get_week_start():
    """Get start of current week (Monday) in user's timezone."""
    today = get_today_start()
    days_since_monday = today.weekday()
    return today - timedelta(days=days_since_monday)


def get_week_end():
    """Get end of current week (Sunday) in UTC."""
    return get_week_start() + timedelta(days=7)

