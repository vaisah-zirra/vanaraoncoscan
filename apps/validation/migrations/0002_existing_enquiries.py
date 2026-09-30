from django.db import migrations

def import_enquiries(apps, schema_editor):
    Enquiry = apps.get_model('accounts', 'ContactEnquiry')
    Lead = apps.get_model('validation', 'Lead')
    for enquiry in Enquiry.objects.filter(consent=True).iterator():
        Lead.objects.get_or_create(enquiry_id=enquiry.pk, defaults={'name':enquiry.name,'email':enquiry.email,
            'organisation':enquiry.organisation,'interest':enquiry.interest,'message':enquiry.message,
            'contact_consent_at':enquiry.created_at,'source':'legacy','stage':'Contacted' if enquiry.handled else 'New'})

class Migration(migrations.Migration):
    dependencies = [('validation','0001_initial')]
    operations = [migrations.RunPython(import_enquiries, migrations.RunPython.noop)]
