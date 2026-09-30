import uuid
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

ROLES = [('Clinician', 'Doctor / clinician'), ('Imaging', 'Radiologist / sonographer'), ('Nursing', 'Nurse / care coordinator'), ('Community', 'Community Health Worker'), ('Leadership', 'Institutional leader / decision-maker'), ('Research', 'Researcher / educator'), ('Other', 'Other')]
INTENTS = [('Pilot', 'Discuss a pilot'), ('Pricing', 'Discuss pricing'), ('Deployment', 'Discuss deployment'), ('Demo', 'Request a guided demonstration'), ('Waitlist', 'Join the waitlist'), ('None', 'No next step yet')]

class Participant(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='participant')
    facility = models.OneToOneField('organizations.Facility', on_delete=models.PROTECT)
    role = models.CharField(max_length=24, choices=ROLES)
    organisation = models.CharField(max_length=180)
    source = models.CharField(max_length=80, default='direct')
    campaign = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    whatsapp_consent = models.BooleanField(default=False)
    research_consent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True)
    class Meta:
        ordering = ['-created_at']

class Visit(models.Model):
    visitor = models.UUIDField(default=uuid.uuid4, db_index=True)
    participant = models.ForeignKey(Participant, null=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=80, default='direct')
    campaign = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now_add=True)
    landing_seen = models.BooleanField(default=False)

class WalkthroughRound(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='rounds')
    case = models.OneToOneField('clinical.Case', on_delete=models.CASCADE, related_name='walkthrough_round')
    started_at = models.DateTimeField(auto_now_add=True)
    assessment_viewed_at = models.DateTimeField(null=True)
    report_requested_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    prompt_dismissed = models.BooleanField(default=False)
    class Meta:
        ordering = ['-started_at']

class Feedback(models.Model):
    round = models.OneToOneField(WalkthroughRound, on_delete=models.CASCADE, related_name='feedback')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    most_useful = models.CharField(max_length=50)
    barrier = models.CharField(max_length=50, blank=True)  # Retained for original responses.
    barriers = models.JSONField(default=list)
    suggestion = models.TextField(max_length=2000, blank=True)
    intent = models.CharField(max_length=24, choices=INTENTS)
    contact_consent = models.BooleanField(default=False)
    completion_at_submission = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='feedback_rating_1_to_5')]

class Lead(models.Model):
    STAGES = [('New', 'New'), ('Contacted', 'Contacted'), ('Demo', 'Demo completed'), ('Pilot', 'Pilot discussion'), ('Next', 'Next action agreed'), ('Closed', 'Closed')]
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    participant = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.SET_NULL)
    enquiry = models.OneToOneField('accounts.ContactEnquiry', null=True, blank=True, on_delete=models.SET_NULL)
    feedback = models.OneToOneField(Feedback, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    role = models.CharField(max_length=24, choices=ROLES, blank=True)
    organisation = models.CharField(max_length=180, blank=True)
    interest = models.CharField(max_length=32)
    message = models.TextField(max_length=3000, blank=True)
    source = models.CharField(max_length=80, default='direct')
    campaign = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    whatsapp_consent = models.BooleanField(default=False)
    contact_consent_at = models.DateTimeField()
    stage = models.CharField(max_length=16, choices=STAGES, default='New')
    next_action = models.CharField(max_length=500, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class LeadUpdate(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='updates')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    stage = models.CharField(max_length=16)
    next_action = models.CharField(max_length=500, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
