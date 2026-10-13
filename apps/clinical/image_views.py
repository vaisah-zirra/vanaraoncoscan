from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from apps.clinical.models import CaseImage, UltrasoundSample
from apps.clinical.image_services import attach_image, remove_image, ensure_editable
from apps.clinical.services import start_case
from apps.workflow.models import CaseEvent
from apps.dashboard.views import scoped_cases
from core.permissions import facility_ids_for


@login_required
@require_http_methods(['GET', 'POST'])
def image_upload(request, pk):
    case = get_object_or_404(scoped_cases(request.user), pk=pk)
    try:
        ensure_editable(case)
    except ValidationError as exc:
        messages.info(request, exc.messages[0])
        return redirect('case-detail', pk=case.pk)
    error = ''
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            expected = request.POST.get('expected_sample', '')
            if action == 'remove':
                remove_image(user=request.user, case_id=case.pk, expected_sample_id=expected)
                messages.success(request, 'Image removed. You can choose another image.')
            elif action == 'attach':
                value = request.POST.get('sample', '')
                if not value.isdigit():
                    raise ValidationError('Choose an image from the library before attaching it.')
                attach_image(user=request.user, case_id=case.pk, sample_id=int(value), expected_sample_id=expected)
                messages.success(request, 'Image attached and saved to this case.')
            else:
                raise ValidationError('Choose a valid attachment action.')
            return redirect('image-upload', pk=case.pk)
        except ValidationError as exc:
            error = exc.messages[0]
        case.refresh_from_db()
    attachment = CaseImage.objects.filter(case=case).select_related('sample').first()
    available = [s for s in UltrasoundSample.objects.filter(active=True, licence_verified=True) if s.image and s.image.storage.exists(s.image.name)]
    tried = set(CaseImage.objects.filter(case__patient=case.patient).values_list('sample_id', flat=True))
    tried.update(CaseEvent.objects.filter(case__patient=case.patient, kind__in=['IMAGE_ATTACHED', 'IMAGE_REPLACED']).values_list('details__sample_id', flat=True))
    samples = [{'id':s.pk, 'label':'Breast US · '+s.study_id, 'filename':s.display_filename, 'size':s.byte_size,
        'format':s.image_format, 'width':s.width, 'height':s.height, 'url':reverse('sample-image', args=[s.pk]),
        'previously_tried':s.pk in tried} for s in available]
    return render(request, 'image_upload.html', {'case':case, 'attachment':attachment, 'samples':samples,
        'error':error, 'expected_sample':str(attachment.sample_id) if attachment else ''})


@login_required
@require_GET
def sample_image(request, pk):
    if not facility_ids_for(request.user).exists():
        raise PermissionDenied
    sample = get_object_or_404(UltrasoundSample, pk=pk, active=True, licence_verified=True)
    try:
        response = FileResponse(sample.image.open('rb'), content_type='image/bmp' if sample.image_format == 'BMP' else 'image/png', filename=sample.display_filename)
    except (FileNotFoundError, OSError, ValueError):
        raise Http404('Image unavailable') from None
    response['Cache-Control'] = 'private, max-age=300'
    return response


@login_required
@require_POST
def try_another_sample(request, pk):
    original = get_object_or_404(scoped_cases(request.user), pk=pk)
    case = start_case(user=request.user, patient_id=original.patient_id, presenting_concern=original.presenting_concern)
    return redirect('image-upload', pk=case.pk)
