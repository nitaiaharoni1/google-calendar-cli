"""Google Calendar API wrapper."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .auth import get_credentials, check_auth
from .utils import parse_datetime, format_datetime
from .retry import with_retry
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
    
    @with_retry()
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
    
    @with_retry()
    def list_calendars(self):
        """List all calendars."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get("items", [])
            return calendars
        except HttpError as error:
            raise Exception(f"Failed to list calendars: {error}")
    
    @with_retry()
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
    
    @with_retry()
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
    
    @with_retry()
    def create_event(
        self,
        summary,
        start_time=None,
        end_time=None,
        description=None,
        location=None,
        calendar_id="primary",
        attendees=None,
        recurrence=None,
        reminders=None,
        timezone="UTC",
        color_id=None,
        add_meet=False,
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
            attendees: List of attendee email addresses
            recurrence: List of recurrence rules (RRULE format strings)
            reminders: Dict with 'useDefault' (bool) and 'overrides' (list of dicts with 'method' and 'minutes')
            timezone: Timezone string (default: 'UTC')
            color_id: Event color ID (string)
            add_meet: Whether to add Google Meet conference link (bool)
        """
        try:
            import uuid
            event = {"summary": summary}
            
            # Parse and format start time
            if start_time:
                if isinstance(start_time, datetime):
                    event["start"] = {
                        "dateTime": start_time.isoformat(),
                        "timeZone": timezone,
                    }
                else:
                    start_dt = parse_datetime(start_time)
                    if start_dt:
                        event["start"] = {
                            "dateTime": start_dt.isoformat(),
                            "timeZone": timezone,
                        }
            else:
                # Default to now
                now = datetime.utcnow()
                event["start"] = {
                    "dateTime": now.isoformat(),
                    "timeZone": timezone,
                }
            
            # Parse and format end time
            if end_time:
                if isinstance(end_time, datetime):
                    event["end"] = {
                        "dateTime": end_time.isoformat(),
                        "timeZone": timezone,
                    }
                else:
                    end_dt = parse_datetime(end_time)
                    if end_dt:
                        event["end"] = {
                            "dateTime": end_dt.isoformat(),
                            "timeZone": timezone,
                        }
            else:
                # Default to 1 hour after start
                start_dt = parse_datetime(event["start"]["dateTime"])
                if start_dt:
                    end_dt = start_dt + timedelta(hours=1)
                    event["end"] = {
                        "dateTime": end_dt.isoformat(),
                        "timeZone": timezone,
                    }
            
            if description:
                event["description"] = description
            
            if location:
                event["location"] = location
            
            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]
            
            if recurrence:
                event["recurrence"] = recurrence if isinstance(recurrence, list) else [recurrence]
            
            if reminders:
                event["reminders"] = reminders
            
            if color_id:
                event["colorId"] = color_id
            
            # Add Google Meet conference
            if add_meet:
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": str(uuid.uuid4()),
                        "conferenceSolutionKey": {
                            "type": "hangoutsMeet"
                        }
                    }
                }
            
            params = {"calendarId": calendar_id, "body": event}
            if add_meet:
                params["conferenceDataVersion"] = 1
            
            created_event = (
                self.service.events()
                .insert(**params)
                .execute()
            )
            return created_event
        except HttpError as error:
            raise Exception(f"Failed to create event: {error}")
    
    @with_retry()
    def update_event(
        self,
        event_id,
        summary=None,
        start_time=None,
        end_time=None,
        description=None,
        location=None,
        calendar_id="primary",
        attendees=None,
        recurrence=None,
        reminders=None,
        timezone=None,
        color_id=None,
        add_meet=False,
        remove_meet=False,
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
            attendees: List of attendee email addresses (None = no change, [] = remove all)
            recurrence: List of recurrence rules (None = no change, [] = remove recurrence)
            reminders: Dict with 'useDefault' and 'overrides' (None = no change)
            timezone: Timezone string (uses existing if not provided)
            color_id: Event color ID (None = no change, "" = remove color)
            add_meet: Whether to add Google Meet conference link
            remove_meet: Whether to remove Google Meet conference link
        """
        try:
            import uuid
            # Get existing event
            event = self.get_event(event_id, calendar_id)
            
            # Get existing timezone if not provided
            if not timezone:
                timezone = event.get("start", {}).get("timeZone", "UTC")
            
            # Update fields
            if summary:
                event["summary"] = summary
            
            if start_time:
                if isinstance(start_time, datetime):
                    event["start"] = {
                        "dateTime": start_time.isoformat(),
                        "timeZone": timezone,
                    }
                else:
                    start_dt = parse_datetime(start_time)
                    if start_dt:
                        event["start"] = {
                            "dateTime": start_dt.isoformat(),
                            "timeZone": timezone,
                        }
            
            if end_time:
                if isinstance(end_time, datetime):
                    event["end"] = {
                        "dateTime": end_time.isoformat(),
                        "timeZone": timezone,
                    }
                else:
                    end_dt = parse_datetime(end_time)
                    if end_dt:
                        event["end"] = {
                            "dateTime": end_dt.isoformat(),
                            "timeZone": timezone,
                        }
            
            if description is not None:
                event["description"] = description
            
            if location is not None:
                event["location"] = location
            
            if attendees is not None:
                event["attendees"] = [{"email": email} for email in attendees] if attendees else []
            
            if recurrence is not None:
                event["recurrence"] = recurrence if isinstance(recurrence, list) else [recurrence] if recurrence else []
            
            if reminders is not None:
                event["reminders"] = reminders
            
            if color_id is not None:
                if color_id == "":
                    event.pop("colorId", None)
                else:
                    event["colorId"] = color_id
            
            # Handle Google Meet conference
            if remove_meet:
                event.pop("conferenceData", None)
            elif add_meet:
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": str(uuid.uuid4()),
                        "conferenceSolutionKey": {
                            "type": "hangoutsMeet"
                        }
                    }
                }
            
            params = {
                "calendarId": calendar_id,
                "eventId": event_id,
                "body": event
            }
            if add_meet or remove_meet:
                params["conferenceDataVersion"] = 1
            
            updated_event = (
                self.service.events()
                .update(**params)
                .execute()
            )
            return updated_event
        except HttpError as error:
            raise Exception(f"Failed to update event: {error}")
    
    @with_retry()
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
    
    def quick_add_event(self, text, calendar_id="primary"):
        """
        Create an event using quick add (natural language).
        
        Args:
            text: Natural language description (e.g., "Appointment on June 3rd 10am-10:25am")
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            event = self.service.events().quickAdd(
                calendarId=calendar_id, text=text
            ).execute()
            return event
        except HttpError as error:
            raise Exception(f"Failed to quick add event: {error}")
    
    def move_event(self, event_id, destination_calendar_id, calendar_id="primary"):
        """
        Move an event to another calendar.
        
        Args:
            event_id: The event ID
            destination_calendar_id: Calendar ID to move event to
            calendar_id: Source calendar ID (default: 'primary')
        """
        try:
            event = self.service.events().move(
                calendarId=calendar_id,
                eventId=event_id,
                destination=destination_calendar_id
            ).execute()
            return event
        except HttpError as error:
            raise Exception(f"Failed to move event: {error}")
    
    def get_recurring_event_instances(self, event_id, calendar_id="primary", max_results=250):
        """
        Get instances of a recurring event.
        
        Args:
            event_id: The recurring event ID
            calendar_id: Calendar ID (default: 'primary')
            max_results: Maximum number of instances to return
        """
        try:
            instances = self.service.events().instances(
                calendarId=calendar_id,
                eventId=event_id,
                maxResults=max_results
            ).execute()
            return instances.get("items", [])
        except HttpError as error:
            raise Exception(f"Failed to get recurring event instances: {error}")
    
    def search_events(self, query, calendar_id="primary", max_results=10):
        """
        Search events using a query string.
        
        Args:
            query: Search query string
            calendar_id: Calendar ID (default: 'primary')
            max_results: Maximum number of results
        """
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            return events_result.get("items", [])
        except HttpError as error:
            raise Exception(f"Failed to search events: {error}")
    
    def freebusy_query(self, time_min, time_max, calendar_ids=None):
        """
        Query free/busy information for calendars.
        
        Args:
            time_min: Start time (datetime or ISO string)
            time_max: End time (datetime or ISO string)
            calendar_ids: List of calendar IDs to check (default: primary)
        """
        try:
            if calendar_ids is None:
                calendar_ids = ["primary"]
            
            if isinstance(time_min, datetime):
                time_min = time_min.isoformat() + "Z"
            if isinstance(time_max, datetime):
                time_max = time_max.isoformat() + "Z"
            
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": cal_id} for cal_id in calendar_ids]
            }
            
            freebusy = self.service.freebusy().query(body=body).execute()
            return freebusy
        except HttpError as error:
            raise Exception(f"Failed to query freebusy: {error}")
    
    def get_calendar(self, calendar_id):
        """
        Get calendar metadata.
        
        Args:
            calendar_id: Calendar ID
        """
        try:
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            return calendar
        except HttpError as error:
            raise Exception(f"Failed to get calendar: {error}")
    
    def create_calendar(self, summary, description=None, timezone=None, color_id=None):
        """
        Create a new calendar.
        
        Args:
            summary: Calendar name
            description: Calendar description
            timezone: Timezone (e.g., 'America/Los_Angeles')
            color_id: Calendar color ID
        """
        try:
            calendar = {"summary": summary}
            if description:
                calendar["description"] = description
            if timezone:
                calendar["timeZone"] = timezone
            if color_id:
                calendar["colorId"] = color_id
            
            created_calendar = self.service.calendars().insert(body=calendar).execute()
            return created_calendar
        except HttpError as error:
            raise Exception(f"Failed to create calendar: {error}")
    
    def update_calendar(self, calendar_id, summary=None, description=None, timezone=None, color_id=None):
        """
        Update calendar metadata.
        
        Args:
            calendar_id: Calendar ID
            summary: New calendar name
            description: New description
            timezone: New timezone
            color_id: New color ID (None = no change, "" = remove color)
        """
        try:
            calendar = self.get_calendar(calendar_id)
            
            if summary:
                calendar["summary"] = summary
            if description is not None:
                calendar["description"] = description
            if timezone:
                calendar["timeZone"] = timezone
            if color_id is not None:
                if color_id == "":
                    calendar.pop("colorId", None)
                else:
                    calendar["colorId"] = color_id
            
            updated_calendar = self.service.calendars().update(
                calendarId=calendar_id, body=calendar
            ).execute()
            return updated_calendar
        except HttpError as error:
            raise Exception(f"Failed to update calendar: {error}")
    
    def delete_calendar(self, calendar_id):
        """
        Delete a calendar (secondary calendars only).
        
        Args:
            calendar_id: Calendar ID
        """
        try:
            self.service.calendars().delete(calendarId=calendar_id).execute()
            return True
        except HttpError as error:
            raise Exception(f"Failed to delete calendar: {error}")
    
    def clear_calendar(self, calendar_id):
        """
        Clear all events from a calendar (primary calendar only).
        
        Args:
            calendar_id: Calendar ID
        """
        try:
            self.service.calendars().clear(calendarId=calendar_id).execute()
            return True
        except HttpError as error:
            raise Exception(f"Failed to clear calendar: {error}")
    
    def get_colors(self):
        """Get available colors for calendars and events."""
        try:
            colors = self.service.colors().get().execute()
            return colors
        except HttpError as error:
            raise Exception(f"Failed to get colors: {error}")
    
    def add_attendees(self, event_id, attendee_emails, calendar_id="primary", send_updates="all"):
        """
        Add attendees to an event.
        
        Args:
            event_id: The event ID
            attendee_emails: List of email addresses to add
            calendar_id: Calendar ID (default: 'primary')
            send_updates: Whether to send updates ('all', 'externalOnly', 'none')
        """
        try:
            event = self.get_event(event_id, calendar_id)
            existing_attendees = {att.get("email") for att in event.get("attendees", [])}
            
            new_attendees = []
            for email in attendee_emails:
                if email not in existing_attendees:
                    new_attendees.append({"email": email})
            
            if not new_attendees:
                return event
            
            event["attendees"] = event.get("attendees", []) + new_attendees
            
            updated_event = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates=send_updates
                )
                .execute()
            )
            return updated_event
        except HttpError as error:
            raise Exception(f"Failed to add attendees: {error}")
    
    def remove_attendees(self, event_id, attendee_emails, calendar_id="primary", send_updates="all"):
        """
        Remove attendees from an event.
        
        Args:
            event_id: The event ID
            attendee_emails: List of email addresses to remove
            calendar_id: Calendar ID (default: 'primary')
            send_updates: Whether to send updates ('all', 'externalOnly', 'none')
        """
        try:
            event = self.get_event(event_id, calendar_id)
            attendees = event.get("attendees", [])
            
            # Filter out removed attendees
            emails_to_remove = set(attendee_emails)
            event["attendees"] = [
                att for att in attendees
                if att.get("email") not in emails_to_remove
            ]
            
            updated_event = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates=send_updates
                )
                .execute()
            )
            return updated_event
        except HttpError as error:
            raise Exception(f"Failed to remove attendees: {error}")
    
    def propose_new_time(self, event_id, new_start_time, new_end_time, calendar_id="primary"):
        """
        Propose a new time for an event (as an attendee).
        
        Args:
            event_id: The event ID
            new_start_time: New start datetime (ISO string or datetime)
            new_end_time: New end datetime (ISO string or datetime)
            calendar_id: Calendar ID (default: 'primary')
        """
        try:
            event = self.get_event(event_id, calendar_id)
            
            # Parse new times
            if isinstance(new_start_time, datetime):
                new_start = new_start_time.isoformat()
            else:
                start_dt = parse_datetime(new_start_time)
                new_start = start_dt.isoformat() if start_dt else new_start_time
            
            if isinstance(new_end_time, datetime):
                new_end = new_end_time.isoformat()
            else:
                end_dt = parse_datetime(new_end_time)
                new_end = end_dt.isoformat() if end_dt else new_end_time
            
            # Update attendee's response with proposed time
            # Note: This requires the user to be an attendee
            # The API doesn't have a direct "propose new time" endpoint,
            # but we can update the event with a new time and set attendee response
            event["start"]["dateTime"] = new_start
            event["end"]["dateTime"] = new_end
            
            # Mark as tentative/proposed
            # In practice, proposing new time typically involves:
            # 1. Updating the event time
            # 2. Setting attendee response to "tentative"
            # 3. Sending updates to organizer
            
            updated_event = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates="all"
                )
                .execute()
            )
            return updated_event
        except HttpError as error:
            raise Exception(f"Failed to propose new time: {error}")

