import hashlib
import json
from PIL import Image
from io import BytesIO
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.clinical.models import UltrasoundSample


class Command(BaseCommand):
    help = 'Import the four licensed, checksum-verified image-library assets.'

    @transaction.atomic
    def handle(self, *args, **options):
        base = settings.BASE_DIR / 'library_assets'
        entries = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
        for entry in entries:
            data = (base / entry['filename']).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise CommandError('Library image checksum mismatch; import stopped.')
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                if image.format not in ('PNG', 'BMP'):
                    raise CommandError('Unsupported image format.')
                image.verify()
            sample, _ = UltrasoundSample.objects.get_or_create(code=entry['code'], defaults={
                'label':entry['label'], 'filename':entry['filename'], 'byte_size':len(data),
                'width':width, 'height':height, 'sha256':entry['sha256'],
                'source_url':entry['source_url'], 'source_filename':entry['source_filename'],
                'attribution':entry['attribution'], 'licence_url':entry['licence_url'], 'licence_verified':True})
            if sample.sha256 != entry['sha256']:
                raise CommandError('An existing sample differs from the manifest; no overwrite performed.')
            if not sample.image or not sample.image.storage.exists(sample.image.name):
                sample.image.save(entry['filename'], ContentFile(data), save=True)
        self.stdout.write(self.style.SUCCESS('Licensed ultrasound sample library is available. Image pixels unchanged.'))
