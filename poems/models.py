from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    credits = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Poem(models.Model):
    STYLE_CHOICES = [
        ('eenvoudig', 'Eenvoudig (makkelijk te begrijpen)'),
        ('modern', 'Modern en vrij'),
        ('rijmend', 'Rijmend (traditioneel met rijm)'),
        ('kinderlijk', 'Kinderlijk (speels en simpel)'),
        ('grappig', 'Grappig (met humor)'),
        ('haiku', 'Haiku (3 regels: 5-7-5 lettergrepen)'),
        ('limerick', 'Limerick (5 grappige rijmende regels)'),
        ('sonnet', 'Sonnet (14 regels met vast rijmschema)'),
        ('acrostichon', 'Acrostichon (eerste letters vormen een woord)'),
        ('romantisch', 'Romantisch (liefdevol en warm)'),
        ('nostalgisch', 'Nostalgisch (herinneringen)'),
        ('inspirerend', 'Inspirerend (motiverend)'),
        ('meditatief', 'Meditatief (rustig en beschouwend)'),
    ]

    MOOD_CHOICES = [
        ('vrolijk', 'Vrolijk'),
        ('melancholisch', 'Melancholisch'),
        ('romantisch', 'Romantisch'),
        ('inspirerend', 'Inspirerend'),
        ('rustig', 'Rustig'),
    ]

    SEASON_CHOICES = [
        ('', 'Geen specifiek seizoen'),
        ('lente', 'Lente'),
        ('zomer', 'Zomer'),
        ('herfst', 'Herfst'),
        ('winter', 'Winter'),
    ]

    LENGTH_CHOICES = [
        ('kort', 'Kort'),
        ('medium', 'Gemiddeld'),
        ('lang', 'Lang'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    theme = models.CharField(max_length=200, help_text="Het thema van het gedicht")
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default='rijmend')
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default='vrolijk')
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, default='', blank=True)
    length = models.CharField(max_length=10, choices=LENGTH_CHOICES, default='medium')
    recipient = models.CharField(max_length=200, blank=True, help_text="Voor wie is het gedicht bedoeld?")
    excluded_words = models.TextField(blank=True, help_text="Woorden die niet in het gedicht mogen voorkomen")
    generated_text = models.TextField()
    image_url = models.URLField(blank=True, null=True, help_text="Optionele illustratie bij het gedicht")
    created_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(help_text="IP adres van de gebruiker", default='127.0.0.1')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gedicht'
        verbose_name_plural = 'Gedichten'

    def __str__(self):
        base = f"Gedicht over {self.theme}"
        if self.recipient:
            base += f" voor {self.recipient}"
        return f"{base} ({self.created_at.strftime('%d-%m-%Y')})"

    @classmethod
    def check_rate_limit(cls, ip_address, user=None):
        # Als de gebruiker ingelogd is, kunnen we voor de gratis limiet per maand checken.
        # Anders, per week op IP-basis.
        if user and user.is_authenticated:
            # Gratis limiet per maand voor ingelogde gebruikers
            now = timezone.now()
            month = now.month
            year = now.year
            poems_count = cls.objects.filter(user=user, created_at__month=month, created_at__year=year).count()
            return poems_count >= 2
        else:
            # Anonieme gebruikers: wekelijks limiet op IP
            time_threshold = timezone.now() - timedelta(days=7)
            poems_count = cls.objects.filter(
                ip_address=ip_address,
                created_at__gte=time_threshold
            ).count()
            return poems_count >= 2

    def clean(self):
        # Gebruikerslimiet checken
        if self.user and self.user.is_authenticated:
            # Als gebruiker al >2 in deze maand heeft gemaakt en geen credits heeft
            if Poem.check_rate_limit(ip_address=self.ip_address, user=self.user) and self.user.profile.credits < 1:
                raise ValidationError(
                    'Je hebt het maximale aantal gratis gedichten (2) voor deze maand bereikt. Koop credits om meer te genereren.'
                )
        else:
            # Anonieme gebruikers check:
            if Poem.check_rate_limit(ip_address=self.ip_address):
                raise ValidationError(
                    'Je hebt het maximale aantal gedichten (2) voor vandaag bereikt. '
                    'Maak een account en koop credits om meer te genereren.'
                )
