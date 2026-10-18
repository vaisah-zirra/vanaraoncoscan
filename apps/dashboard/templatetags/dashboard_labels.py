from django import template
register = template.Library()
@register.filter
def event_label(value):
    return str(value).replace('_', ' ').capitalize().replace('Ai ', 'AI ')


@register.filter
def ago(value):
    """'just now', '5 minutes ago', '2 hours ago' – for queue timestamps."""
    from django.utils import timezone
    from django.utils.timesince import timesince
    if not value:
        return ''
    if (timezone.now() - value).total_seconds() < 60:
        return 'just now'
    return timesince(value).split(',')[0] + ' ago'
