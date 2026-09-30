from django import forms
from django.utils import timezone

class FollowUpUpdateForm(forms.Form):
    request_id=forms.UUIDField(widget=forms.HiddenInput)
    version=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    action=forms.ChoiceField(choices=[('COMPLETE','Complete follow-up'),('RESCHEDULE','Reschedule review')],widget=forms.RadioSelect)
    notes=forms.CharField(label='Outcome or reason for rescheduling',max_length=4000,widget=forms.Textarea(attrs={'rows':5,'placeholder':'Record the review outcome and agreed plan, or explain why the review needs a new date.'}))
    due_date=forms.DateField(label='New review date (rescheduling only)',required=False,widget=forms.DateInput(attrs={'type':'date'}))
    confirmed=forms.BooleanField(label='I confirm that these details accurately record the follow-up outcome or scheduling change.')

    def clean(self):
        data=super().clean()
        if data.get('action')=='RESCHEDULE':
            if not data.get('due_date'):
                self.add_error('due_date','Choose the new review date.')
            elif data['due_date']<timezone.localdate():
                self.add_error('due_date','Choose today or a future date.')
        return data
