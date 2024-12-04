from django import forms
from .models import Poem
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div

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
    class Meta:
        model = Poem
        fields = ['theme', 'mood', 'recipient']
        labels = {
            'theme': 'Onderwerp',
            'mood': 'Stemming',
            'recipient': 'Voor wie is het gedicht?',
        }
        widgets = {
            'theme': forms.TextInput(attrs={'placeholder': 'Bijv. speelgoed, avontuur...'}),
            'recipient': forms.TextInput(attrs={'placeholder': 'Voor wie is het gedicht?'}),
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
        if commit:
            instance.save()
        return instance
