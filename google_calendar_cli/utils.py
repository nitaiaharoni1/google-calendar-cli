"""Utility functions for Calendar CLI."""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as date_parser


def get_accounts_config_path():
    """Get the path to accounts configuration file."""
    return Path.home() / ".google_calendar_accounts.json"


def get_default_account():
    """Get the default account name."""
    config_path = get_accounts_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("default_account")
        except:
            pass
    return None


def set_default_account(account_name):
    """Set the default account name."""
    config_path = get_accounts_config_path()
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except:
            pass
    
    config["default_account"] = account_name
    if "accounts" not in config:
        config["accounts"] = []
    if account_name not in config["accounts"]:
        config["accounts"].append(account_name)
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    ensure_token_permissions(config_path)


def list_accounts():
    """List all configured accounts."""
    config_path = get_accounts_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("accounts", [])
        except:
            pass
    return []


def get_token_path(account=None):
    """Get the path to the token file for a specific account."""
    if account is None:
        account = get_default_account()
    
    if account:
        return Path.home() / f".google_calendar_token_{account}.json"
    else:
        # Legacy: default token file
        return Path.home() / ".google_calendar_token.json"


def get_credentials_path():
    """Get the path to credentials.json file."""
    # Check current directory first
    current_dir = Path.cwd() / "credentials.json"
    if current_dir.exists():
        return current_dir
    
    # Check home directory
    home_dir = Path.home() / "credentials.json"
    if home_dir.exists():
        return home_dir
    
    return None


def ensure_token_permissions(token_path):
    """Ensure token file has secure permissions (600)."""
    if token_path.exists():
        os.chmod(token_path, 0o600)


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
    """Format datetime for display."""
    if not dt:
        return ""
    
    if isinstance(dt, str):
        dt = parse_datetime(dt)
    
    if not dt:
        return ""
    
    if include_time:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return dt.strftime("%Y-%m-%d")


def get_today_start():
    """Get start of today in UTC."""
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def get_week_start():
    """Get start of current week (Monday) in UTC."""
    today = get_today_start()
    days_since_monday = today.weekday()
    return today - timedelta(days=days_since_monday)


def get_week_end():
    """Get end of current week (Sunday) in UTC."""
    return get_week_start() + timedelta(days=7)

