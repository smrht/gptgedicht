# Data migration to create initial banner positions

from django.db import migrations


def create_initial_positions(apps, schema_editor):
    BannerPosition = apps.get_model('ads', 'BannerPosition')
    
    positions = [
        {
            'name': 'Sidebar Premium',
            'slug': 'sidebar-premium',
            'position_type': 'sidebar',
            'width': 300,
            'height': 250,
            'price_month': 49.00,
            'price_quarter': 129.00,
            'price_year': 449.00,
            'description': 'Prominente positie in de sidebar. Zichtbaar op alle pagina\'s.',
            'is_active': True,
        },
        {
            'name': 'Onder Content',
            'slug': 'onder-content',
            'position_type': 'below_content',
            'width': 728,
            'height': 90,
            'price_month': 39.00,
            'price_quarter': 99.00,
            'price_year': 349.00,
            'description': 'Leaderboard banner direct onder de gegenereerde gedichten.',
            'is_active': True,
        },
        {
            'name': 'Header Banner',
            'slug': 'header-banner',
            'position_type': 'header',
            'width': 728,
            'height': 90,
            'price_month': 39.00,
            'price_quarter': 99.00,
            'price_year': 349.00,
            'description': 'Leaderboard banner tussen navigatie en content.',
            'is_active': True,
        },
        {
            'name': 'Footer Banner',
            'slug': 'footer-banner',
            'position_type': 'footer',
            'width': 728,
            'height': 90,
            'price_month': 29.00,
            'price_quarter': 69.00,
            'price_year': 249.00,
            'description': 'Leaderboard banner in de footer van de website.',
            'is_active': True,
        },
    ]
    
    for pos_data in positions:
        BannerPosition.objects.create(**pos_data)


def remove_initial_positions(apps, schema_editor):
    BannerPosition = apps.get_model('ads', 'BannerPosition')
    BannerPosition.objects.filter(
        slug__in=['sidebar-premium', 'onder-content', 'header-banner', 'footer-banner']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ads', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_positions, remove_initial_positions),
    ]
