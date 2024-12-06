import logging
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ValidationError
from .models import Poem
from .forms import PoemForm, SinterklaasPoemForm
from .utils import contains_blocked_content, retry_with_exponential_backoff
from openai import OpenAI

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Haal het IP-adres van de gebruiker op."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_openai_client():
    """
    Maak een OpenAI client aan met de nieuwe API-structuur.
    We gaan ervan uit dat settings.OPENAI_API_KEY correct is ingesteld.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError("OPENAI_API_KEY niet gevonden in settings.")

    # Verwijder de validatie van de API key.
    # We gaan er vanuit dat de gebruiker een geldige key heeft.
    client = OpenAI(api_key=api_key)
    return client

def test_openai_connection():
    """Test of de OpenAI API goed werkt via de nieuwe structuur."""
    try:
        client = get_openai_client()
        # Simpele test prompt
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'API connection successful'"}],
            max_tokens=10
        )
        # Als we hier komen is de connectie gelukt
        return True, "API connection successful"
    except Exception as e:
        logger.error(f"OpenAI test mislukt: {e}")
        return False, str(e)

class PoemCreateView(CreateView):
    model = Poem
    template_name = 'poems/create_poem.html'
    success_url = reverse_lazy('poem_create')

    @method_decorator(ratelimit(key='ip', rate='5/m', method=['POST']))
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        try:
            ip_address = get_client_ip(request)
            # Check rate limit
            if Poem.check_rate_limit(ip_address):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Je hebt het maximale aantal gedichten (2) voor vandaag bereikt. Probeer het morgen opnieuw.'
                }, status=429)

            data = request.POST.dict()
            # Check op ongepaste content
            for veld in ['theme', 'mood', 'recipient', 'excluded_words']:
                if contains_blocked_content(data.get(veld, '')):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Sorry, dit type inhoud is niet toegestaan.'
                    }, status=400)

            poem = Poem(
                theme=data.get('theme', ''),
                style=data.get('style', ''),
                mood=data.get('mood', ''),
                season=data.get('season', ''),
                length=data.get('length', ''),
                recipient=data.get('recipient', ''),
                excluded_words=data.get('excluded_words', ''),
                ip_address=ip_address
            )

            try:
                poem.generated_text = self._generate_poem_with_retry(data)
                poem.full_clean()
                poem.save()
                return JsonResponse({
                    'status': 'success',
                    'poem': poem.generated_text
                })
            except ValidationError as e:
                logger.error(f"Validatie fout: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
            except Exception as e:
                logger.error(f"Fout bij genereren gedicht: {e}")
                if 'rate limit' in str(e).lower():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Het systeem is momenteel erg druk. Probeer het over enkele minuten opnieuw.'
                    }, status=429)
                return JsonResponse({
                    'status': 'error',
                    'message': 'Er is een fout opgetreden bij het genereren van het gedicht.'
                }, status=500)
        except Exception as e:
            logger.error(f"Request fout: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'Ongeldige gegevens ingevoerd.'
            }, status=400)

    def get(self, request, *args, **kwargs):
        success, message = test_openai_connection()
        if not success:
            return JsonResponse({
                'status': 'error',
                'message': f'API Configuratie Fout: {message}'
            }, status=500)
        return render(request, self.template_name)

    @retry_with_exponential_backoff(max_retries=3, initial_wait=5)
    def _generate_poem_with_retry(self, data):
        """
        Genereer een gedicht met de nieuwe OpenAI API manier.
        """
        system_prompt = """Je bent een ervaren dichter die prachtige Nederlandse gedichten schrijft.
Je schrijft alleen familie-vriendelijke, gepaste gedichten.
Vermijd onder alle omstandigheden ongepaste, seksuele of expliciete inhoud.
Focus op positieve, opbouwende en inspirerende thema's.

