"""Tests for Google Calendar CLI configuration."""

import pytest
from unittest.mock import patch
from google_calendar_cli.config import get_preference, set_preference


def test_get_preference_default():
    """Test getting preference with default value."""
    with patch("google_calendar_cli.config.load_preferences") as mock_load:
        mock_load.return_value = {}
        result = get_preference("nonexistent", "default_value")
        assert result == "default_value"


def test_set_preference():
    """Test setting a preference."""
    with patch("google_calendar_cli.config.load_preferences") as mock_load, \
         patch("google_calendar_cli.config.save_preferences") as mock_save:
        mock_load.return_value = {}
        set_preference("test_key", "test_value")
        mock_save.assert_called_once()

