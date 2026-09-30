from uuid import NAMESPACE_URL, uuid5
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.clinical.case_content import CASE_CONTENT
from apps.clinical.models import Case, QualityAssessment, AIAssessment
from apps.organizations.models import Facility
from apps.workflow.models import Referral, FollowUp

class Command(BaseCommand):
    help = 'Replace legacy placeholder copy in the four seeded cases; preserve edited records.'

    @transaction.atomic
    def handle(self, *args, **options):
        Facility.objects.filter(slug='vanara-demo', is_demo=True, name='Acacia Imaging Centre — Demo').update(name='Acacia Imaging Centre')
        changed = 0
        for letter, content in CASE_CONTENT.items():
            case = Case.objects.filter(pk=uuid5(NAMESPACE_URL, f'vanara-demo/case/{letter}'), patient__facility__slug='vanara-demo', patient__is_synthetic=True).first()
            if not case:
                continue
            changed += Case.objects.filter(pk=case.pk, presenting_concern__startswith='Synthetic scenario:').update(presenting_concern=content['context'])
            QualityAssessment.objects.filter(case=case, reason__startswith='Simulated ').update(reason=content['quality'])
            AIAssessment.objects.filter(case=case, finding__startswith='Controlled demo output:').update(finding=content['finding'])
            if letter == 'A':
                FollowUp.objects.filter(case=case, notes__startswith='Fictional follow-up').update(notes=content['followup'])
            if letter == 'B':
                Referral.objects.filter(case=case, reason__startswith='Demo clinician-confirmed').update(reason=content['referral'], destination='Acacia Specialist Breast Clinic')
        self.stdout.write(self.style.SUCCESS(f'Updated {changed} legacy case narratives. User-edited content preserved.'))
