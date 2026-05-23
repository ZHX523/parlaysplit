import json

from django import template
from django.utils.html import escape

from parlays.models import LEG_TYPE_DESCRIPTION_HINTS
from parlays.utils import format_dollars

register = template.Library()


@register.filter
def currency(value):
    """Render a dollar amount with commas, e.g. $1,234.56."""
    return format_dollars(value)


@register.simple_tag
def leg_type_hints_attr():
    """JSON object of leg_type -> description placeholder, HTML-escaped for attributes."""
    return escape(json.dumps(LEG_TYPE_DESCRIPTION_HINTS))