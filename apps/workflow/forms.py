from django import forms
from django.utils import timezone
from apps.workflow.models import ClinicalDecision

class ClinicalDecisionForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.CharField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('REFERRAL', 'Confirm referral'), ('SPECIALIST', 'Request specialist review'), ('FOLLOW_UP', 'Schedule follow-up'), ('ROUTINE', 'Complete assessment / return to routine care')], widget=forms.RadioSelect)
    notes = forms.CharField(label='Clinical review notes', max_length=4000, widget=forms.Textarea(attrs={'rows':5}))
    destination = forms.CharField(label='Receiving service', max_length=240, required=False,
        widget=forms.TextInput(attrs={'list':'receiving-services','placeholder':'Type a service or choose a suggestion'}))
    urgency = forms.ChoiceField(label='Referral urgency', required=False,
        choices=[('', 'Choose urgency'), ('ROUTINE','Routine'), ('PRIORITY','Priority'), ('URGENT','Urgent')])
    reason = forms.CharField(label='Referral reason / specialist review question', max_length=4000, required=False,
        widget=forms.Textarea(attrs={'rows':4}))
    due_date = forms.DateField(label='Follow-up date', required=False, widget=forms.DateInput(attrs={'type':'date'}))
    followup_notes = forms.CharField(label='Follow-up plan', max_length=4000, required=False, widget=forms.Textarea(attrs={'rows':4}))
    safety_net = forms.CharField(label='Routine-care plan and return advice', max_length=4000, required=False, widget=forms.Textarea(attrs={'rows':4}))
    concordant = forms.BooleanField(required=False, label='I confirm the history, examination and imaging are concordant, with no unresolved concern requiring further assessment.')
    confirmed = forms.BooleanField(label='I have reviewed the history, image and findings, and confirm this decision.')

    def clean(self):
        data = super().clean()
        action = data.get('action')
        required = {'REFERRAL':['destination','urgency','reason'], 'SPECIALIST':['reason'], 'FOLLOW_UP':['due_date','followup_notes'], 'ROUTINE':['safety_net','concordant']}.get(action, [])
        for field in required:
            if not data.get(field):
                self.add_error(field, 'Complete this field for the selected decision.')
        if action == 'FOLLOW_UP' and data.get('due_date') and data['due_date'] < timezone.localdate():
            self.add_error('due_date', 'Choose today or a future date.')
        return data
