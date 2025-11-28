# Generated migration for ads app

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Banner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='banners/', verbose_name='Afbeelding')),
                ('alt_text', models.CharField(max_length=200, verbose_name='Alt tekst')),
                ('destination_url', models.URLField(help_text='URL waar de banner naar linkt', verbose_name='Bestemming URL')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Banner',
                'verbose_name_plural': 'Banners',
            },
        ),
        migrations.CreateModel(
            name='BannerPosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Naam')),
                ('slug', models.SlugField(unique=True)),
                ('position_type', models.CharField(choices=[('sidebar', 'Sidebar Rechts'), ('below_content', 'Onder Content'), ('header', 'Tussen Nav en Content'), ('footer', 'Footer')], max_length=20, unique=True)),
                ('width', models.PositiveIntegerField(verbose_name='Breedte (px)')),
                ('height', models.PositiveIntegerField(verbose_name='Hoogte (px)')),
                ('price_month', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Prijs per maand (€)')),
                ('price_quarter', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Prijs per kwartaal (€)')),
                ('price_year', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Prijs per jaar (€)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actief')),
                ('description', models.TextField(blank=True, verbose_name='Beschrijving')),
            ],
            options={
                'verbose_name': 'Banner Positie',
                'verbose_name_plural': 'Banner Posities',
                'ordering': ['-price_month'],
            },
        ),
        migrations.CreateModel(
            name='BannerPurchase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purchase_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('period', models.CharField(choices=[('month', '1 Maand'), ('quarter', '3 Maanden'), ('year', '1 Jaar')], max_length=10)),
                ('price_paid', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Betaald bedrag (€)')),
                ('start_date', models.DateTimeField(blank=True, null=True)),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('pending', 'In afwachting van betaling'), ('active', 'Actief'), ('expired', 'Verlopen'), ('cancelled', 'Geannuleerd')], default='pending', max_length=20)),
                ('stripe_session_id', models.CharField(blank=True, max_length=200)),
                ('stripe_payment_intent', models.CharField(blank=True, max_length=200)),
                ('buyer_email', models.EmailField(max_length=254, verbose_name='E-mailadres koper')),
                ('buyer_name', models.CharField(blank=True, max_length=200, verbose_name='Naam koper')),
                ('company_name', models.CharField(blank=True, max_length=200, verbose_name='Bedrijfsnaam')),
                ('banner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ads.banner', verbose_name='Banner')),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='purchases', to='ads.bannerposition', verbose_name='Positie')),
            ],
            options={
                'verbose_name': 'Banner Aankoop',
                'verbose_name_plural': 'Banner Aankopen',
                'ordering': ['-created_at'],
            },
        ),
    ]
