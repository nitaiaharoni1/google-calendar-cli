"""Google Calendar API wrapper."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .auth import get_credentials, check_auth
from .utils import parse_datetime, format_datetime
from .retry import with_retry
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Tuple


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
                if time_min.tzinfo is not None:
                    # Convert to UTC, then format without offset
                    time_min = time_min.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    # Assume UTC for naive datetimes
                    time_min = time_min.strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(time_max, datetime):
                if time_max.tzinfo is not None:
                    # Convert to UTC, then format without offset
                    time_max = time_max.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    # Assume UTC for naive datetimes
                    time_max = time_max.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": cal_id} for cal_id in calendar_ids]
            }
            
            freebusy = self.service.freebusy().query(body=body).execute()
            return freebusy
        except HttpError as error:
            raise Exception(f"Failed to query freebusy: {error}")
    
    @with_retry()
    def find_available_slots(
        self,
        attendee_emails: List[str],
        duration_minutes: int,
        time_min: datetime,
        time_max: datetime,
        working_hours_start: int = 9,
        working_hours_end: int = 18,
        exclude_weekends: bool = True,
        timezone: str = "UTC"
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find available time slots when all attendees are free.
        
        Args:
            attendee_emails: List of email addresses to check availability for
            duration_minutes: Duration of the meeting in minutes
            time_min: Start of search window (datetime)
            time_max: End of search window (datetime)
            working_hours_start: Start of working hours (0-23, default: 9)
            working_hours_end: End of working hours (0-23, default: 18)
            exclude_weekends: Whether to exclude weekends (default: True)
            timezone: Timezone string (default: "UTC")
        
        Returns:
            List of (start, end) datetime tuples representing available slots
        """
        try:
            # Use email addresses as calendar IDs (primary calendar for each user)
            calendar_ids = attendee_emails.copy()
            
            # Query FreeBusy for all attendees
            freebusy_result = self.freebusy_query(time_min, time_max, calendar_ids)
            
            # Collect all busy periods from all calendars
            all_busy_periods = []
            calendars = freebusy_result.get("calendars", {})
            
            for cal_id, cal_data in calendars.items():
                errors = cal_data.get("errors", [])
                if errors:
                    # Log but continue - some calendars may not be accessible
                    continue
                
                busy_periods = cal_data.get("busy", [])
                for period in busy_periods:
                    start_str = period.get("start")
                    end_str = period.get("end")
                    if start_str and end_str:
                        try:
                            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                            # Ensure timezone-aware (API returns UTC)
                            if start_dt.tzinfo is None:
                                start_dt = start_dt.replace(tzinfo=timezone.utc)
                            if end_dt.tzinfo is None:
                                end_dt = end_dt.replace(tzinfo=timezone.utc)
                            all_busy_periods.append((start_dt, end_dt))
                        except ValueError:
                            continue
            
            # Sort busy periods by start time
            all_busy_periods.sort(key=lambda x: x[0])
            
            # Merge overlapping busy periods
            merged_busy = []
            if all_busy_periods:
                current_start, current_end = all_busy_periods[0]
                # Ensure first period is timezone-aware
                if current_start.tzinfo is None:
                    current_start = current_start.replace(tzinfo=timezone.utc)
                if current_end.tzinfo is None:
                    current_end = current_end.replace(tzinfo=timezone.utc)
                
                for start, end in all_busy_periods[1:]:
                    # Ensure timezone-aware
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    
                    if start <= current_end:
                        # Overlapping or adjacent - merge
                        current_end = max(current_end, end)
                    else:
                        # Gap - save current and start new
                        merged_busy.append((current_start, current_end))
                        current_start, current_end = start, end
                merged_busy.append((current_start, current_end))
            
            # Find all free slots by generating potential slots and filtering
            available_slots = []
            duration_delta = timedelta(minutes=duration_minutes)
            
            # Get timezone for working hours conversion
            try:
                tz = ZoneInfo(timezone)
            except Exception:
                tz = timezone.utc
            
            # Ensure time_min and time_max are timezone-aware and convert to UTC
            if time_min.tzinfo is None:
                time_min = time_min.replace(tzinfo=timezone.utc)
            else:
                time_min = time_min.astimezone(timezone.utc)
            if time_max.tzinfo is None:
                time_max = time_max.replace(tzinfo=timezone.utc)
            else:
                time_max = time_max.astimezone(timezone.utc)
            
            # Convert time range to target timezone for day iteration
            time_min_local = time_min.astimezone(tz)
            time_max_local = time_max.astimezone(tz)
            
            # Generate all potential slots within the time range
            current_date = time_min_local.date()
            end_date = time_max_local.date()
            
            while current_date <= end_date:
                # Skip weekends if excluded
                if exclude_weekends and current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
                    continue
                
                # Generate slots for this day within working hours
                day_start = datetime.combine(current_date, datetime.min.time().replace(hour=working_hours_start), tzinfo=tz)
                day_end = datetime.combine(current_date, datetime.min.time().replace(hour=working_hours_end), tzinfo=tz)
                
                # Ensure day_start is within our time range
                if day_start < time_min_local:
                    day_start = time_min_local
                if day_end > time_max_local:
                    day_end = time_max_local
                
                # Generate slots starting from day_start, incrementing by duration
                slot_start = day_start
                while slot_start + duration_delta <= day_end:
                    slot_end = slot_start + duration_delta
                    
                    # Convert back to UTC for comparison with busy periods
                    slot_start_utc = slot_start.astimezone(timezone.utc)
                    slot_end_utc = slot_end.astimezone(timezone.utc)
                    
                    # Check if this slot overlaps with any busy period
                    is_free = True
                    for busy_start, busy_end in merged_busy:
                        # Busy periods should already be timezone-aware from parsing, but check defensively
                        if busy_start.tzinfo is None:
                            busy_start = busy_start.replace(tzinfo=timezone.utc)
                        if busy_end.tzinfo is None:
                            busy_end = busy_end.replace(tzinfo=timezone.utc)
                        
                        # Check for overlap
                        if not (slot_end_utc <= busy_start or slot_start_utc >= busy_end):
                            is_free = False
                            break
                    
                    # Also check if slot is within our time range (time_min/time_max are already UTC)
                    if slot_start_utc < time_min or slot_end_utc > time_max:
                        is_free = False
                    
                    if is_free:
                        available_slots.append((slot_start_utc, slot_end_utc))
                    
                    # Move to next slot (increment by duration)
                    slot_start += duration_delta
                
                current_date += timedelta(days=1)
            
            # Sort slots by start time
            available_slots.sort(key=lambda x: x[0])
            
            return available_slots
            
        except Exception as error:
            raise Exception(f"Failed to find available slots: {error}")
    
    def _is_valid_slot(
        self,
        start: datetime,
        end: datetime,
        working_hours_start: int,
        working_hours_end: int,
        exclude_weekends: bool,
        timezone_str: str
    ) -> bool:
        """
        Check if a time slot is valid based on constraints.
        
        Args:
            start: Slot start time (timezone-aware datetime)
            end: Slot end time (timezone-aware datetime)
            working_hours_start: Start of working hours (0-23)
            working_hours_end: End of working hours (0-23)
            exclude_weekends: Whether to exclude weekends
            timezone_str: Timezone string (e.g., "America/Los_Angeles", "UTC")
        
        Returns:
            True if slot is valid, False otherwise
        """
        try:
            # Convert to target timezone for working hours check
            tz = ZoneInfo(timezone_str)
            start_local = start.astimezone(tz)
            end_local = end.astimezone(tz)
        except Exception:
            # Fallback to UTC if timezone is invalid
            tz = timezone.utc
            start_local = start.astimezone(tz) if start.tzinfo else start.replace(tzinfo=tz)
            end_local = end.astimezone(tz) if end.tzinfo else end.replace(tzinfo=tz)
        
        # Check weekend exclusion
        if exclude_weekends:
            weekday = start_local.weekday()  # 0=Monday, 6=Sunday
            if weekday >= 5:  # Saturday or Sunday
                return False
        
        # Check working hours in the target timezone
        start_hour = start_local.hour
        end_hour = end_local.hour
        
        # Slot must start at or after working hours start
        if start_hour < working_hours_start:
            return False
        
        # Slot must end at or before working hours end
        if end_hour > working_hours_end:
            return False
        elif end_hour == working_hours_end and end_local.minute > 0:
            return False
        
        return True
    
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

