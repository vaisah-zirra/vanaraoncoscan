from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from apps.dashboard.views import scoped_cases
from apps.workflow.reporting import report_data, render_report


@login_required
@require_GET
@never_cache
def case_report(request, pk):
    case=get_object_or_404(scoped_cases(request.user).select_related('patient__facility'),pk=pk)
    data=report_data(case)
    response=HttpResponse(render_report(data),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="VanaraOncoScan_{case.pk}_{data["revision"]}.pdf"'
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store, max-age=0'
    from apps.validation.services import record_view
    record_view(request.user, case, 'report')
    return response
