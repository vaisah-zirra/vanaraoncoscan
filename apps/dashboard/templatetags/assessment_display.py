from django import template
from apps.clinical.presentation import assessment_display, LEGEND
register=template.Library()

@register.simple_tag
def display_for(case):
    return assessment_display(case)

@register.inclusion_tag('components/confidence_card.html')
def confidence_card(case, compact=False):
    return {'display':assessment_display(case),'compact':compact}

@register.inclusion_tag('components/assessment_legend.html')
def assessment_legend():
    return {'legend':LEGEND}

@register.inclusion_tag('components/specialist_response.html')
def specialist_response(case):
    from apps.workflow.specialist_content import specialist_content
    return specialist_content(case)
