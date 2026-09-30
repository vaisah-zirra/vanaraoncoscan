from .services import participant_for, round_queryset, round_progress

def workspace_validation(request):
    if request.path.startswith(('/accounts/', '/admin/', '/validation/')) or request.path in ('/', '/pilot/', '/information/'):
        return {}
    participant = participant_for(request.user)
    if not participant:
        return {}
    items = round_queryset(participant)
    case_id = getattr(request, 'resolver_match', None)
    case_id = case_id.kwargs.get('pk') if case_id else None
    current = items.filter(case_id=case_id).first() if request.path.startswith('/cases/') and case_id else items.first()
    prompt = items.filter(completed_at__isnull=False, feedback__isnull=True, prompt_dismissed=False).first()
    return {'validation_participant':participant, 'validation_progress':round_progress(current) if current else None, 'validation_prompt':prompt}