Volg deze regels voor specifieke stijlen:
- Voor 'haiku': Schrijf precies 3 regels met 5-7-5 lettergrepen, vaak over natuur of seizoenen
- Voor 'limerick': Schrijf 5 regels met rijmschema aabba, humoristisch maar gepast
- Voor 'sonnet': Schrijf 14 regels met rijmschema abab cdcd efef gg
- Voor 'acrostichon': Zorg dat de eerste letters van elke regel het opgegeven thema of de naam van de ontvanger vormen
- Voor 'kinderlijk': Gebruik eenvoudige woorden en korte zinnen, maak het speels en begrijpelijk voor kinderen
- Voor 'rijmend': Zorg voor een duidelijk rijmschema door het hele gedicht
- Voor 'eenvoudig': Gebruik simpele taal die door iedereen begrepen kan worden
- Voor 'modern': Schrijf in vrije vorm zonder vaste regels
- Voor 'grappig': Maak het gedicht luchtig en humoristisch
- Voor 'romantisch': Focus op liefde en warme gevoelens
- Voor 'nostalgisch': Roep herinneringen en verlangen op
- Voor 'inspirerend': Maak het gedicht motiverend en positief
- Voor 'meditatief': Schrijf rustig en beschouwend"""

        prompt = f"Schrijf een gepast, familie-vriendelijk {data.get('style', 'rijmend')} gedicht"
        if data.get('theme'):
            prompt += f" over {data['theme']}"
        if data.get('recipient'):
            prompt += f" voor {data['recipient']}"
        if data.get('mood'):
            prompt += f" met een {data['mood']} stemming"
        if data.get('season'):
            prompt += f" passend bij het seizoen {data['season']}"
        if data.get('length'):
            prompt += f". Het gedicht moet {data['length']} lang zijn"
        if data.get('excluded_words'):
            prompt += f". Vermijd de volgende woorden in het gedicht: {data['excluded_words']}"
        prompt += ". Zorg ervoor dat de inhoud volledig gepast is voor alle leeftijden."

        client = get_openai_client()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )

        generated_text = completion.choices[0].message.content.strip()

        if contains_blocked_content(generated_text):
            raise ValueError("Gegenereerde inhoud bevat ongepaste termen")

        return generated_text

class SinterklaasPoemCreateView(CreateView):
    model = Poem
    form_class = SinterklaasPoemForm
    template_name = 'poems/create_sinterklaas_poem.html'
    success_url = reverse_lazy('sinterklaas_poem_create')

    @method_decorator(ratelimit(key='ip', rate='5/m', method=['POST']))
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            cleaned_data = form.cleaned_data

            for field in ['subject', 'mood', 'recipient', 'additional_info']:
                if contains_blocked_content(cleaned_data.get(field, '')):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Sorry, dit type inhoud is niet toegestaan.'
                    }, status=400)

            poem = form.save(commit=False)
            poem.theme = 'SINTERKLAAS'

            try:
                poem.generated_text = self._generate_poem_with_retry(cleaned_data)
                poem.full_clean()
                poem.save()
                return JsonResponse({
                    'status': 'success',
                    'poem': poem.generated_text
                })
            except ValidationError as e:
                logger.error(f"Validatie fout: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
            except Exception as e:
                logger.error(f"Fout bij genereren Sinterklaasgedicht: {e}")
                if 'rate limit' in str(e).lower():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Het systeem is momenteel erg druk. Probeer het over enkele minuten opnieuw.'
                    }, status=429)
                return JsonResponse({
                    'status': 'error',
                    'message': 'Er is een fout opgetreden bij het genereren van het Sinterklaasgedicht.'
                }, status=500)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Ongeldige gegevens ingevoerd.'
            }, status=400)

    @retry_with_exponential_backoff(max_retries=3, initial_wait=5)
    def _generate_poem_with_retry(self, data):
        system_prompt = """Je bent een ervaren Sinterklaas dichter die prachtige Nederlandse gedichten schrijft.
Je schrijft alleen familie-vriendelijke, gepaste gedichten.
Vermijd onder alle omstandigheden ongepaste, seksuele of expliciete inhoud.
Focus op positieve, opbouwende en inspirerende thema's.

Begin altijd met de regel: 'Sinterklaas zat eens te denken, wat hij jou zou schenken.'
Voeg humor en persoonlijke details toe waar mogelijk."""

        prompt = "Sinterklaas zat eens te denken, wat hij jou zou schenken."
        prompt += f" Dit gedicht is voor {data['recipient']}."
        prompt += f" Het onderwerp is {data['subject']} en de toon is {data['mood']}."
        if data.get('additional_info'):
            prompt += f" Extra context: {data['additional_info']}"

        client = get_openai_client()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )

        generated_text = completion.choices[0].message.content.strip()

        if contains_blocked_content(generated_text):
            raise ValueError("Gegenereerde inhoud bevat ongepaste termen")

        return generated_text
