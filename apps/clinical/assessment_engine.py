"""Deterministic workflow engine with source-derived annotations; no live inference."""
import hashlib
import json
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError

ENGINE_VERSION = 'demo-assessment-v1'
MIN_SIDE = 128  # Technical prototype policy, not a validated clinical threshold.
MAX_BYTES = 10 * 1024 * 1024


def profile_for(sample):
    path = settings.BASE_DIR / 'library_assets' / 'assessment_profiles.json'
    try:
        profiles = json.loads(path.read_text(encoding='utf-8'))
        profile = profiles[sample.code]
    except (OSError, ValueError, KeyError) as exc:
        raise ValidationError('An assessment profile is not available for this sample yet.') from exc
    if profile['image_sha256'] != sample.sha256:
        raise ValidationError('The sample does not match its assessment profile. Please contact the administrator.')
    return profile


def inspect_image(sample):
    checks = []
    def check(label, passed, detail):
        checks.append({'label':label, 'passed':passed, 'detail':detail})
    digest = ''
    try:
        with sample.image.open('rb') as handle:
            data = handle.read(MAX_BYTES + 1)
        digest = hashlib.sha256(data).hexdigest()
        check('File integrity', digest == sample.sha256 and len(data) == sample.byte_size,
              'The image matches the stored source file.' if digest == sample.sha256 else 'The image differs from its verified source file.')
        check('File size', 0 < len(data) <= MAX_BYTES, f'{len(data):,} bytes received; maximum supported size is 10 MB.')
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            supported = image.format in ('PNG', 'BMP')
            image.verify()
        check('Image decoding', supported, 'Image decoded successfully.' if supported else 'A supported PNG or BMP image is required.')
        check('Recorded dimensions', (width,height)==(sample.width,sample.height), f'{width} × {height} pixels.')
        enough = min(width, height) >= MIN_SIDE
        check('Review resolution', enough, f'{width} × {height} pixels; this workspace requires at least {MIN_SIDE} pixels on each side for detailed review.')
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        check('Image decoding', False, 'The image cannot be opened reliably. Please attach another image.')
    adequate = bool(checks) and all(c['passed'] for c in checks)
    reason = ('Technical checks passed. The image can proceed to assessment. Clinical adequacy still requires review of the full examination.' if adequate else
              'Assessment paused. The attached image does not meet the technical requirements for this workspace. Select a suitable image in a new assessment before continuing.')
    return {'adequate':adequate, 'reason':reason, 'checks':checks, 'image_sha256':digest,
            'sample_id':sample.pk, 'filename':sample.filename, 'policy':'technical-quality-v1', 'min_side':MIN_SIDE}


def generate_result(sample):
    profile = profile_for(sample)
    if profile.get('quality_only'):
        raise ValidationError('This sample is reserved for the image-quality pathway.')
    result = dict(profile)
    from apps.clinical.report_library import REPORT_VERSION
    result.update({'sample_id':sample.pk, 'sample_code':sample.code, 'filename':sample.filename, 'width':sample.width,
                   'height':sample.height, 'engine':ENGINE_VERSION, 'source_url':sample.source_url,
                   'report_version':REPORT_VERSION})
    for box in result.get('boxes', []):
        if (box['x'] < 0 or box['y'] < 0 or box['width'] <= 0 or box['height'] <= 0 or
            box['x']+box['width'] > sample.width or box['y']+box['height'] > sample.height):
            raise ValidationError('Source annotation falls outside the image bounds.')
    return result
