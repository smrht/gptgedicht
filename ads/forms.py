from django import forms
from django.core.exceptions import ValidationError
from PIL import Image
from .models import Banner, BannerPurchase, BannerPosition


class BannerUploadForm(forms.ModelForm):
    """Form voor het uploaden van een banner afbeelding."""
    
    class Meta:
        model = Banner
        fields = ['image', 'alt_text', 'destination_url']
        widgets = {
            'alt_text': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Korte beschrijving van je banner'
            }),
            'destination_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'https://jouwwebsite.nl'
            }),
            'image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/png,image/jpeg,image/gif,image/webp',
                'id': 'banner-upload'
            }),
        }
    
    def __init__(self, *args, position=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.position = position
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            raise ValidationError('Upload een afbeelding.')
        
        # Check bestandsgrootte (max 2MB)
        if image.size > 2 * 1024 * 1024:
            raise ValidationError('Afbeelding mag maximaal 2MB zijn.')
        
        # Check afmetingen als positie bekend is
        if self.position:
            try:
                img = Image.open(image)
                width, height = img.size
                
                if width != self.position.width or height != self.position.height:
                    raise ValidationError(
                        f'Afbeelding moet exact {self.position.width}x{self.position.height} '
                        f'pixels zijn. Jouw afbeelding is {width}x{height} pixels.'
                    )
            except Exception as e:
                if 'pixels' in str(e):
                    raise
                raise ValidationError('Kon afbeelding niet verwerken. Upload een geldig bestand.')
        
        return image


class BannerPurchaseForm(forms.Form):
    """Form voor het kiezen van periode en invullen contactgegevens."""
    
    PERIOD_CHOICES = [
        ('month', '1 Maand'),
        ('quarter', '3 Maanden (-12%)'),
        ('year', '1 Jaar (-24%)'),
    ]
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'hidden peer'}),
        initial='month'
    )
    
    buyer_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'jouw@email.nl'
        }),
        label='E-mailadres'
    )
    
    buyer_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'Je naam (optioneel)'
        }),
        label='Naam'
    )
    
    company_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'Bedrijfsnaam (optioneel)'
        }),
        label='Bedrijfsnaam'
    )
