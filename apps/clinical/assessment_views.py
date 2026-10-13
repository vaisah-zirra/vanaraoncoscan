from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_GET
from apps.clinical.models import AIAssessment, QualityAssessment
from apps.dashboard.views import scoped_cases
from apps.clinical.assessment_services import run_quality_check, run_assessment


@login_required
@require_http_methods(['GET','POST'])
def quality_check(request, pk):
    case = get_object_or_404(scoped_cases(request.user),pk=pk)
    if not hasattr(case,'attachment'):
        return redirect('image-upload',pk=pk)
    error=''
    if request.method=='POST':
        try:
            action=request.POST.get('action')
            if action=='quality':
                run_quality_check(user=request.user,case_id=pk,expected_sample_id=request.POST.get('sample'))
                target=reverse('quality-check',args=[pk])
            elif action=='assess':
                run_assessment(user=request.user,case_id=pk,expected_sample_id=request.POST.get('sample'))
                target=reverse('assessment-result',args=[pk])
            else:
                raise ValidationError('Select a valid assessment action.')
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'redirect':target})
            return redirect(target)
        except ValidationError as exc:
            error=exc.messages[0]
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'error':error},status=400)
    quality=QualityAssessment.objects.filter(case=case).first()
    return render(request,'quality_check.html',{'case':case,'quality':quality,'error':error,'has_result':AIAssessment.objects.filter(case=case).exists()})


@login_required
@require_GET
def assessment_result(request,pk):
    case=get_object_or_404(scoped_cases(request.user),pk=pk)
    assessment=get_object_or_404(AIAssessment,case=case)
    if not assessment.details:
        return redirect('case-detail',pk=pk)
    from apps.validation.services import record_view
    record_view(request.user, case, 'assessment')
    from apps.clinical.report_library import report_for_assessment
    return render(request,'assessment_result.html',{'case':case,'assessment':assessment,'result':assessment.details,
        'report':report_for_assessment(assessment, getattr(case,'attachment',None)),
        'review_needed':assessment.disposition in ('UNCERTAIN','REVIEW_REQUIRED'),
        'suspicious':assessment.disposition=='SUSPICIOUS'})
