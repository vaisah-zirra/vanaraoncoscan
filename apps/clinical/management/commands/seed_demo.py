"""Create reproducible fictional demo records without overwriting user work."""
import secrets
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import Facility, Membership
from apps.clinical.case_content import CASE_CONTENT
from apps.clinical.models import Patient, Study, Case, QualityAssessment, AIAssessment
from apps.workflow.models import SpecialistReview, Referral, FollowUp, CaseEvent


class Command(BaseCommand):
    help = 'Seed fictional demo accounts and four internally consistent workflow examples.'

    @transaction.atomic
    def handle(self, *args, **options):
        facility, _ = Facility.objects.get_or_create(
            slug='vanara-demo', defaults={'name': 'Acacia Imaging Centre', 'is_demo': True})
        if not facility.is_demo:
            raise CommandError('The reserved facility is not marked as demo; no changes made.')
        credentials = []
        users = {}
        specs = [('facility', 'Amara', 'Bello', False, False),
                 ('reviewer', 'Tunde', 'Okafor', True, False),
                 ('admin', 'Demo', 'Administrator', True, True)]
        for role, first, last, staff, superuser in specs:
            username = f'demo.{role}'
            user, created = get_user_model().objects.get_or_create(username=username,
                defaults={'first_name': first, 'last_name': last, 'email': f'{role}@demo.example.invalid',
                          'is_staff': staff, 'is_superuser': superuser})
            if created:
                password = secrets.token_urlsafe(24)
                user.set_password(password)
                user.save()
                credentials.append((username, password))
            elif user.email != f'{role}@demo.example.invalid':
                raise CommandError(f'{username} is not a recognized seeded account; refusing to change it.')
            users[role] = user
            if role != 'admin':
                membership, _ = Membership.objects.get_or_create(user=user, facility=facility,
                    defaults={'role': Membership.Role.FACILITY if role == 'facility' else Membership.Role.REVIEWER})
                expected = Membership.Role.FACILITY if role == 'facility' else Membership.Role.REVIEWER
                if membership.role != expected:
                    raise CommandError(f'{username} has an unexpected membership; no changes made.')

        examples = [
            ('A', 'Amina Yusuf', Study.Scenario.ROUTINE, Case.Status.FOLLOW_UP,
             'Synthetic scenario: intermittent left breast discomfort; routine assessment pathway.',
             AIAssessment.Disposition.NON_SUSPICIOUS, 'Controlled demo output: non-suspicious disposition.'),
            ('B', 'Ngozi Eze', Study.Scenario.SUSPICIOUS, Case.Status.REFERRAL_CONFIRMED,
             'Synthetic scenario: newly noticed right breast lump; further evaluation pathway.',
             AIAssessment.Disposition.SUSPICIOUS, 'Controlled demo output: suspicious disposition requiring clinician confirmation.'),
            ('C', 'Grace Adeyemi', Study.Scenario.UNCERTAIN, Case.Status.REVIEW_PENDING,
             'Synthetic scenario: an indeterminate finding requiring specialist interpretation.',
             AIAssessment.Disposition.UNCERTAIN, 'Controlled demo output: assessment uncertain; specialist review requested.'),
            ('D', 'Fatima Ibrahim', Study.Scenario.QUALITY, Case.Status.QUALITY_FAILURE,
             'Synthetic scenario: limited study quality; reacquisition required before assessment.', None, None),
        ]
        for letter, name, scenario, status, concern, disposition, finding in examples:
            concern = CASE_CONTENT[letter]['context']
            finding = CASE_CONTENT[letter]['finding']
            study, _ = Study.objects.get_or_create(code=f'DEMO-{letter}', defaults={
                'title': scenario.label, 'scenario': scenario,
                'provenance': 'Scenario metadata only. Licensed ultrasound imagery has not yet been supplied.'})
            patient, _ = Patient.objects.get_or_create(facility=facility, reference=f'DEMO-{letter}',
                defaults={'display_name': name, 'is_synthetic': True})
            if not patient.is_synthetic or study.scenario != scenario:
                raise CommandError('Existing demo reference conflicts with the seed specification.')
            case, created = Case.objects.get_or_create(id=uuid5(NAMESPACE_URL, f'vanara-demo/case/{letter}'),
                defaults={'patient': patient, 'study': study, 'status': status, 'presenting_concern': concern})
            if case.patient_id != patient.pk or case.study_id != study.pk:
                raise CommandError('Reserved demo case identifier belongs to another record.')
            if not created:
                continue  # Preserve subsequent user actions and clinical records.
            events = ['ASSESSMENT_STARTED', 'PATIENT_SELECTED', 'STUDY_SELECTED', 'QUALITY_CHECK_COMPLETED']
            QualityAssessment.objects.create(case=case, adequate=letter != 'D', reason=CASE_CONTENT[letter]['quality'])
            if disposition:
                AIAssessment.objects.create(case=case, disposition=disposition, finding=finding)
                events.append('AI_RESULT_VIEWED')
            if letter == 'A':
                FollowUp.objects.create(case=case, due_date=timezone.localdate() + timedelta(days=14),
                    notes=CASE_CONTENT['A']['followup'])
                events.append('FOLLOWUP_CREATED')
            elif letter == 'B':
                Referral.objects.create(case=case, reason=CASE_CONTENT['B']['referral'],
                    destination='Acacia Specialist Breast Clinic', confirmed_by=users['facility'])
                events.append('REFERRAL_CONFIRMED')
            elif letter == 'C':
                SpecialistReview.objects.create(case=case, reviewer=users['reviewer'])
                events.append('SPECIALIST_REVIEW_REQUESTED')
            else:
                events.append('ASSESSMENT_PAUSED')
            for kind in events:
                CaseEvent.objects.create(case=case, actor=users['facility'], kind=kind,
                    details={'source': 'demo_seed', 'synthetic': True, 'scenario': letter})

        if credentials:
            path = settings.BASE_DIR / '.demo-credentials.txt'
            # Open exclusively: a rerun must never silently replace an existing credential record.
            try:
                with path.open('x', encoding='utf-8') as handle:
                    handle.write('LOCAL DEMO ACCOUNTS — PRIVATE\nAll names and records are fictional.\n\n')
                    for username, password in credentials:
                        handle.write(f'Username: {username}\nPassword: {password}\n\n')
            except FileExistsError as exc:
                raise CommandError('Credential file already exists. No database changes committed.') from exc
        self.stdout.write(self.style.SUCCESS('Demo accounts and four synthetic scenarios ready. Passwords were not printed.'))
