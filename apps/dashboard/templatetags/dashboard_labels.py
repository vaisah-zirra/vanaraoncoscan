from django import template
register = template.Library()
@register.filter
def event_label(value):
    return str(value).replace('_', ' ').capitalize().replace('Ai ', 'AI ')
