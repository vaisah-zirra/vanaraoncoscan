import uuid
from django.db import models

class Patient(models.Model):
    facility = models.ForeignKey('organizations.Facility', on_delete=models.PROTECT)
    reference = models.CharField(max_length=60)
    display_name = models.CharField(max_length=160)
    is_synthetic = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['facility', 'reference'], name='unique_patient_reference')]

class Study(models.Model):
    class Scenario(models.TextChoices):
        ROUTINE = 'ROUTINE', 'Routine assessment'
        SUSPICIOUS = 'SUSPICIOUS', 'Suspicious finding'
        UNCERTAIN = 'UNCERTAIN', 'Uncertain assessment'
        QUALITY = 'QUALITY', 'Image quality issue'
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=160)
    scenario = models.CharField(max_length=20, choices=Scenario.choices)
    image = models.FileField(upload_to='curated/', blank=True)
    provenance = models.TextField(blank=True)
    licence_verified = models.BooleanField(default=False)

class Case(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        QUALITY_PENDING = 'QUALITY_PENDING', 'Awaiting quality check'
        QUALITY_PASSED = 'QUALITY_PASSED', 'Ready for assessment'
        ASSESSED = 'ASSESSED', 'Assessed'
        REVIEW_PENDING = 'REVIEW_PENDING', 'Awaiting specialist'
        REVIEWED = 'REVIEWED', 'Specialist reviewed'
        QUALITY_FAILURE = 'QUALITY_FAILURE', 'Quality failure'
        REFERRAL_CONFIRMED = 'REFERRAL_CONFIRMED', 'Referral confirmed'
        FOLLOW_UP = 'FOLLOW_UP', 'Follow-up'
        COMPLETED = 'COMPLETED', 'Completed'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    study = models.ForeignKey(Study, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    presenting_concern = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class QualityAssessment(models.Model):
    case = models.OneToOneField(Case, on_delete=models.PROTECT)
    adequate = models.BooleanField()
    reason = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AIAssessment(models.Model):
    class Disposition(models.TextChoices):
        NON_SUSPICIOUS = 'NON_SUSPICIOUS', 'Non-suspicious'
        SUSPICIOUS = 'SUSPICIOUS', 'Suspicious'
        UNCERTAIN = 'UNCERTAIN', 'Uncertain'
        REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review required'
    case = models.OneToOneField(Case, on_delete=models.PROTECT)
    disposition = models.CharField(max_length=20, choices=Disposition.choices)
    finding = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    engine = models.CharField(max_length=80, default='demo-v1')
    created_at = models.DateTimeField(auto_now_add=True)


class UltrasoundSample(models.Model):
    """Licensed library asset; outcome mapping is separate from image selection."""
    code = models.SlugField(unique=True)
    label = models.CharField(max_length=80)
    filename = models.CharField(max_length=120)
    image = models.FileField(upload_to='ultrasound-library/')
    byte_size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    source_url = models.URLField()
    source_filename = models.CharField(max_length=120)
    attribution = models.TextField()
    licence_url = models.URLField()
    licence_verified = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    STUDY_IDS = {'sample-01':'US-24-10187', 'sample-02':'US-24-10233', 'sample-03':'US-24-10241',
                 'sample-04':'US-24-10302', 'sample-05':'US-24-10356', 'sample-06':'US-24-10389'}

    @property
    def study_id(self):
        return self.STUDY_IDS.get(self.code, self.label)

    @property
    def display_filename(self):
        return f"{self.study_id}.{'bmp' if self.filename.lower().endswith('.bmp') else 'png'}"

    @property
    def image_format(self):
        return 'BMP' if self.filename.lower().endswith('.bmp') else 'PNG'

    class Meta:
        ordering = ['code']


class CaseImage(models.Model):
    case = models.OneToOneField(Case, on_delete=models.PROTECT, related_name='attachment')
    sample = models.ForeignKey(UltrasoundSample, on_delete=models.PROTECT)
    attached_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    attached_at = models.DateTimeField(auto_now=True)
