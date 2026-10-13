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


@register.inclusion_tag('components/structured_report.html')
def structured_report(case, compact=False):
    from apps.clinical.report_library import report_for_assessment
    assessment = getattr(case, 'aiassessment', None)
    quality = getattr(case, 'qualityassessment', None)
    report = None
    if assessment and not (quality and not quality.adequate):
        report = report_for_assessment(assessment, getattr(case, 'attachment', None))
        if report and report.get('patient_summary_reviewed') and case.specialistreview_set.filter(signed_at__isnull=False).exists():
            report = {**report, 'patient_summary': report['patient_summary_reviewed']}
    return {'case': case, 'report': report, 'display': assessment_display(case), 'compact': compact}
