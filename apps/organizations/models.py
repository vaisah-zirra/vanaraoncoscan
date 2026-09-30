from django.conf import settings
from django.db import models

class Facility(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    is_demo = models.BooleanField(default=False)
    def __str__(self):
        return self.name

class Membership(models.Model):
    class Role(models.TextChoices):
        FACILITY = 'FACILITY', 'Facility User'
        REVIEWER = 'REVIEWER', 'Specialist Reviewer'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'facility'], name='unique_facility_membership')]
