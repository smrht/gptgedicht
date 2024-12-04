from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Count
from datetime import timedelta

# Create your models here.

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

    # Required fields
    theme = models.CharField(max_length=200, help_text="Het thema van het gedicht")
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default='rijmend')
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default='vrolijk')
    
    # Optional fields
    season = models.CharField(max_length=10, choices=SEASON_CHOICES, default='', blank=True)
    length = models.CharField(max_length=10, choices=LENGTH_CHOICES, default='medium')
    recipient = models.CharField(max_length=200, blank=True, help_text="Voor wie is het gedicht bedoeld?")
    excluded_words = models.TextField(blank=True, help_text="Woorden die niet in het gedicht mogen voorkomen")
    
    # Generated content and metadata
    generated_text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(help_text="IP adres van de gebruiker")

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
    def check_rate_limit(cls, ip_address):
        """
        Check if the IP address has exceeded the rate limit.
        Returns True if the limit is exceeded, False otherwise.
        """
        time_threshold = timezone.now() - timedelta(days=1)  # Last 24 hours
        poems_count = cls.objects.filter(
            ip_address=ip_address,
            created_at__gte=time_threshold
        ).count()
        return poems_count >= 2  # Limit to 2 poems per IP per day

    def clean(self):
        """
        Validate that the IP address hasn't exceeded the rate limit
        """
        if self.ip_address and self.check_rate_limit(self.ip_address):
            raise ValidationError(
                'Je hebt het maximale aantal gedichten (2) voor vandaag bereikt. '
                'Probeer het morgen opnieuw.'
            )
