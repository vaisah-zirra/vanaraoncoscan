import json
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from apps.clinical.report_library import REPORTS, BIRADS, SIGNALS, report_for_code
from apps.clinical.presentation import SAMPLE_DISPLAYS
from tests import test_assessment as base

PROFILES = json.loads((settings.BASE_DIR / 'library_assets/assessment_profiles.json').read_text(encoding='utf-8'))
# BI-RADS categories that are consistent with each workflow disposition.
ALLOWED = {'NON_SUSPICIOUS': {'1', '2', '3'}, 'UNCERTAIN': {'0'}, 'SUSPICIOUS': {'4A', '4B', '4C', '5'}}


class ReportLibraryTests(SimpleTestCase):
    def test_every_assessable_sample_has_a_consistent_report(self):
        for code, profile in PROFILES.items():
            if profile.get('quality_only'):
                self.assertNotIn(code, REPORTS)
                continue
            report = report_for_code(code)
            self.assertIsNotNone(report, code)
            category = report['birads']['category']
            self.assertIn(category, BIRADS)
            self.assertIn(category, ALLOWED[profile['disposition']], code)
            self.assertIn('BI-RADS ' + category, profile['impression'], code)
            self.assertEqual(len(report['lesions']), len(profile['boxes']), code)
            for lesion, box in zip(report['lesions'], profile['boxes']):
                self.assertEqual(len(lesion['descriptors']), 7)
                self.assertTrue(all(d['signal'] in SIGNALS for d in lesion['descriptors']))
                self.assertEqual(sum(lesion['counts'].values()), 7)
            if profile['boxes']:
                m = REPORTS[code]['morphometrics']
                self.assertEqual((m['width_px'], m['height_px']), (box['width'], box['height']), code)
            self.assertTrue(report['impression'] and report['recommendations'] and report['reasoning'] and report['patient_summary'])

    def test_low_confidence_sample_is_provisional_and_below_threshold(self):
        report = report_for_code('sample-04')
        self.assertTrue(report['birads']['provisional'])
        self.assertLess(SAMPLE_DISPLAYS['sample-04'][1], report['threshold'])
        for code in ('sample-01', 'sample-02', 'sample-03', 'sample-05'):
            self.assertGreaterEqual(SAMPLE_DISPLAYS[code][1], report_for_code(code)['threshold'])

    def test_suspicious_report_recommends_tissue_diagnosis(self):
        report = report_for_code('sample-05')
        self.assertEqual(report['birads']['category'], '5')
        self.assertTrue(any('biopsy' in line.lower() for line in report['recommendations']))
        self.assertGreaterEqual(report['lesions'][0]['counts']['suspicious'], 4)


class StructuredReportViewTests(TestCase):
    setUp = base.AssessmentTests.setUp
    attach = base.AssessmentTests.attach
    quality = base.AssessmentTests.quality
    assess = base.AssessmentTests.assess

    def test_result_page_and_pdf_include_structured_report(self):
        sample = self.attach('sample-05'); self.quality(sample); assessment = self.assess(sample)
        self.assertEqual(assessment.details['sample_code'], 'sample-05')
        response = self.client.get(reverse('assessment-result', args=[self.case.pk]))
        self.assertContains(response, 'Clinical interpretation')
        self.assertContains(response, 'Highly suggestive of malignancy')
        self.assertContains(response, 'Lesion 1 · BI-RADS 5')
        self.assertContains(response, 'Differential diagnosis')
        review = self.client.get(reverse('clinician-review', args=[self.case.pk]))
        self.assertContains(review, 'AI report: BI-RADS 5')
        pdf = self.client.get(reverse('case-report', args=[self.case.pk]))
        self.assertEqual(pdf.status_code, 200)
        from pypdf import PdfReader
        from io import BytesIO
        text = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        self.assertIn('Structured ultrasound report', text)
        self.assertIn('Differential diagnosis', text)

    def test_normal_sample_reports_bi_rads_1_without_lesion_table(self):
        sample = self.attach('sample-02'); self.quality(sample); self.assess(sample)
        response = self.client.get(reverse('assessment-result', args=[self.case.pk]))
        self.assertContains(response, 'Negative')
        self.assertNotContains(response, 'Lexicon feature')

    def test_quality_failure_has_no_structured_report(self):
        sample = self.attach('sample-06'); quality = self.quality(sample)
        self.assertFalse(quality.adequate)
        response = self.client.get(reverse('case-detail', args=[self.case.pk]))
        self.assertNotContains(response, 'STRUCTURED ULTRASOUND REPORT')
