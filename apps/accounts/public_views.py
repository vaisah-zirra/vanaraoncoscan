import time
from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from .models import ContactEnquiry

INTERESTS = [('','Select your interest'),('Practice','Practice subscription'),('Clinic','Clinic subscription'),('Network','Network subscription'),('Partnership','Partnership or research'),('General','General enquiry'),('Demo','Guided demonstration'),('Pilot','Pilot / waitlist'),('Pricing','Pricing discussion'),('Deployment','Deployment discussion')]
class ContactForm(forms.Form):
    name = forms.CharField(label='Your name', max_length=120, widget=forms.TextInput(attrs={'autocomplete':'name','placeholder':'Full name'}))
    email = forms.EmailField(label='Email address', max_length=254, widget=forms.EmailInput(attrs={'autocomplete':'email','placeholder':'you@organisation.com'}))
    organisation = forms.CharField(label='Organisation (optional)', max_length=180, required=False, widget=forms.TextInput(attrs={'autocomplete':'organization','placeholder':'Clinic, practice or organisation'}))
    interest = forms.ChoiceField(label='I’m interested in', choices=INTERESTS)
    message = forms.CharField(label='How can we help?', max_length=3000, widget=forms.Textarea(attrs={'rows':4,'placeholder':'Tell us about your team and what you would like to explore.'}))
    consent = forms.BooleanField(label='I agree to be contacted about this enquiry.')
    website = forms.CharField(required=False, widget=forms.HiddenInput)

@never_cache
@require_http_methods(['GET','POST'])
def landing(request):
    selected=request.GET.get('interest','')
    if selected not in dict(INTERESTS): selected=''
    form=ContactForm(request.POST if request.method=='POST' else None,initial={'interest':selected})
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data['website']:
            form.add_error(None,'Your message could not be submitted. Please reload the page and try again.')
        elif time.time()-request.session.get('last_enquiry_at',0)<60:
            form.add_error(None,'Please wait a minute before sending another enquiry.')
        else:
            values={key:form.cleaned_data[key] for key in ['name','email','organisation','interest','message','consent']}
            enquiry = ContactEnquiry.objects.create(**values)
            from apps.validation.services import lead_from_enquiry
            lead_from_enquiry(request, enquiry)
            request.session['last_enquiry_at']=time.time()
            request.session['enquiry_received']=True
            return redirect(reverse('landing')+'#contact')
    received=request.session.pop('enquiry_received',False) if request.method=='GET' else False
    response=render(request,'landing.html',{'contact_form':form,'received':received})
    return response
