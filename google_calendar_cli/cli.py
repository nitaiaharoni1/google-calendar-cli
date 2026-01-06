"""Google Calendar CLI - Main command-line interface."""

import click
import sys
import logging
import os
from datetime import datetime, timedelta, timezone
from .auth import authenticate, get_credentials, check_auth
from .api import CalendarAPI
from .utils import format_datetime, get_today_start, get_week_start, get_week_end, parse_datetime, list_accounts, remove_account, get_default_account, set_default_account, set_account_alias, remove_account_alias, get_account_aliases, resolve_account
from .shared_auth import check_token_health, refresh_token
from .config import get_preference, set_preference
from .templates import list_templates, get_template, create_template, delete_template, render_template
from .history import add_operation, get_recent_operations, get_last_undoable_operation


@click.group()
@click.version_option(version="1.4.0")
@click.option("--account", "-a", help="Account name to use (default: current default account or GOOGLE_CALENDAR_ACCOUNT env var)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging")
@click.pass_context
def cli(ctx, account, verbose):
    """Google Calendar CLI - Command-line interface for Google Calendar."""
    ctx.ensure_object(dict)
    # Resolve account: CLI arg > env var > default
    if account is None:
        account = os.getenv("GOOGLE_CALENDAR_ACCOUNT")
    if account is None:
        account = get_default_account()
    ctx.obj["ACCOUNT"] = account
    
    # Setup logging
    if verbose or get_preference("verbose", False):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logging.getLogger("googleapiclient").setLevel(logging.DEBUG)
        ctx.obj["VERBOSE"] = True
    else:
        logging.basicConfig(level=logging.WARNING)
        ctx.obj["VERBOSE"] = False


@cli.command(name="help")
@click.argument("command", required=False)
@click.pass_context
def help_command(ctx, command):
    """Show help message. Use 'help <command>' for command-specific help."""
    if command:
        # Show help for a specific command
        try:
            cmd = ctx.parent.command.get_command(ctx.parent, command)
            if cmd:
                click.echo(cmd.get_help(ctx))
            else:
                click.echo(f"❌ Unknown command: {command}", err=True)
                click.echo(f"\nAvailable commands:")
                for name in sorted(ctx.parent.command.list_commands(ctx.parent)):
                    click.echo(f"  {name}")
        except Exception:
            click.echo(f"❌ Unknown command: {command}", err=True)
            click.echo(f"\nAvailable commands:")
            for name in sorted(ctx.parent.command.list_commands(ctx.parent)):
                click.echo(f"  {name}")
    else:
        # Show main help
        if ctx.parent:
            click.echo(ctx.parent.get_help())
        else:
            click.echo(ctx.get_help())


# Account option decorator
def _resolve_account_callback(ctx, param, value):
    """Callback to resolve account aliases."""
    if value is not None:
        return resolve_account(value)
    return value


_account_option = click.option("--account", "-a", help="Account name or alias to use (default: current default account)", callback=_resolve_account_callback)


@cli.command()
def init():
    """Initialize and authenticate with Google Calendar API."""
    click.echo("🔐 Setting up Google Calendar authentication...")
    creds = authenticate()
    
    if creds:
        try:
            api = CalendarAPI()
            profile = api.get_profile()
            
            # Fetch and cache user settings
            settings = api.get_user_settings()
            if settings.get('timezone'):
                set_preference('timezone', settings['timezone'])
            if settings.get('dateFieldOrder'):
                set_preference('date_format', settings['dateFieldOrder'])
            if settings.get('weekStart'):
                set_preference('week_start', settings['weekStart'])
            
            # Cache user email from primary calendar
            if profile.get('id'):
                set_preference('user_email', profile.get('id'))
            
            click.echo(f"✅ Authenticated successfully!")
            if profile.get("summary"):
                click.echo(f"   Primary calendar: {profile.get('summary')}")
            if settings.get('timezone'):
                click.echo(f"   Timezone: {settings.get('timezone')}")
            
            click.echo(f"\n💡 Tip: Use 'google-calendar alias <name>' to set a friendly alias for this account.")
        except Exception as e:
            click.echo(f"⚠️  Authentication saved but verification failed: {e}")
    else:
        sys.exit(1)


@cli.command()
def accounts():
    """List all configured accounts and aliases."""
    accounts_list = list_accounts()
    aliases = get_account_aliases()
    default = get_default_account()
    
    if not accounts_list:
        click.echo("No accounts configured. Run 'google-calendar init' to add an account.")
        return
    
    # Build reverse mapping: account -> list of aliases
    account_aliases = {}
    for alias_name, account_email in aliases.items():
        if account_email not in account_aliases:
            account_aliases[account_email] = []
        account_aliases[account_email].append(alias_name)
    
    click.echo(f"Configured accounts ({len(accounts_list)}):\n")
    for acc in accounts_list:
        marker = " (default)" if acc == default else ""
        alias_list = account_aliases.get(acc, [])
        alias_str = f" (aliases: {', '.join(alias_list)})" if alias_list else ""
        click.echo(f"  • {acc}{marker}{alias_str}")
    
    if default:
        click.echo(f"\nDefault account: {default}")


