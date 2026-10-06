from xml.etree import ElementTree
from django.test import TestCase
from django.contrib.staticfiles import finders
from PIL import Image


class SearchAndSharingTests(TestCase):
    def test_home_sharing_metadata(self):
        response = self.client.get('/')
        self.assertContains(response, 'rel="canonical" href="https://vanaraoncoscan.cyou/"')
        self.assertContains(response, 'property="og:image" content="https://vanaraoncoscan.cyou/static/brand/social-preview-v1.jpg"')
        with Image.open(finders.find('brand/social-preview-v1.jpg')) as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, 'JPEG')

    def test_discovery_endpoints_are_public_and_exclude_private_records(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sitemap: https://vanaraoncoscan.cyou/sitemap.xml')
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        tree = ElementTree.fromstring(response.content)
        self.assertEqual([node.text for node in tree.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')], ['https://vanaraoncoscan.cyou/'])
