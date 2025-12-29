"""Google Calendar CLI - Main command-line interface."""

import click
import sys
from datetime import datetime, timedelta
from .auth import authenticate, get_credentials, check_auth
from .api import CalendarAPI
from .utils import format_datetime, get_today_start, get_week_start, get_week_end, parse_datetime, list_accounts, get_default_account, set_default_account


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Google Calendar CLI - Command-line interface for Google Calendar."""
    pass


# Account option decorator
_account_option = click.option("--account", "-a", help="Account name to use (default: current default account)")


@cli.command()
@click.option("--account", "-a", help="Account name (optional, will use email if not provided)")
def init(account):
    """Initialize and authenticate with Google Calendar API."""
    click.echo("🔐 Setting up Google Calendar authentication...")
    creds = authenticate(account)
    
    if creds:
        try:
            api = CalendarAPI(account)
            profile = api.get_profile()
            click.echo(f"✅ Authenticated successfully!")
            if profile.get("summary"):
                click.echo(f"   Primary calendar: {profile.get('summary')}")
            
            # Show account name if different from calendar ID
            default_account = get_default_account()
            if default_account and default_account != profile.get("id"):
                click.echo(f"   Account name: {default_account}")
        except Exception as e:
            click.echo(f"⚠️  Authentication saved but verification failed: {e}")
    else:
        sys.exit(1)


@cli.command()
def accounts():
    """List all configured accounts."""
    accounts_list = list_accounts()
    default = get_default_account()
    
    if not accounts_list:
        click.echo("No accounts configured. Run 'google-calendar init' to add an account.")
        return
    
    click.echo(f"Configured accounts ({len(accounts_list)}):\n")
    for acc in accounts_list:
        marker = " (default)" if acc == default else ""
        click.echo(f"  • {acc}{marker}")
    
    if default:
        click.echo(f"\nDefault account: {default}")


@cli.command()
@click.argument("account_name")
def use(account_name):
    """Set default account to use."""
    accounts_list = list_accounts()
    
    if account_name not in accounts_list:
        click.echo(f"❌ Error: Account '{account_name}' not found.")
        click.echo(f"Available accounts: {', '.join(accounts_list)}")
        click.echo("\nRun 'google-calendar init --account <name>' to add a new account.")
        sys.exit(1)
    
    set_default_account(account_name)
    click.echo(f"✅ Default account set to: {account_name}")


@cli.command()
@_account_option
def me(account):
    """Show authenticated user information."""
    try:
        api = CalendarAPI(account)
        profile = api.get_profile()
        if profile:
            click.echo(f"📅 Primary Calendar: {profile.get('summary', 'Unknown')}")
            click.echo(f"   ID: {profile.get('id', 'N/A')}")
            click.echo(f"   Timezone: {profile.get('timeZone', 'N/A')}")
        else:
            click.echo("No primary calendar found.")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--max", "-m", default=10, help="Maximum number of events")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
def list(max, calendar, account):
    """List upcoming events."""
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


@cli.command()
@click.argument("event_id")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
def get(event_id, calendar, account):
    """Get event details."""
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
@click.argument("title")
@click.option("--start", "-s", help="Start time (ISO format or natural language)")
@click.option("--end", "-e", help="End time (ISO format or natural language)")
@click.option("--description", "-d", help="Event description")
@click.option("--location", "-l", help="Event location")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
def create(title, start, end, description, location, calendar, account):
    """Create a new event."""
    try:
        api = CalendarAPI(account)
        result = api.create_event(
            summary=title,
            start_time=start,
            end_time=end,
            description=description,
            location=location,
            calendar_id=calendar,
        )
        click.echo(f"✅ Event created successfully!")
        click.echo(f"   ID: {result.get('id')}")
        click.echo(f"   Title: {result.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--title", "-t", help="New event title")
@click.option("--start", "-s", help="New start time")
@click.option("--end", "-e", help="New end time")
@click.option("--description", "-d", help="New description")
@click.option("--location", "-l", help="New location")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@_account_option
def update(event_id, title, start, end, description, location, calendar, account):
    """Update an event."""
    try:
        api = CalendarAPI(account)
        result = api.update_event(
            event_id=event_id,
            summary=title,
            start_time=start,
            end_time=end,
            description=description,
            location=location,
            calendar_id=calendar,
        )
        click.echo(f"✅ Event updated successfully!")
        click.echo(f"   ID: {result.get('id')}")
        click.echo(f"   Title: {result.get('summary')}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("event_id")
@click.option("--calendar", "-c", default="primary", help="Calendar ID")
@click.confirmation_option(prompt="Are you sure you want to delete this event?")
@_account_option
def delete(event_id, calendar, account):
    """Delete an event."""
    try:
        api = CalendarAPI(account)
        api.delete_event(event_id, calendar_id=calendar)
        click.echo(f"✅ Event {event_id} deleted successfully")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@_account_option
def calendars(account):
    """List all calendars."""
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
@_account_option
def today(calendar, account):
    """Show today's events."""
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
@_account_option
def week(calendar, account):
    """Show this week's events."""
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


if __name__ == "__main__":
    cli()

