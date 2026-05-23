from django import template

from parlays.utils import format_dollars

register = template.Library()


@register.filter
def currency(value):
    """Render a dollar amount with commas, e.g. $1,234.56."""
    return format_dollars(value)
