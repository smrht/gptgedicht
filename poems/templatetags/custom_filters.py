from django import template

register = template.Library()

@register.filter
def divided_by(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None 