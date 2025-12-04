from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap voor statische pagina's"""
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            'poem_create',
            'sinterklaas_poem_create',
            'valentijn_poem_create',
            'about',
            'privacy',
            'terms',
            'contact',
            'signup',
            'login',
        ]

    def location(self, item):
        return reverse(item)


class HomeSitemap(Sitemap):
    """Sitemap voor homepage met hogere prioriteit"""
    priority = 1.0
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return ['poem_create']

    def location(self, item):
        return reverse(item)
