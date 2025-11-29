from django import forms
from .models import Poem
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class PoemForm(forms.ModelForm):
    class Meta:
        model = Poem
        fields = ['theme', 'style', 'mood', 'season', 'length', 'recipient', 'excluded_words']
        labels = {
            'theme': 'Thema',
            'style': 'Stijl',
            'mood': 'Stemming',
            'season': 'Seizoen (optioneel)',
            'length': 'Lengte',
            'recipient': 'Voor wie is het gedicht? (optioneel)',
            'excluded_words': 'Woorden om te vermijden (optioneel, gescheiden door komma\'s)',
        }
        widgets = {
            'theme': forms.TextInput(attrs={'placeholder': 'Bijv: liefde, sinterklaas, vriendschap, kerst, verjaardag...'}),
            'recipient': forms.TextInput(attrs={'placeholder': 'Bijvoorbeeld: mijn moeder, Lisa, mijn beste vriend'}),
            'excluded_words': forms.Textarea(attrs={
                'rows': 2, 
                'placeholder': 'Bijvoorbeeld: roos, zee, zon (gescheiden door komma\'s)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('theme', css_class='form-control mb-3'),
                    Field('style', css_class='form-select mb-3'),
                    Field('mood', css_class='form-select mb-3'),
                    css_class='col-md-6'
                ),
                Div(
                    Field('season', css_class='form-select mb-3'),
                    Field('length', css_class='form-select mb-3'),
                    Field('recipient', css_class='form-control mb-3'),
                    css_class='col-md-6'
                ),
                css_class='row'
            ),
            Field('excluded_words', css_class='form-control mb-3'),
            Div(
                Submit('submit', 'Genereer Gedicht', css_class='btn btn-primary'),
                css_class='mb-3'
            )
        )

class SinterklaasPoemForm(forms.ModelForm):
    # Sinterklaas-specifieke mood choices (wijkt af van model)
    SINT_MOOD_CHOICES = [
        ('vrolijk', 'Vrolijk en speels'),
        ('grappig', 'Grappig met humor'),
        ('lief', 'Lief en hartelijk'),
        ('pesterig', 'Licht pesterig (vriendelijk)'),
    ]

    # Overschrijf mood met eigen choices
    mood = forms.ChoiceField(
        choices=SINT_MOOD_CHOICES,
        label='Stemming',
        widget=forms.Select()
    )

    # Extra veld dat niet in het model zit
    additional_info = forms.CharField(
        required=False,
        label='Extra informatie (optioneel)',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Bijv: Het cadeau is een boek over tuinieren, ze is altijd bezig in de tuin'
        })
    )

    class Meta:
        model = Poem
        fields = ['theme', 'recipient']  # mood handled separately
        labels = {
            'theme': 'Onderwerp / Thema',
            'recipient': 'Voor wie is het gedicht?',
        }
        widgets = {
            'theme': forms.TextInput(attrs={'placeholder': 'Bijv. voetbal, lezen, altijd te laat komen'}),
            'recipient': forms.TextInput(attrs={'placeholder': 'Bijv: Oma, kleine Tim, mijn collega Jan'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('theme', css_class='form-control mb-3'),
            Field('mood', css_class='form-select mb-3'),
            Field('recipient', css_class='form-control mb-3'),
            Div(
                Submit('submit', 'Genereer Sinterklaasgedicht', css_class='btn btn-primary'),
                css_class='mb-3'
            )
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.style = 'rijmend'  # Default style for Sinterklaas poems
        instance.length = 'medium'  # Default length
        instance.mood = self.cleaned_data.get('mood', 'vrolijk')  # Mood from form
        if commit:
            instance.save()
        return instance


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Voer een geldig e-mailadres in.")
    # Honeypot veld - als dit ingevuld is, is het een bot
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'autocomplete': 'off',
        'tabindex': '-1',
    }))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean(self):
        cleaned_data = super().clean()
        # Honeypot check - als website veld is ingevuld, is het een bot
        if cleaned_data.get('website'):
            raise forms.ValidationError("Spam gedetecteerd.")
        return cleaned_data