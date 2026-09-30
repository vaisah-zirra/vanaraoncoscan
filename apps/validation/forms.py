from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import ROLES, INTENTS, Lead
from .feedback_choices import USEFUL_PARTS, ADOPTION_FACTORS

class ContactDetails(forms.Form):
    full_name = forms.CharField(max_length=120, label='Full name', widget=forms.TextInput(attrs={'autocomplete':'name'}))
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    role = forms.ChoiceField(choices=[('', 'Choose your professional role')] + ROLES, label='Professional role')
    organisation = forms.CharField(max_length=180, label='Organisation / institution', widget=forms.TextInput(attrs={'autocomplete':'organization'}))
    whatsapp = forms.RegexField(r'^\+?[0-9 ()-]{7,30}$', required=False, max_length=30, label='WhatsApp number (optional)', widget=forms.TextInput(attrs={'type':'tel','autocomplete':'tel'}))
    whatsapp_consent = forms.BooleanField(required=False, label='You may contact me on WhatsApp about my interest.')
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    def clean(self):
        data = super().clean()
        if data.get('website'):
            raise ValidationError('Unable to submit. Please reload and try again.')
        if data.get('whatsapp') and not data.get('whatsapp_consent'):
            self.add_error('whatsapp_consent', 'Please allow WhatsApp contact or leave the number blank.')
        if data.get('whatsapp_consent') and not data.get('whatsapp'):
            self.add_error('whatsapp', 'Enter a number or clear the WhatsApp permission.')
        return data
    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

class SignupForm(ContactDetails):
    field_order = ['full_name','email','role','organisation','password1','password2','whatsapp','whatsapp_consent','consent','website']
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}), help_text='Use at least 8 characters. Avoid common passwords and personal details.')
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}))
    consent = forms.BooleanField(label='I agree to the use of my registration details, walkthrough activity and feedback for MVP evaluation, as described in the information notice.')
    def clean_email(self):
        email = super().clean_email()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError('Unable to register this email. Try logging in with your existing account.')
        return email
    def clean(self):
        data = super().clean()
        if data.get('password1') and data.get('password2') != data['password1']:
            self.add_error('password2', 'The passwords do not match.')
        if data.get('password1'):
            name = data.get('full_name', '').split(' ', 1)
            user = get_user_model()(email=data.get('email',''), first_name=name[0], last_name=name[-1])
            try:
                validate_password(data['password1'], user)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return data

class InterestForm(ContactDetails):
    interest = forms.ChoiceField(choices=[('', 'Choose your next step')] + [item for item in INTENTS if item[0] != 'None'])
    message = forms.CharField(max_length=3000, required=False, label='What would you like to explore? (optional)', widget=forms.Textarea(attrs={'rows':3}))
    consent = forms.BooleanField(label='I agree to be contacted about this enquiry and to the use of these details as described in the information notice.')

class FeedbackForm(forms.Form):
    def clean_barriers(self):
        values = list(dict.fromkeys(self.cleaned_data['barriers']))
        if len(values) > 3:
            raise ValidationError('Select no more than three adoption factors.')
        if 'Unsure' in values and len(values) > 1:
            raise ValidationError('Choose “Not sure yet” on its own, or select specific factors.')
        return values

    rating = forms.TypedChoiceField(coerce=int, choices=[(i, f'{i} '+('star' if i==1 else 'stars')) for i in range(1,6)], widget=forms.RadioSelect, label='How useful was this workflow?')
    most_useful = forms.ChoiceField(label='Which part was most useful?', choices=[('', 'Choose one')] + USEFUL_PARTS)
    barriers = forms.MultipleChoiceField(label='Which factors would most influence your decision to adopt this platform?', choices=ADOPTION_FACTORS, widget=forms.CheckboxSelectMultiple, help_text='Select up to three. Choose “Not sure yet” on its own.')
    suggestion = forms.CharField(label='What should we improve? (optional)', max_length=2000, required=False, widget=forms.Textarea(attrs={'rows':3}))
    intent = forms.ChoiceField(label='What would you like to do next?', choices=INTENTS, initial='None')
    contact_consent = forms.BooleanField(required=False, label='You may contact me by email about this next step.')
    def clean(self):
        data = super().clean()
        if data.get('intent') not in (None, 'None') and not data.get('contact_consent'):
            self.add_error('contact_consent', 'Please allow contact, or choose “No next step yet”.')
        return data

class LeadUpdateForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput)
    class Meta:
        model = Lead
        fields = ['stage', 'next_action', 'next_action_date']
        widgets = {'next_action_date': forms.DateInput(attrs={'type':'date'}), 'next_action': forms.Textarea(attrs={'rows':3})}
