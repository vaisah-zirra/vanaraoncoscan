import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count,Q
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from django.views.decorators.http import require_GET,require_http_methods
from apps.workflow.models import FollowUp
from apps.workflow.followup_forms import FollowUpUpdateForm
from apps.workflow.followup_services import update_followup
from core.permissions import facility_ids_for

def scoped_followups(user):
    return FollowUp.objects.filter(case__patient__facility_id__in=facility_ids_for(user)).select_related('case__patient','completed_by')

@login_required
@require_GET
def followup_list(request):
    today=timezone.localdate();all_items=scoped_followups(request.user)
    counts=all_items.aggregate(open=Count('pk',filter=Q(completed_at__isnull=True)),overdue=Count('pk',filter=Q(completed_at__isnull=True,due_date__lt=today)),today=Count('pk',filter=Q(completed_at__isnull=True,due_date=today)),completed=Count('pk',filter=Q(completed_at__isnull=False)))
    q=request.GET.get('q','').strip()[:120];status=request.GET.get('status','open');sort=request.GET.get('sort','due')
    filters={'open':Q(completed_at__isnull=True),'overdue':Q(completed_at__isnull=True,due_date__lt=today),'today':Q(completed_at__isnull=True,due_date=today),'upcoming':Q(completed_at__isnull=True,due_date__gt=today),'completed':Q(completed_at__isnull=False),'all':Q()}
    if status not in filters: status='open'
    ordering={'due':'due_date','latest':'-due_date','patient':'case__patient__display_name'}
    if sort not in ordering: sort='due'
    items=all_items.filter(filters[status])
    if q: items=items.filter(Q(case__patient__display_name__icontains=q)|Q(case__patient__reference__icontains=q)|Q(notes__icontains=q))
    page=Paginator(items.order_by(ordering[sort],'pk'),10).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    return render(request,'followups.html',{'page':page,'counts':counts,'today':today,'q':q,'status':status,'sort':sort,'querystring':params.urlencode()})

@login_required
@require_http_methods(['GET','POST'])
def followup_detail(request,pk):
    item=get_object_or_404(scoped_followups(request.user),pk=pk)
    form=FollowUpUpdateForm(request.POST if request.method=='POST' else None,initial={'request_id':uuid.uuid4(),'version':item.version})
    if request.method=='POST' and form.is_valid():
        try: update_followup(user=request.user,followup_id=pk,data=request.POST)
        except ValidationError as exc: form.add_error(None,exc.messages[0])
        else:
            messages.success(request,'Follow-up updated. The case timeline and report now reflect this record.')
            return redirect('followup-detail',pk=pk)
    return render(request,'followup_detail.html',{'item':item,'form':form,'today':timezone.localdate(),'updates':item.updates.select_related('actor').order_by('-created_at','-pk')})
