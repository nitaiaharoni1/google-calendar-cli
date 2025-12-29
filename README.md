# Google Calendar CLI

A powerful command-line interface for Google Calendar built with Python. Manage your events directly from the terminal.

## Features

- 📅 **List events** from your calendars
- ➕ **Create events** with custom times and descriptions
- ✏️ **Update events** - modify title, time, location, or description
- 🗑️ **Delete events** with confirmation
- 📋 **List calendars** - view all your calendars
- 📆 **Today's events** - quick view of today's schedule
- 📊 **Week view** - see all events for the current week
- 🔐 **Secure OAuth 2.0 authentication**

## Installation

### Using Homebrew (macOS)

```bash
brew tap nitaiaharoni/google-calendar-cli
brew install google-calendar-cli
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/nitaiaharoni/google-calendar-cli.git
cd google-calendar-cli
```

2. Install dependencies:
```bash
pip3 install -r requirements.txt
```

3. Install the package:
```bash
pip3 install -e .
```

Or use the installation script:
```bash
./install.sh
```

## Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Calendar API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

### 2. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace)
   - Fill in required fields (App name, User support email, etc.)
   - Add your email to test users
   - Save and continue
4. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: Calendar CLI (or your preferred name)
   - Click "Create"
5. Download the credentials file:
   - Click the download icon next to your OAuth client
   - Save it as `credentials.json`
   - Place it in the current directory or your home directory (`~/`)

### 3. Authenticate

Run the initialization command:

```bash
google-calendar init
```

This will:
- Open a browser window for Google authentication
- Ask you to grant permissions to the Google Calendar API
- Save your refresh token securely in `~/.google_calendar_token.json`

## Usage

### Basic Commands

```bash
# Show authenticated user info
google-calendar me

# List upcoming events (default: 10)
google-calendar list

# List more events
google-calendar list --max 20

# List events from a specific calendar
google-calendar list --calendar <calendar-id>

# Get event details
google-calendar get <event-id>

# Create a new event
google-calendar create "Meeting with Team" --start "2025-01-15T14:00:00" --end "2025-01-15T15:00:00"

# Create event with description and location
google-calendar create "Lunch" --start "2025-01-15T12:00:00" --description "Team lunch" --location "Restaurant XYZ"

# Update an event
google-calendar update <event-id> --title "New Title" --start "2025-01-15T16:00:00"

# Delete an event
google-calendar delete <event-id>

# List all calendars
google-calendar calendars

# Show today's events
google-calendar today

# Show this week's events
google-calendar week
```

### Date/Time Formats

The CLI accepts various date/time formats:

- ISO format: `2025-01-15T14:00:00`
- ISO with timezone: `2025-01-15T14:00:00Z` or `2025-01-15T14:00:00+00:00`
- Date only: `2025-01-15` (will use default time)

Examples:
```bash
# Full ISO format
google-calendar create "Meeting" --start "2025-01-15T14:00:00" --end "2025-01-15T15:00:00"

# Date only (uses default time)
google-calendar create "All Day Event" --start "2025-01-15"
```

## Command Reference

| Command | Description |
|---------|-------------|
| `google-calendar init` | Initialize and authenticate with Google Calendar API |
| `google-calendar me` | Show authenticated user information |
| `google-calendar list [--max N] [--calendar CALENDAR_ID]` | List upcoming events |
| `google-calendar get <event-id> [--calendar CALENDAR_ID]` | Get event details |
| `google-calendar create <title> [--start DATETIME] [--end DATETIME] [--description TEXT] [--location LOCATION]` | Create event |
| `google-calendar update <event-id> [--title TITLE] [--start DATETIME] [--end DATETIME] [--description TEXT] [--location LOCATION]` | Update event |
| `google-calendar delete <event-id> [--calendar CALENDAR_ID]` | Delete event |
| `google-calendar calendars` | List all calendars |
| `google-calendar today [--calendar CALENDAR_ID]` | Show today's events |
| `google-calendar week [--calendar CALENDAR_ID]` | Show this week's events |

## Examples

### Quick Event Creation

```bash
# Create a meeting in 1 hour
calendar create "Team Standup" --start "$(date -u -v+1H +%Y-%m-%dT%H:%M:%S)" --end "$(date -u -v+2H +%Y-%m-%dT%H:%M:%S)"
```

### View Today's Schedule

```bash
# See what's happening today
google-calendar today
```

### Manage Multiple Calendars

```bash
# List all calendars
google-calendar calendars

# List events from a specific calendar
google-calendar list --calendar <calendar-id>

# Create event in a specific calendar
google-calendar create "Event" --calendar <calendar-id> --start "2025-01-15T14:00:00"
```

### Update Events

```bash
# Change event time
google-calendar update <event-id> --start "2025-01-15T16:00:00" --end "2025-01-15T17:00:00"

# Change title and location
google-calendar update <event-id> --title "New Meeting Title" --location "New Location"
```

## Troubleshooting

### Authentication Issues

**"credentials.json not found"**
- Make sure you've downloaded the OAuth credentials from Google Cloud Console
- Place `credentials.json` in the current directory or your home directory

**"Not authenticated"**
- Run `google-calendar init` to authenticate
- Make sure you've granted all required permissions

**Token expired**
- The CLI automatically refreshes tokens, but if issues persist:
  - Delete `~/.google_calendar_token.json`
  - Run `google-calendar init` again

### API Errors

**"Quota exceeded"**
- Google Calendar API has rate limits
- Wait a few minutes and try again
- Consider reducing the number of API calls

**"Permission denied"**
- Make sure you've enabled the Google Calendar API in Google Cloud Console
- Check that your OAuth credentials are correct
- Verify you've granted the necessary scopes

**"Calendar not found"**
- Use `calendar calendars` to list available calendars
- Make sure you're using the correct calendar ID
- Default calendar ID is `primary`

## Requirements

- Python 3.8 or higher
- Google Cloud Project with Google Calendar API enabled
- OAuth 2.0 credentials

## Security

- Tokens are stored securely in `~/.google_calendar_token.json` with 600 permissions
- Never commit `credentials.json` or token files to version control
- Use environment variables for CI/CD if needed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Created by [Nitai Aharoni](https://github.com/nitaiaharoni)

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/nitaiaharoni/google-calendar-cli/issues) page.

