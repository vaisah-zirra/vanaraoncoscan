from django.db import migrations

def preserve_history(apps, schema_editor):
    Lead = apps.get_model('validation', 'Lead')
    for lead in Lead.objects.filter(source='legacy', enquiry__isnull=False).select_related('enquiry').iterator():
        values = {'created_at':lead.enquiry.created_at}
        # "Handled" in the old inbox is not evidence that contact occurred.
        if lead.enquiry.handled and not lead.updates.exists():
            values.update(stage='New',next_action='Imported enquiry previously marked handled. Review and set its current stage.')
        Lead.objects.filter(pk=lead.pk).update(**values)

class Migration(migrations.Migration):
    dependencies = [('validation','0002_existing_enquiries')]
    operations = [migrations.RunPython(preserve_history, migrations.RunPython.noop)]
