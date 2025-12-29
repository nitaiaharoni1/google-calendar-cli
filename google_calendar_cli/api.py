"""Google Calendar API wrapper."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .auth import get_credentials, check_auth
from .utils import parse_datetime, format_datetime
from datetime import datetime, timedelta


class CalendarAPI:
    """Wrapper for Google Calendar API operations."""
    
    def __init__(self, account=None):
        """
        Initialize Calendar API service.
        
        Args:
            account: Account name (optional). If None, uses default account.
        """
        creds = check_auth(account)
        if not creds:
            raise Exception("Not authenticated. Run 'google-calendar init' first.")
        
        self.service = build("calendar", "v3", credentials=creds)
        self.account = account
    
    def get_profile(self):
        """Get user profile information."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            # Get primary calendar info
            primary_calendar = next(
                (cal for cal in calendar_list.get("items", []) if cal.get("primary")),
                None
            )
            return primary_calendar or {}
        except HttpError as error:
            raise Exception(f"Failed to get profile: {error}")
    
    def list_calendars(self):
        """List all calendars."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get("items", [])
            return calendars
        except HttpError as error:
            raise Exception(f"Failed to list calendars: {error}")
    
    def list_events(
        self,
        calendar_id="primary",
        max_results=10,
        time_min=None,
        time_max=None,
        single_events=True,
        order_by="startTime",
    ):
        """
        List events from a calendar.
        
        Args:
            calendar_id: Calendar ID (default: 'primary')
            max_results: Maximum number of events to return
            time_min: Lower bound (exclusive) for an event's end time
            time_max: Upper bound (exclusive) for an event's start time
            single_events: Whether to expand recurring events
            order_by: Order of results (startTime or updated)
        """
        try:
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": single_events,
                "orderBy": order_by,
            }
            
            if time_min:
                if isinstance(time_min, datetime):
                    time_min = time_min.isoformat() + "Z"
                params["timeMin"] = time_min
            
            if time_max:
                if isinstance(time_max, datetime):
                    time_max = time_max.isoformat() + "Z"
                params["timeMax"] = time_max
            
            events_result = self.service.events().list(**params).execute()
            events = events_result.get("items", [])
            return events
        except HttpError as error:
            raise Exception(f"Failed to list events: {error}")
    
    def get_event(self, event_id, calendar_id="primary"):
        """
        Get a specific event by ID.
        
        Args:
            event_id: The event ID
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            event = (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            return event
        except HttpError as error:
            raise Exception(f"Failed to get event: {error}")
    
    def create_event(
        self,
        summary,
        start_time=None,
        end_time=None,
        description=None,
        location=None,
        calendar_id="primary",
    ):
        """
        Create a new event.
        
        Args:
            summary: Event title
            start_time: Start datetime (datetime object or ISO string)
            end_time: End datetime (datetime object or ISO string)
            description: Event description
            location: Event location
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            event = {"summary": summary}
            
            # Parse and format start time
            if start_time:
                if isinstance(start_time, datetime):
                    event["start"] = {
                        "dateTime": start_time.isoformat(),
                        "timeZone": "UTC",
                    }
                else:
                    start_dt = parse_datetime(start_time)
                    if start_dt:
                        event["start"] = {
                            "dateTime": start_dt.isoformat(),
                            "timeZone": "UTC",
                        }
            else:
                # Default to now
                now = datetime.utcnow()
                event["start"] = {
                    "dateTime": now.isoformat(),
                    "timeZone": "UTC",
                }
            
            # Parse and format end time
            if end_time:
                if isinstance(end_time, datetime):
                    event["end"] = {
                        "dateTime": end_time.isoformat(),
                        "timeZone": "UTC",
                    }
                else:
                    end_dt = parse_datetime(end_time)
                    if end_dt:
                        event["end"] = {
                            "dateTime": end_dt.isoformat(),
                            "timeZone": "UTC",
                        }
            else:
                # Default to 1 hour after start
                start_dt = parse_datetime(event["start"]["dateTime"])
                if start_dt:
                    end_dt = start_dt + timedelta(hours=1)
                    event["end"] = {
                        "dateTime": end_dt.isoformat(),
                        "timeZone": "UTC",
                    }
            
            if description:
                event["description"] = description
            
            if location:
                event["location"] = location
            
            created_event = (
                self.service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute()
            )
            return created_event
        except HttpError as error:
            raise Exception(f"Failed to create event: {error}")
    
    def update_event(
        self,
        event_id,
        summary=None,
        start_time=None,
        end_time=None,
        description=None,
        location=None,
        calendar_id="primary",
    ):
        """
        Update an existing event.
        
        Args:
            event_id: The event ID
            summary: New event title
            start_time: New start datetime
            end_time: New end datetime
            description: New description
            location: New location
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            # Get existing event
            event = self.get_event(event_id, calendar_id)
            
            # Update fields
            if summary:
                event["summary"] = summary
            
            if start_time:
                if isinstance(start_time, datetime):
                    event["start"] = {
                        "dateTime": start_time.isoformat(),
                        "timeZone": "UTC",
                    }
                else:
                    start_dt = parse_datetime(start_time)
                    if start_dt:
                        event["start"] = {
                            "dateTime": start_dt.isoformat(),
                            "timeZone": "UTC",
                        }
            
            if end_time:
                if isinstance(end_time, datetime):
                    event["end"] = {
                        "dateTime": end_time.isoformat(),
                        "timeZone": "UTC",
                    }
                else:
                    end_dt = parse_datetime(end_time)
                    if end_dt:
                        event["end"] = {
                            "dateTime": end_dt.isoformat(),
                            "timeZone": "UTC",
                        }
            
            if description is not None:
                event["description"] = description
            
            if location is not None:
                event["location"] = location
            
            updated_event = (
                self.service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )
            return updated_event
        except HttpError as error:
            raise Exception(f"Failed to update event: {error}")
    
    def delete_event(self, event_id, calendar_id="primary"):
        """
        Delete an event.
        
        Args:
            event_id: The event ID
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            return True
        except HttpError as error:
            raise Exception(f"Failed to delete event: {error}")