@cli.command(name="remove-account")
@click.argument("account_name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def remove_account_cmd(account_name, force):
    """Remove an account and delete its authentication token.
    
    Examples:
        google-calendar remove-account test@example.com
        google-calendar remove-account work --force
    """
    accounts_list = list_accounts()
    
    if account_name not in accounts_list:
        click.echo(f"❌ Account '{account_name}' not found.", err=True)
        click.echo(f"\nAvailable accounts: {', '.join(accounts_list) if accounts_list else 'none'}", err=True)
        sys.exit(1)
    
    if not force:
        if not click.confirm(f"Remove account '{account_name}'? This will delete its authentication token."):
            click.echo("Cancelled.")
            return
    
    if remove_account(account_name):
        click.echo(f"✅ Account '{account_name}' removed successfully.")
        
        # Show new default if changed
        new_default = get_default_account()
        if new_default:
            click.echo(f"   New default account: {new_default}")
        else:
            click.echo("   No accounts remaining.")
    else:
        click.echo(f"❌ Failed to remove account '{account_name}'.", err=True)
        sys.exit(1)


@cli.command()
@click.argument("alias_name")
@click.argument("account_email", required=False)
@click.option("--remove", "-r", is_flag=True, help="Remove the alias")
def alias(alias_name, account_email, remove):
    """Set or remove an alias for an account.
    
    Examples:
        google-calendar alias work nitai@company.com    # Set alias
        google-calendar alias work --remove             # Remove alias
        google-calendar alias work                      # Show what alias points to
    """
    aliases = get_account_aliases()
    
    if remove:
        if remove_account_alias(alias_name):
            click.echo(f"✅ Alias '{alias_name}' removed.")
        else:
            click.echo(f"❌ Alias '{alias_name}' not found.", err=True)
            sys.exit(1)
        return
    
    if account_email is None:
        # Show what the alias points to
        if alias_name in aliases:
            click.echo(f"'{alias_name}' → {aliases[alias_name]}")
        else:
            click.echo(f"❌ Alias '{alias_name}' not found.", err=True)
            # Suggest available aliases
            if aliases:
                click.echo(f"\nAvailable aliases: {', '.join(aliases.keys())}")
            sys.exit(1)
        return
    
    # Set the alias
    if set_account_alias(alias_name, account_email):
        click.echo(f"✅ Alias set: '{alias_name}' → {account_email}")
    else:
        click.echo(f"❌ Account '{account_email}' not found.", err=True)
        accounts_list = list_accounts()
        if accounts_list:
            click.echo(f"\nAvailable accounts: {', '.join(accounts_list)}")
        sys.exit(1)


@cli.command()
@click.argument("account_name")
def use(account_name):
    """Set default account to use. Accepts account email or alias."""
    # Resolve alias to actual account
    resolved = resolve_account(account_name)
    accounts_list = list_accounts()
    
    if resolved not in accounts_list:
        click.echo(f"❌ Error: Account '{account_name}' not found.")
        click.echo(f"Available accounts: {', '.join(accounts_list)}")
        aliases = get_account_aliases()
        if aliases:
            click.echo(f"Available aliases: {', '.join(aliases.keys())}")
        click.echo("\nRun 'google-calendar init' to add a new account.")
        sys.exit(1)
    
    set_default_account(resolved)
    if resolved != account_name:
        click.echo(f"✅ Default account set to: {resolved} (via alias '{account_name}')")
    else:
        click.echo(f"✅ Default account set to: {resolved}")


@cli.group()
def auth():
    """Authentication management commands."""
    pass


@auth.command()
@click.option("--account", "-a", help="Check specific account (default: all accounts)")
def status(account):
    """Show token health status for account(s)."""
    from .auth import SCOPES
    
    accounts_to_check = [account] if account else list_accounts()
    
    if not accounts_to_check:
        click.echo("No accounts configured. Run 'google-calendar init' to add an account.")
        return
    
    for acc in accounts_to_check:
        health = check_token_health(acc, "calendar", SCOPES)
        status_icon = {
            "valid": "✅",
            "expired_refreshable": "⚠️",
            "expired": "❌",
            "scope_mismatch": "❌",
            "missing": "❌",
            "error": "❌"
        }.get(health["status"], "❓")
        
        click.echo(f"\n{status_icon} Account: {acc}")
        click.echo(f"   Status: {health['status']}")
        click.echo(f"   Message: {health.get('message', 'N/A')}")
        
        if health["status"] == "valid" and health.get("expires_in"):
            hours = health["expires_in"] // 3600
            days = hours // 24
            if days > 0:
                click.echo(f"   Expires in: {days} days, {hours % 24} hours")
            else:
                click.echo(f"   Expires in: {hours} hours")
        
        if health["status"] == "scope_mismatch":
            click.echo(f"   Current scopes: {', '.join(health.get('current_scopes', []))}")
            click.echo(f"   Required scopes: {', '.join(health.get('required_scopes', []))}")


@auth.command()
@click.option("--account", "-a", help="Refresh specific account (default: current default)")
@click.option("--all", is_flag=True, help="Refresh all accounts")
def refresh(account, all):
    """Refresh expired token(s)."""
    from .auth import SCOPES
    
    if all:
        accounts_to_refresh = list_accounts()
        if not accounts_to_refresh:
            click.echo("No accounts configured.")
            return
    else:
        accounts_to_refresh = [account or get_default_account()]
        if not accounts_to_refresh[0]:
            click.echo("❌ Error: No account specified and no default account set.")
            click.echo("Use --account <name> or run 'google-calendar init' first.")
            sys.exit(1)
    
    for acc in accounts_to_refresh:
        click.echo(f"\nRefreshing account: {acc}")
        creds = refresh_token(acc, "calendar", SCOPES)
        if creds:
            click.echo(f"✅ Token refreshed successfully for {acc}")
        else:
            click.echo(f"❌ Failed to refresh token for {acc}")
            click.echo(f"   Run 'google-calendar init --account {acc}' to re-authenticate.")


@cli.command()
@_account_option
@click.pass_context
def me(ctx, account):
    """Show authenticated user information."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        profile = api.get_profile()
        if profile:
            click.echo(f"📅 Primary Calendar: {profile.get('summary', 'Unknown')}")
            click.echo(f"   ID: {profile.get('id', 'N/A')}")
            click.echo(f"   Timezone: {profile.get('timeZone', 'N/A')}")
            
            # Show cached settings
            cached_tz = get_preference('timezone')
            if cached_tz and cached_tz != profile.get('timeZone'):
                click.echo(f"   Cached Timezone: {cached_tz}")
            
            date_format = get_preference('date_format')
            if date_format:
                click.echo(f"   Date Format: {date_format}")
        else:
            click.echo("No primary calendar found.")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--max", "-m", default=10, help="Maximum number of events")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
@click.pass_context
def list(ctx, max, calendar, account):
    """List upcoming events."""
    account = account or ctx.obj.get("ACCOUNT")
    try:
        api = CalendarAPI(account)
        now = datetime.utcnow()
        events = api.list_events(
            calendar_id=calendar,
            max_results=max,
            time_min=now.isoformat() + "Z",
        )
        
        if not events:
            click.echo("No upcoming events found.")
            return
        
        click.echo(f"Found {len(events)} upcoming events:\n")
        
        for event in events:
            event_id = event.get("id")
            summary = event.get("summary", "No Title")
            
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date")
            if start_time:
                start_dt = parse_datetime(start_time)
                start_str = format_datetime(start_dt) if start_dt else start_time
            else:
                start_str = "Unknown"
            
            location = event.get("location", "")
            
            click.echo(f"📅 {summary}")
            click.echo(f"   ID: {event_id}")
            click.echo(f"   Start: {start_str}")
            if location:
                click.echo(f"   Location: {location}")
            click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command(name="find-time")
@click.argument("attendees", nargs=-1, required=True)
@click.option("--duration", "-d", default=30, type=int, help="Meeting duration in minutes (default: 30)")
@click.option("--days", default=7, type=int, help="Days to search ahead (default: 7, ignored if --start/--end provided)")
@click.option("--start", "-s", help="Start date/time (flexible format, e.g., 'next Monday', '2026-01-15', 'Monday 9am')")
@click.option("--end", "-e", help="End date/time (flexible format, e.g., 'next Friday', '2026-01-20', 'Friday 6pm')")
@click.option("--start-hour", default=9, type=int, help="Working hours start (0-23, default: 9)")
@click.option("--end-hour", default=18, type=int, help="Working hours end (0-23, default: 18)")
@click.option("--exclude-weekends/--include-weekends", default=True, help="Exclude weekends (default: True)")
@click.option("--max-results", "-m", default=10, type=int, help="Maximum number of slots to show (default: 10)")
@click.option("--timezone", "-t", default=None, help="Timezone (default: from your calendar settings)")
@click.pass_context
@_account_option
def find_time(ctx, attendees, duration, days, start, end, start_hour, end_hour, exclude_weekends, max_results, timezone, account):
    """Find available meeting times when all attendees are free."""
    # Import timezone module with alias since parameter 'timezone' shadows it
    from datetime import timezone as tz_module
    # Use cached timezone if not provided
    tz_str = timezone if timezone is not None else get_preference('timezone', 'UTC')
    account = account or ctx.obj.get("ACCOUNT")
    
    if not attendees:
        click.echo("❌ Error: At least one attendee email is required.", err=True)
        sys.exit(1)
    
    try:
        api = CalendarAPI(account)
        
        # Use attendees as provided (must be email addresses)
        # Note: can't use list() here as the 'list' command shadows the built-in
        resolved_attendees = [*attendees]
        
        # Calculate time range
        if start or end:
            # Use --start/--end if provided
            if not start:
                click.echo("❌ Error: --start is required when --end is provided.", err=True)
                sys.exit(1)
            if not end:
                click.echo("❌ Error: --end is required when --start is provided.", err=True)
                sys.exit(1)
            
            time_min_dt = parse_datetime(start)
            time_max_dt = parse_datetime(end)
            
            if not time_min_dt:
                click.echo(f"❌ Error: Could not parse start time: {start}", err=True)
                sys.exit(1)
            if not time_max_dt:
                click.echo(f"❌ Error: Could not parse end time: {end}", err=True)
                sys.exit(1)
            
            # Ensure timezone-aware
            if time_min_dt.tzinfo is None:
                time_min_dt = time_min_dt.replace(tzinfo=tz_module.utc)
            else:
                time_min_dt = time_min_dt.astimezone(tz_module.utc)
            
            if time_max_dt.tzinfo is None:
                time_max_dt = time_max_dt.replace(tzinfo=tz_module.utc)
            else:
                time_max_dt = time_max_dt.astimezone(tz_module.utc)
            
            time_min = time_min_dt
            time_max = time_max_dt
        else:
            # Fall back to --days
            time_min = datetime.now(tz_module.utc)
            time_max = time_min + timedelta(days=days)
        
        click.echo(f"Finding available times for {len(resolved_attendees)} attendee(s) ({duration} min meeting)...")
        click.echo(f"Searching from {format_datetime(time_min)} to {format_datetime(time_max)}")
        click.echo()
        
        # Find available slots
        available_slots = api.find_available_slots(
            attendee_emails=resolved_attendees,
            duration_minutes=duration,
            time_min=time_min,
            time_max=time_max,
            working_hours_start=start_hour,
            working_hours_end=end_hour,
            exclude_weekends=exclude_weekends,
            timezone=tz_str
        )
        
        if not available_slots:
            click.echo("❌ No available time slots found in the specified range.")
            click.echo("   Try:")
            click.echo("   - Increasing --days")
            click.echo("   - Adjusting --start-hour and --end-hour")
            click.echo("   - Using --include-weekends")
            sys.exit(1)
        
        # Limit results
        available_slots = available_slots[:max_results]
        
        if start and end:
            click.echo(f"Available slots from {format_datetime(time_min)} to {format_datetime(time_max)}:\n")
        else:
            click.echo(f"Available slots in the next {days} days:\n")
        
        for i, (slot_start, slot_end) in enumerate(available_slots, 1):
            start_str = format_datetime(slot_start)
            end_str = format_datetime(slot_end)
            click.echo(f"  {i}. {start_str} - {end_str}")
        
        click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
@click.pass_context
def get(ctx, event_id, calendar, account):
    """Get event details."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        event = api.get_event(event_id, calendar_id=calendar)
        
        click.echo(f"📅 {event.get('summary', 'No Title')}")
        click.echo(f"   ID: {event.get('id')}")
        
        start = event.get("start", {})
        start_time = start.get("dateTime") or start.get("date")
        if start_time:
            start_dt = parse_datetime(start_time)
            click.echo(f"   Start: {format_datetime(start_dt) if start_dt else start_time}")
        
        end = event.get("end", {})
        end_time = end.get("dateTime") or end.get("date")
        if end_time:
            end_dt = parse_datetime(end_time)
            click.echo(f"   End: {format_datetime(end_dt) if end_dt else end_time}")
        
        if event.get("location"):
            click.echo(f"   Location: {event.get('location')}")
        
        if event.get("description"):
            click.echo(f"   Description: {event.get('description')}")
        
        if event.get("attendees"):
            click.echo(f"   Attendees: {len(event.get('attendees', []))}")
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("title", required=False)
@click.option("--start", "-s", help="Start time (ISO format or natural language)")
@click.option("--end", "-e", help="End time (ISO format or natural language)")
@click.option("--description", "-d", help="Event description")
@click.option("--location", "-l", help="Event location")
@click.option("--attendee", multiple=True, help="Attendee email address (can specify multiple)")
@click.option("--recurrence", "-r", help="Recurrence rule (RRULE format, e.g., 'FREQ=WEEKLY;COUNT=5')")
@click.option("--reminder-email", help="Email reminder minutes before (e.g., '1440' for 24 hours)")
@click.option("--reminder-popup", help="Popup reminder minutes before (e.g., '10')")
@click.option("--timezone", "-t", default=None, help="Timezone (default: from your calendar settings)")
@click.option("--color", help="Event color ID (use 'colors' command to see available colors)")
@click.option("--meet", is_flag=True, help="Add Google Meet video conference link")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--template", help="Use event template (name)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode - prompts for missing fields")
@click.option("--dry-run", is_flag=True, help="Show what would be created without actually creating")
@click.pass_context
@_account_option
def create(ctx, title, start, end, description, location, attendee, recurrence, reminder_email, reminder_popup, timezone, color, meet, calendar, template, interactive, dry_run, account):
    """Create a new event."""
    account = account or ctx.obj.get('ACCOUNT')
    
    # Use cached timezone if not provided
    if timezone is None:
        timezone = get_preference('timezone', 'UTC')
    
    # Interactive mode - prompt for missing fields
    if interactive or not title:
        if not title:
            title = click.prompt("Title", type=str)
        if not start:
            start = click.prompt("Start time (ISO format or natural language)", type=str)
        if not end:
            end = click.prompt("End time (ISO format or natural language)", type=str)
        if not description:
            description_input = click.prompt("Description (optional, press Enter to skip)", default="", show_default=False)
            description = description_input if description_input else None
        if not location:
            location_input = click.prompt("Location (optional, press Enter to skip)", default="", show_default=False)
            location = location_input if location_input else None
    
    # Load template if specified
    if template:
        try:
            template_data = render_template(template, title=title, start=start, end=end)
            title = template_data.get("title") or title
            description = template_data.get("description") or description
            location = template_data.get("location") or location
            if template_data.get("attendees"):
                attendee = [*attendee] + template_data.get("attendees", [])
        except Exception as e:
            click.echo(f"❌ Error loading template: {e}", err=True)
            sys.exit(1)
    
    if dry_run:
        click.echo("🔍 DRY RUN - Would create event:")
        click.echo(f"   Title: {title}")
        click.echo(f"   Calendar: {calendar}")
        if start:
            click.echo(f"   Start: {start}")
        if end:
            click.echo(f"   End: {end}")
        if location:
            click.echo(f"   Location: {location}")
        if description:
            click.echo(f"   Description: {description[:100]}..." if len(description) > 100 else f"   Description: {description}")
        if attendee:
            click.echo(f"   Attendees: {', '.join(attendee)}")
        if recurrence:
            click.echo(f"   Recurrence: {recurrence}")
        if meet:
            click.echo("   Google Meet: Yes")
        return
    
    try:
        api = CalendarAPI(account)
        
        # Build reminders dict if specified
        reminders = None
        if reminder_email or reminder_popup:
            overrides = []
            if reminder_email:
                overrides.append({"method": "email", "minutes": int(reminder_email)})
            if reminder_popup:
                overrides.append({"method": "popup", "minutes": int(reminder_popup)})
            reminders = {"useDefault": False, "overrides": overrides}
        
        # Parse recurrence
        recurrence_list = None
        if recurrence:
            recurrence_list = [f"RRULE:{recurrence}"] if not recurrence.startswith("RRULE:") else [recurrence]
        
        result = api.create_event(
            summary=title,
            start_time=start,
            end_time=end,
            description=description,
            location=location,
            calendar_id=calendar,
            attendees=[*attendee] if attendee else None,
            recurrence=recurrence_list,
            reminders=reminders,
            timezone=timezone,
            color_id=color,
            add_meet=meet,
        )
        
        # Record in history (create is undoable - can delete)
        add_operation("create", {
            "event_id": result.get("id"),
            "title": title,
            "calendar": calendar
        }, undoable=True, undo_func="delete")
        
        click.echo(f"✅ Event created successfully!")
        click.echo(f"   ID: {result.get('id')}")
        click.echo(f"   Title: {result.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--title", help="New event title")
@click.option("--start", "-s", help="New start time")
@click.option("--end", "-e", help="New end time")
@click.option("--description", "-d", help="New description")
@click.option("--location", "-l", help="New location")
@click.option("--attendee", "-a", multiple=True, help="Attendee email address (can specify multiple, use empty to clear)")
@click.option("--recurrence", "-r", help="Recurrence rule (RRULE format, empty string to remove)")
@click.option("--reminder-email", help="Email reminder minutes before")
@click.option("--reminder-popup", help="Popup reminder minutes before")
@click.option("--timezone", "-t", help="Timezone (e.g., 'America/Los_Angeles')")
@click.option("--color", help="Event color ID (use 'colors' command to see available colors, empty string to remove)")
@click.option("--meet", is_flag=True, help="Add Google Meet video conference link")
@click.option("--no-meet", is_flag=True, help="Remove Google Meet video conference link")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--dry-run", is_flag=True, help="Show what would be updated without actually updating")
@click.pass_context
@_account_option
def update(ctx, event_id, title, start, end, description, location, attendee, recurrence, reminder_email, reminder_popup, timezone, color, meet, no_meet, calendar, dry_run, account):
    """Update an event."""
    account = account or ctx.obj.get('ACCOUNT')
    
    if dry_run:
        click.echo(f"🔍 DRY RUN - Would update event {event_id}:")
        if title:
            click.echo(f"   Title: {title}")
        if start:
            click.echo(f"   Start: {start}")
        if end:
            click.echo(f"   End: {end}")
        if location:
            click.echo(f"   Location: {location}")
        if description:
            click.echo(f"   Description: {description[:100]}..." if len(description) > 100 else f"   Description: {description}")
        if attendee:
            click.echo(f"   Attendees: {', '.join(attendee)}")
        return
    try:
        api = CalendarAPI(account)
        
        # Build reminders dict if specified
        reminders = None
        if reminder_email or reminder_popup:
            overrides = []
            if reminder_email:
                overrides.append({"method": "email", "minutes": int(reminder_email)})
            if reminder_popup:
                overrides.append({"method": "popup", "minutes": int(reminder_popup)})
            reminders = {"useDefault": False, "overrides": overrides}
        
        # Parse recurrence
        recurrence_list = None
        if recurrence is not None:
            if recurrence == "":
                recurrence_list = []
            else:
                recurrence_list = [f"RRULE:{recurrence}"] if not recurrence.startswith("RRULE:") else [recurrence]
        
        # Get original event for undo
        original_event = api.get_event(event_id, calendar_id=calendar)
        
        result = api.update_event(
            event_id=event_id,
            summary=title,
            start_time=start,
            end_time=end,
            description=description,
            location=location,
            calendar_id=calendar,
            attendees=[*attendee] if attendee else None,
            recurrence=recurrence_list,
            reminders=reminders,
            timezone=timezone,
            color_id=color,
            add_meet=meet,
            remove_meet=no_meet,
        )
        
        # Record in history (update is undoable - can restore original)
        add_operation("update", {
            "event_id": event_id,
            "calendar": calendar,
            "original": original_event
        }, undoable=True, undo_func="restore")
        
        click.echo(f"✅ Event updated successfully!")
        click.echo(f"   ID: {result.get('id')}")
        click.echo(f"   Title: {result.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without actually deleting")
@click.confirmation_option(prompt="Are you sure you want to delete this event?")
@click.pass_context
@_account_option
def delete(ctx, event_id, calendar, dry_run, account):
    """Delete an event."""
    account = account or ctx.obj.get('ACCOUNT')
    
    if dry_run:
        click.echo(f"🔍 DRY RUN - Would delete event {event_id} from calendar {calendar}")
        return
    try:
        # Get event details before deletion for history
        api = CalendarAPI(account)
        event_details = api.get_event(event_id, calendar_id=calendar)
        
        api.delete_event(event_id, calendar_id=calendar)
        
        # Record in history (delete is not undoable)
        add_operation("delete", {
            "event_id": event_id,
            "calendar": calendar,
            "title": event_details.get("summary", "Unknown")
        }, undoable=False)
        
        click.echo(f"✅ Event {event_id} deleted successfully")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
@_account_option
def calendars(ctx, account):
    """List all calendars."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        calendars = api.list_calendars()
        
        if not calendars:
            click.echo("No calendars found.")
            return
        
        click.echo(f"Found {len(calendars)} calendars:\n")
        for cal in calendars:
            name = cal.get("summary", "Unnamed")
            cal_id = cal.get("id")
            primary = " (Primary)" if cal.get("primary") else ""
            click.echo(f"📅 {name}{primary}")
            click.echo(f"   ID: {cal_id}")
            if cal.get("timeZone"):
                click.echo(f"   Timezone: {cal.get('timeZone')}")
            click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.pass_context
@_account_option
def today(ctx, calendar, account):
    """Show today's events."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        today_start = get_today_start()
        today_end = today_start + timedelta(days=1)
        
        events = api.list_events(
            calendar_id=calendar,
            max_results=50,
            time_min=today_start.isoformat() + "Z",
            time_max=today_end.isoformat() + "Z",
        )
        
        if not events:
            click.echo("No events today.")
            return
        
        click.echo(f"📅 Today's events ({len(events)}):\n")
        
        for event in events:
            summary = event.get("summary", "No Title")
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date")
            if start_time:
                start_dt = parse_datetime(start_time)
                start_str = format_datetime(start_dt) if start_dt else start_time
            else:
                start_str = "Unknown"
            
            click.echo(f"  • {start_str} - {summary}")
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.pass_context
@_account_option
def week(ctx, calendar, account):
    """Show this week's events."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        week_start = get_week_start()
        week_end = get_week_end()
        
        events = api.list_events(
            calendar_id=calendar,
            max_results=100,
            time_min=week_start.isoformat() + "Z",
            time_max=week_end.isoformat() + "Z",
        )
        
        if not events:
            click.echo("No events this week.")
            return
        
        click.echo(f"📅 This week's events ({len(events)}):\n")
        
        current_date = None
        for event in events:
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date")
            if start_time:
                start_dt = parse_datetime(start_time)
                if start_dt:
                    event_date = start_dt.date()
                    if event_date != current_date:
                        click.echo(f"\n{event_date.strftime('%A, %B %d, %Y')}:")
                        current_date = event_date
                    
                    summary = event.get("summary", "No Title")
                    time_str = start_dt.strftime("%H:%M")
                    click.echo(f"  • {time_str} - {summary}")
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("text")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.pass_context
@_account_option
def quick_add(ctx, text, calendar, account):
    """Create an event using quick add (natural language)."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        event = api.quick_add_event(text, calendar_id=calendar)
        click.echo(f"✅ Event created successfully!")
        click.echo(f"   ID: {event.get('id')}")
        click.echo(f"   Title: {event.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.argument("destination_calendar")
@click.option("--calendar", "-c", default="primary", help="Source calendar ID")
@click.pass_context
@_account_option
def move(ctx, event_id, destination_calendar, calendar, account):
    """Move an event to another calendar."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        event = api.move_event(event_id, destination_calendar, calendar_id=calendar)
        click.echo(f"✅ Event moved successfully!")
        click.echo(f"   Event ID: {event.get('id')}")
        click.echo(f"   Title: {event.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--max", "-m", default=250, help="Maximum number of instances")
@click.pass_context
@_account_option
def instances(ctx, event_id, calendar, max, account):
    """Get instances of a recurring event."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        instances_list = api.get_recurring_event_instances(event_id, calendar_id=calendar, max_results=max)
        
        if not instances_list:
            click.echo("No instances found.")
            return
        
        click.echo(f"Found {len(instances_list)} instances:\n")
        for instance in instances_list:
            summary = instance.get("summary", "No Title")
            start = instance.get("start", {})
            start_time = start.get("dateTime") or start.get("date")
            if start_time:
                start_dt = parse_datetime(start_time)
                start_str = format_datetime(start_dt) if start_dt else start_time
            else:
                start_str = "Unknown"
            
            click.echo(f"📅 {summary}")
            click.echo(f"   ID: {instance.get('id')}")
            click.echo(f"   Start: {start_str}")
            click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--max", "-m", default=10, help="Maximum number of results")
@click.pass_context
@_account_option
def search(ctx, query, calendar, max, account):
    """Search events using a query string."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        events = api.search_events(query, calendar_id=calendar, max_results=max)
        
        if not events:
            click.echo(f"No events found for query: {query}")
            return
        
        click.echo(f"Found {len(events)} events for '{query}':\n")
        for event in events:
            summary = event.get("summary", "No Title")
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date")
            if start_time:
                start_dt = parse_datetime(start_time)
                start_str = format_datetime(start_dt) if start_dt else start_time
            else:
                start_str = "Unknown"
            
            click.echo(f"📅 {summary}")
            click.echo(f"   ID: {event.get('id')}")
            click.echo(f"   Start: {start_str}")
            click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("time_min")
@click.argument("time_max")
@click.option("--calendar", "-c", multiple=True, help="Calendar IDs to check (can specify multiple)")
@click.pass_context
@_account_option
def freebusy(ctx, time_min, time_max, calendar, account):
    """Query free/busy information for calendars.
    
    Time arguments support flexible formats:
    - ISO format: '2026-01-15T09:00:00Z'
    - Date only: '2026-01-15'
    - Natural language: 'next Monday', 'Monday 9am', 'tomorrow'
    """
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        
        # Parse time arguments with flexible format support
        time_min_dt = parse_datetime(time_min)
        time_max_dt = parse_datetime(time_max)
        
        if not time_min_dt:
            click.echo(f"❌ Error: Could not parse start time: {time_min}", err=True)
            sys.exit(1)
        if not time_max_dt:
            click.echo(f"❌ Error: Could not parse end time: {time_max}", err=True)
            sys.exit(1)
        
        # Ensure timezone-aware (convert to UTC)
        if time_min_dt.tzinfo is None:
            time_min_dt = time_min_dt.replace(tzinfo=timezone.utc)
        else:
            time_min_dt = time_min_dt.astimezone(timezone.utc)
        
        if time_max_dt.tzinfo is None:
            time_max_dt = time_max_dt.replace(tzinfo=timezone.utc)
        else:
            time_max_dt = time_max_dt.astimezone(timezone.utc)
        
        calendar_ids = [*calendar] if calendar else None
        result = api.freebusy_query(time_min_dt, time_max_dt, calendar_ids=calendar_ids)
        
        calendars = result.get("calendars", {})
        click.echo("Free/Busy Information:\n")
        for cal_id, cal_data in calendars.items():
            click.echo(f"📅 Calendar: {cal_id}")
            busy = cal_data.get("busy", [])
            if busy:
                click.echo("   Busy periods:")
                for period in busy:
                    click.echo(f"     {period.get('start')} - {period.get('end')}")
            else:
                click.echo("   ✅ Free")
            click.echo()
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("calendar_id")
@click.pass_context
@_account_option
def get_calendar(ctx, calendar_id, account):
    """Get calendar metadata."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        calendar = api.get_calendar(calendar_id)
        
        click.echo(f"📅 {calendar.get('summary', 'Unnamed')}")
        click.echo(f"   ID: {calendar.get('id')}")
        if calendar.get("description"):
            click.echo(f"   Description: {calendar.get('description')}")
        if calendar.get("timeZone"):
            click.echo(f"   Timezone: {calendar.get('timeZone')}")
        if calendar.get("location"):
            click.echo(f"   Location: {calendar.get('location')}")
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("summary")
@click.option("--description", "-d", help="Calendar description")
@click.option("--timezone", "-t", help="Timezone (default: from your calendar settings)")
@click.option("--color", help="Calendar color ID (use 'colors' command to see available colors)")
@click.pass_context
@_account_option
def create_calendar(ctx, summary, description, timezone, color, account):
    """Create a new calendar."""
    account = account or ctx.obj.get('ACCOUNT')
    
    # Use cached timezone if not provided
    if timezone is None:
        timezone = get_preference('timezone', 'UTC')
    
    try:
        api = CalendarAPI(account)
        calendar = api.create_calendar(summary, description=description, timezone=timezone, color_id=color)
        click.echo(f"✅ Calendar created successfully!")
        click.echo(f"   ID: {calendar.get('id')}")
        click.echo(f"   Name: {calendar.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("calendar_id")
@click.option("--summary", "-s", help="New calendar name")
@click.option("--description", "-d", help="New description")
@click.option("--timezone", "-t", help="New timezone")
@click.option("--color", help="Calendar color ID (use 'colors' command, empty string to remove)")
@click.pass_context
@_account_option
def update_calendar(ctx, calendar_id, summary, description, timezone, color, account):
    """Update calendar metadata."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        calendar = api.update_calendar(calendar_id, summary=summary, description=description, timezone=timezone, color_id=color)
        click.echo(f"✅ Calendar updated successfully!")
        click.echo(f"   ID: {calendar.get('id')}")
        click.echo(f"   Name: {calendar.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("calendar_id")
@click.confirmation_option(prompt="Are you sure you want to delete this calendar?")
@click.pass_context
@_account_option
def delete_calendar(ctx, calendar_id, account):
    """Delete a calendar (secondary calendars only)."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        api.delete_calendar(calendar_id)
        click.echo(f"✅ Calendar {calendar_id} deleted successfully")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("calendar_id")
@click.confirmation_option(prompt="Are you sure you want to clear all events from this calendar?")
@click.pass_context
@_account_option
def clear_calendar(ctx, calendar_id, account):
    """Clear all events from a calendar (primary calendar only)."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        api.clear_calendar(calendar_id)
        click.echo(f"✅ Calendar {calendar_id} cleared successfully")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
@_account_option
def colors(ctx, account):
    """Get available colors for calendars and events."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        colors_data = api.get_colors()
        
        calendar_colors = colors_data.get("calendar", {})
        event_colors = colors_data.get("event", {})
        
        if calendar_colors:
            click.echo("Calendar Colors:\n")
            for color_id, color_info in calendar_colors.items():
                background = color_info.get("background", "N/A")
                foreground = color_info.get("foreground", "N/A")
                click.echo(f"   {color_id}: bg={background}, fg={foreground}")
        
        if event_colors:
            click.echo("\nEvent Colors:\n")
            for color_id, color_info in event_colors.items():
                background = color_info.get("background", "N/A")
                foreground = color_info.get("foreground", "N/A")
                click.echo(f"   {color_id}: bg={background}, fg={foreground}")
    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.argument("emails", nargs=-1, required=False)
@click.option("--emails", "emails_opt", help="Comma-separated list of email addresses (e.g., 'email1@example.com,email2@example.com')")
@click.option("--email", "email_list", multiple=True, help="Attendee email address (can specify multiple times)")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--send-updates", default="all", type=click.Choice(["all", "externalOnly", "none"]), help="Send updates to attendees")
@click.pass_context
@_account_option
def add_attendees(ctx, event_id, emails, emails_opt, email_list, calendar, send_updates, account):
    """Add attendees to an event.
    
    You can provide emails as positional arguments, --emails flag, or --email flags:
    
    \b
    Examples:
        google-calendar add-attendees EVENT_ID email1@x.com email2@x.com
        google-calendar add-attendees EVENT_ID --emails "email1@x.com,email2@x.com"
        google-calendar add-attendees EVENT_ID --email email1@x.com --email email2@x.com
    """
    account = account or ctx.obj.get('ACCOUNT')
    
    # Combine emails from all sources: positional args, --emails flag, and --email flags
    all_emails = []
    if emails:
        all_emails.extend([e.strip() for e in emails])
    if emails_opt:
        all_emails.extend([e.strip() for e in emails_opt.split(',')])
    if email_list:
        all_emails.extend(email_list)
    
    if not all_emails:
        click.echo("❌ Error: At least one email address is required.", err=True)
        click.echo("\nUsage examples:", err=True)
        click.echo("  google-calendar add-attendees EVENT_ID email1@x.com email2@x.com", err=True)
        click.echo("  google-calendar add-attendees EVENT_ID --emails 'email1@x.com,email2@x.com'", err=True)
        click.echo("  google-calendar add-attendees EVENT_ID --email email1@x.com --email email2@x.com", err=True)
        sys.exit(1)
    
    try:
        api = CalendarAPI(account)
        event = api.add_attendees(event_id, all_emails, calendar_id=calendar, send_updates=send_updates)
        click.echo(f"✅ Attendees added successfully!")
        click.echo(f"   Event ID: {event.get('id')}")
        click.echo(f"   Total attendees: {len(event.get('attendees', []))}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.argument("emails", nargs=-1, required=False)
@click.option("--emails", "emails_opt", help="Comma-separated list of email addresses to remove")
@click.option("--email", "email_list", multiple=True, help="Attendee email address to remove (can specify multiple times)")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.option("--send-updates", default="all", type=click.Choice(["all", "externalOnly", "none"]), help="Send updates to attendees")
@click.pass_context
@_account_option
def remove_attendees(ctx, event_id, emails, emails_opt, email_list, calendar, send_updates, account):
    """Remove attendees from an event.
    
    You can provide emails as positional arguments, --emails flag, or --email flags:
    
    \b
    Examples:
        google-calendar remove-attendees EVENT_ID email1@x.com email2@x.com
        google-calendar remove-attendees EVENT_ID --emails "email1@x.com,email2@x.com"
        google-calendar remove-attendees EVENT_ID --email email1@x.com --email email2@x.com
    """
    account = account or ctx.obj.get('ACCOUNT')
    
    # Combine emails from all sources: positional args, --emails flag, and --email flags
    all_emails = []
    if emails:
        all_emails.extend([e.strip() for e in emails])
    if emails_opt:
        all_emails.extend([e.strip() for e in emails_opt.split(',')])
    if email_list:
        all_emails.extend(email_list)
    
    if not all_emails:
        click.echo("❌ Error: At least one email address is required.", err=True)
        click.echo("\nUsage examples:", err=True)
        click.echo("  google-calendar remove-attendees EVENT_ID email1@x.com email2@x.com", err=True)
        click.echo("  google-calendar remove-attendees EVENT_ID --emails 'email1@x.com,email2@x.com'", err=True)
        click.echo("  google-calendar remove-attendees EVENT_ID --email email1@x.com --email email2@x.com", err=True)
        sys.exit(1)
    
    try:
        api = CalendarAPI(account)
        event = api.remove_attendees(event_id, all_emails, calendar_id=calendar, send_updates=send_updates)
        click.echo(f"✅ Attendees removed successfully!")
        click.echo(f"   Event ID: {event.get('id')}")
        click.echo(f"   Remaining attendees: {len(event.get('attendees', []))}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.argument("location")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
@click.pass_context
def set_location(ctx, event_id, location, calendar, account):
    """Set location for an event."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        event = api.update_event(event_id, location=location, calendar_id=calendar)
        click.echo(f"✅ Location updated successfully!")
        click.echo(f"   Event ID: {event.get('id')}")
        click.echo(f"   Location: {event.get('location')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.argument("new_start")
@click.argument("new_end")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
@click.pass_context
def propose_new_time(ctx, event_id, new_start, new_end, calendar, account):
    """Propose a new time for an event (as an attendee)."""
    account = account or ctx.obj.get('ACCOUNT')
    try:
        api = CalendarAPI(account)
        event = api.propose_new_time(event_id, new_start, new_end, calendar_id=calendar)
        click.echo(f"✅ New time proposed successfully!")
        click.echo(f"   Event ID: {event.get('id')}")
        click.echo(f"   Proposed start: {event.get('start', {}).get('dateTime', 'N/A')}")
        click.echo(f"   Proposed end: {event.get('end', {}).get('dateTime', 'N/A')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def template():
    """Event template management commands."""
    pass


@template.command("list")
def template_list():
    """List all event templates."""
    templates = list_templates()
    if not templates:
        click.echo("No templates found.")
        click.echo("\nCreate a template with: google-calendar template create <name>")
        return
    
    click.echo(f"Found {len(templates)} template(s):\n")
    for tmpl in templates:
        click.echo(f"📅 {tmpl['name']}")
        if tmpl.get("title"):
            click.echo(f"   Title: {tmpl['title']}")
        if tmpl.get("location"):
            click.echo(f"   Location: {tmpl['location']}")
        if tmpl.get("duration_minutes"):
            click.echo(f"   Duration: {tmpl['duration_minutes']} minutes")
        click.echo()


@template.command("create")
@click.argument("name")
@click.option("--title", help="Event title")
@click.option("--description", help="Event description")
@click.option("--location", help="Event location")
@click.option("--duration", type=int, default=60, help="Duration in minutes")
@click.option("--attendee", multiple=True, help="Attendee email address")
def template_create(name, title, description, location, duration, attendee):
    """Create a new event template."""
    if not any([title, description, location]):
        click.echo("Creating template interactively...")
        title = title or click.prompt("Title (optional)", default="", show_default=False)
        description = description or click.prompt("Description (optional)", default="", show_default=False)
        location = location or click.prompt("Location (optional)", default="", show_default=False)
    
    template = create_template(
        name,
        title=title,
        description=description,
        location=location,
        duration_minutes=duration,
        attendees=[*attendee] if attendee else None
    )
    click.echo(f"✅ Template '{name}' created successfully!")


@template.command("delete")
@click.argument("name")
def template_delete(name):
    """Delete an event template."""
    if delete_template(name):
        click.echo(f"✅ Template '{name}' deleted successfully!")
    else:
        click.echo(f"❌ Template '{name}' not found.", err=True)
        sys.exit(1)


@template.command("show")
@click.argument("name")
def template_show(name):
    """Show template details."""
    template = get_template(name)
    if not template:
        click.echo(f"❌ Template '{name}' not found.", err=True)
        sys.exit(1)
    
    click.echo(f"📅 Template: {name}")
    if template.get("title"):
        click.echo(f"   Title: {template['title']}")
    if template.get("description"):
        click.echo(f"   Description: {template['description']}")
    if template.get("location"):
        click.echo(f"   Location: {template['location']}")
    if template.get("duration_minutes"):
        click.echo(f"   Duration: {template['duration_minutes']} minutes")
    if template.get("attendees"):
        click.echo(f"   Attendees: {', '.join(template['attendees'])}")


@cli.command()
@click.option("--limit", "-l", default=10, type=int, help="Number of operations to show")
def history(limit):
    """Show recent operation history."""
    operations = get_recent_operations(limit)
    
    if not operations:
        click.echo("No operations in history.")
        return
    
    click.echo(f"Recent operations (last {len(operations)}):\n")
    for op in reversed(operations):
        timestamp = op.get("timestamp", "")
        op_type = op.get("type", "unknown")
        details = op.get("details", {})
        undoable = "✓" if op.get("undoable") else "✗"
        
        click.echo(f"{undoable} [{timestamp[:19]}] {op_type}")
        if details:
            for key, value in details.items():
                if key not in ["event_id", "original"]:  # Skip internal IDs for cleaner display
                    click.echo(f"   {key}: {value}")
        click.echo()


@cli.command()
@_account_option
@click.pass_context
def undo(ctx, account):
    """Undo the last undoable operation."""
    account = account or ctx.obj.get("ACCOUNT")
    
    last_op = get_last_undoable_operation()
    
    if not last_op:
        click.echo("❌ No undoable operation found.")
        return
    
    op_type = last_op.get("type")
    details = last_op.get("details", {})
    undo_func = last_op.get("undo_func")
    
    click.echo(f"Undoing: {op_type} at {last_op.get('timestamp', '')[:19]}")
    
    try:
        api = CalendarAPI(account)
        
        if op_type == "create" and undo_func == "delete":
            event_id = details.get("event_id")
            calendar = details.get("calendar", "primary")
            if event_id:
                api.delete_event(event_id, calendar_id=calendar)
                click.echo(f"✅ Event {event_id} deleted (undone)")
            else:
                click.echo("❌ Cannot undo: missing event ID")
        elif op_type == "update" and undo_func == "restore":
            event_id = details.get("event_id")
            calendar = details.get("calendar", "primary")
            original = details.get("original")
            if event_id and original:
                api.update_event(event_id, calendar_id=calendar, **original)
                click.echo(f"✅ Event {event_id} restored to previous state")
            else:
                click.echo("❌ Cannot undo: missing event data")
        else:
            click.echo(f"❌ Cannot undo operation type: {op_type}")
    
    except Exception as e:
        click.echo(f"❌ Error undoing operation: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish"]), required=True, help="Shell type for completion script")
def completion(shell):
    """Generate shell completion script. Add to your shell config file."""
    try:
        from click.shell_completion import get_completion_script
        
        # Get the completion script
        script = get_completion_script("google-calendar", "_GOOGLE_CALENDAR_COMPLETE", shell)
        click.echo(script)
        click.echo(f"\n# To install, run:", err=True)
        if shell == "fish":
            click.echo(f"# google-calendar completion --shell {shell} > ~/.config/fish/completions/google-calendar.fish", err=True)
        else:
            click.echo(f"# google-calendar completion --shell {shell} >> ~/.{shell}rc", err=True)
    except ImportError:
        click.echo("❌ Shell completion not available. Install click>=8.0", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error generating completion script: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

