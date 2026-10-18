from django.conf import settings
from django.db import models

class SpecialistReview(models.Model):
    case = models.ForeignKey('clinical.Case', on_delete=models.PROTECT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    assessment = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    agrees_with_ai = models.BooleanField(null=True)
    class Concordance(models.TextChoices):
        AGREE = 'AGREE', 'Agree with AI'
        PARTIAL = 'PARTIAL', 'Partially agree'
        DISAGREE = 'DISAGREE', 'Disagree with AI'
    concordance = models.CharField(max_length=10, choices=Concordance.choices, blank=True)
    birads = models.CharField('BI-RADS category', max_length=3, blank=True)
    findings = models.TextField(blank=True)
    # Pilot only: signed automatically from the image's predefined second read (never shown to testers).
    simulated = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)

class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Awaiting acknowledgement'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        SCHEDULED = 'SCHEDULED', 'Appointment scheduled'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    appointment_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)

    case = models.OneToOneField('clinical.Case', on_delete=models.PROTECT)
    reason = models.TextField()
    destination = models.CharField(max_length=240)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(auto_now_add=True)
    urgency = models.CharField(max_length=16, choices=[('ROUTINE', 'Routine'), ('PRIORITY', 'Priority'), ('URGENT', 'Urgent')], blank=True)

class FollowUp(models.Model):
    case = models.ForeignKey('clinical.Case', on_delete=models.PROTECT)
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    outcome = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=0)

class CaseEvent(models.Model):
    case = models.ForeignKey('clinical.Case', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    kind = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['created_at', 'pk']


class ClinicalDecision(models.Model):
    class Action(models.TextChoices):
        REFERRAL = 'REFERRAL', 'Referral confirmed'
        SPECIALIST = 'SPECIALIST', 'Specialist review requested'
        FOLLOW_UP = 'FOLLOW_UP', 'Follow-up scheduled'
        ROUTINE = 'ROUTINE', 'Assessment completed / return to routine care'
    case = models.ForeignKey('clinical.Case', on_delete=models.PROTECT, related_name='clinical_decisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    action = models.CharField(max_length=16, choices=Action.choices)
    notes = models.TextField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class FollowUpUpdate(models.Model):
    followup = models.ForeignKey(FollowUp, on_delete=models.PROTECT, related_name='updates')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    action = models.CharField(max_length=16, choices=[('COMPLETE','Follow-up completed'),('RESCHEDULE','Review rescheduled')])
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class ReferralUpdate(models.Model):
    referral = models.ForeignKey(Referral, on_delete=models.PROTECT, related_name='updates')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    status = models.CharField(max_length=16, choices=Referral.Status.choices)
    notes = models.TextField()
    appointment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
