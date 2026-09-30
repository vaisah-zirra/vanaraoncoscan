from django.contrib.auth.models import AbstractUser
class User(AbstractUser):
    """Custom identity model; facility roles live on memberships."""


from django.db import models
import uuid

class ContactEnquiry(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    organisation = models.CharField(max_length=180, blank=True)
    interest = models.CharField(max_length=32)
    message = models.TextField(max_length=3000)
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Website enquiries'
    def __str__(self):
        return f'{self.name} — {self.interest}'
