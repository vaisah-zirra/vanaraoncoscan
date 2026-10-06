"""Discovery endpoints for the public marketing homepage."""
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def robots(request):
    return HttpResponse(
        'User-agent: *\nAllow: /\n'
        'Sitemap: https://vanaraoncoscan.cyou/sitemap.xml\n',
        content_type='text/plain',
    )


@require_safe
def sitemap(request):
    # Only the marketing homepage belongs in search, never case or account URLs.
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://vanaraoncoscan.cyou/</loc></url></urlset>',
        content_type='application/xml',
    )
