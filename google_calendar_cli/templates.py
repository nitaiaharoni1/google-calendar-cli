"""Event templates management for Google Calendar CLI."""

import json
import os
from pathlib import Path
from .shared_auth import GOOGLE_CONFIG_DIR


TEMPLATES_DIR = GOOGLE_CONFIG_DIR / "templates"


def ensure_templates_dir():
    """Ensure templates directory exists."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return TEMPLATES_DIR


def list_templates():
    """List all available event templates."""
    ensure_templates_dir()
    templates = []
    
    for template_file in TEMPLATES_DIR.glob("*.json"):
        try:
            with open(template_file) as f:
                template = json.load(f)
                template["name"] = template_file.stem
                templates.append(template)
        except:
            continue
    
    return templates


def get_template(name):
    """Get a template by name."""
    ensure_templates_dir()
    template_path = TEMPLATES_DIR / f"{name}.json"
    
    if not template_path.exists():
        return None
    
    try:
        with open(template_path) as f:
            return json.load(f)
    except:
        return None


def create_template(name, title=None, description=None, location=None, duration_minutes=60, attendees=None, reminders=None):
    """Create or update an event template."""
    ensure_templates_dir()
    
    template = {
        "title": title or "",
        "description": description or "",
        "location": location or "",
        "duration_minutes": duration_minutes,
        "attendees": attendees or [],
        "reminders": reminders or {}
    }
    
    template_path = TEMPLATES_DIR / f"{name}.json"
    with open(template_path, "w") as f:
        json.dump(template, f, indent=2)
    
    # Ensure secure permissions
    os.chmod(template_path, 0o600)
    
    return template


def delete_template(name):
    """Delete a template."""
    ensure_templates_dir()
    template_path = TEMPLATES_DIR / f"{name}.json"
    
    if template_path.exists():
        template_path.unlink()
        return True
    
    return False


def render_template(name, **kwargs):
    """Render a template with variable substitution."""
    template = get_template(name)
    if not template:
        raise ValueError(f"Template '{name}' not found")
    
    rendered = {}
    for key, value in template.items():
        if isinstance(value, str):
            # Simple variable substitution: {{var_name}}
            rendered_value = value
            for var_name, var_value in kwargs.items():
                rendered_value = rendered_value.replace(f"{{{{{var_name}}}}}}}", str(var_value))
            rendered[key] = rendered_value
        elif isinstance(value, list):
            rendered[key] = [v.replace(f"{{{{{k}}}}}}}", str(vv)) if isinstance(v, str) else v 
                            for v in value for k, vv in kwargs.items()]
        else:
            rendered[key] = value
    
    return rendered

