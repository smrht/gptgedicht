from django.db import models
from django.utils import timezone
from django.core.validators import URLValidator
from datetime import timedelta
import uuid


class BannerPosition(models.Model):
    """Beschikbare banner posities op de website."""
    
    POSITION_CHOICES = [
        ('sidebar', 'Sidebar Rechts'),
        ('below_content', 'Onder Content'),
        ('header', 'Tussen Nav en Content'),
        ('footer', 'Footer'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Naam')
    slug = models.SlugField(unique=True)
    position_type = models.CharField(
        max_length=20, 
        choices=POSITION_CHOICES,
        unique=True
    )
    width = models.PositiveIntegerField(verbose_name='Breedte (px)')
    height = models.PositiveIntegerField(verbose_name='Hoogte (px)')
    
    # Prijzen in euro's
    price_month = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Prijs per maand (€)'
    )
    price_quarter = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Prijs per kwartaal (€)'
    )
    price_year = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Prijs per jaar (€)'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='Actief')
    description = models.TextField(blank=True, verbose_name='Beschrijving')
    
    class Meta:
        verbose_name = 'Banner Positie'
        verbose_name_plural = 'Banner Posities'
        ordering = ['-price_month']
    
    def __str__(self):
        return f"{self.name} ({self.width}x{self.height})"
    
    def get_dimensions(self):
        return f"{self.width}x{self.height}"
    
    def has_active_banner(self):
        """Check of er een actieve banner is voor deze positie."""
        return self.purchases.filter(
            status='active',
            end_date__gte=timezone.now()
        ).exists()
    
    def get_active_banner(self):
        """Haal de actieve banner op voor deze positie."""
        purchase = self.purchases.filter(
            status='active',
            end_date__gte=timezone.now()
        ).first()
        return purchase.banner if purchase else None


class Banner(models.Model):
    """Geüploade banner afbeelding."""
    
    image = models.ImageField(upload_to='banners/', verbose_name='Afbeelding')
    alt_text = models.CharField(max_length=200, verbose_name='Alt tekst')
    destination_url = models.URLField(
        verbose_name='Bestemming URL',
        help_text='URL waar de banner naar linkt'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
    
    def __str__(self):
        return f"Banner: {self.alt_text[:50]}"


class BannerPurchase(models.Model):
    """Een banner aankoop/reservering."""
    
    PERIOD_CHOICES = [
        ('month', '1 Maand'),
        ('quarter', '3 Maanden'),
        ('year', '1 Jaar'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'In afwachting van betaling'),
        ('active', 'Actief'),
        ('expired', 'Verlopen'),
        ('cancelled', 'Geannuleerd'),
    ]
    
    # Unieke ID voor de purchase
    purchase_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Relaties
    position = models.ForeignKey(
        BannerPosition, 
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name='Positie'
    )
    banner = models.ForeignKey(
        Banner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Banner'
    )
    
    # Periode en prijs
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    price_paid = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Betaald bedrag (€)'
    )
    
    # Datums
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Status en betaling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_session_id = models.CharField(max_length=200, blank=True)
    stripe_payment_intent = models.CharField(max_length=200, blank=True)
    
    # Contact gegevens
    buyer_email = models.EmailField(verbose_name='E-mailadres koper')
    buyer_name = models.CharField(max_length=200, blank=True, verbose_name='Naam koper')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Bedrijfsnaam')
    
    class Meta:
        verbose_name = 'Banner Aankoop'
        verbose_name_plural = 'Banner Aankopen'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.position.name} - {self.get_period_display()} ({self.status})"
    
    def activate(self):
        """Activeer de banner na succesvolle betaling."""
        self.status = 'active'
        self.start_date = timezone.now()
        
        if self.period == 'month':
            self.end_date = self.start_date + timedelta(days=30)
        elif self.period == 'quarter':
            self.end_date = self.start_date + timedelta(days=90)
        elif self.period == 'year':
            self.end_date = self.start_date + timedelta(days=365)
        
        self.save()
    
    def is_expired(self):
        """Check of de banner is verlopen."""
        if self.end_date and self.status == 'active':
            return timezone.now() > self.end_date
        return False
    
    def days_remaining(self):
        """Bereken het aantal resterende dagen."""
        if self.end_date and self.status == 'active':
            remaining = self.end_date - timezone.now()
            return max(0, remaining.days)
        return 0
