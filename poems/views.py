import logging
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import CreateView, View
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.exceptions import ValidationError
from pydantic import BaseModel
from .models import Poem, Profile
from .forms import PoemForm, SinterklaasPoemForm
from .utils import contains_blocked_content, retry_with_exponential_backoff
from openai import OpenAI
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
import stripe
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login

from .forms import SignupForm
from .models import Poem, Profile
from django.conf import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class PoemSchema(BaseModel):
    title: str
    verses: list[str]

def get_client_ip(request):
    """Haal het IP-adres van de gebruiker op."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_openai_client():
    """
    Maak een OpenAI client aan.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError("OPENAI_API_KEY niet gevonden in settings.")
    client = OpenAI(api_key=api_key)
    return client

def test_openai_connection():
    """Test of de OpenAI API goed werkt."""
    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say 'API connection successful'"}],
            max_tokens=10
        )
        return True, "API connection successful"
    except Exception as e:
        logger.error(f"OpenAI test mislukt: {e}")
        return False, str(e)

def beschrijf_stijl_op_basis_van_de_user_input(data):
    style = data.get('style', 'rijmend')
    # Voeg hier per stijl duidelijke instructies toe
    if style == 'haiku':
        return "Gebruik de haikuvorm: 3 regels met 5-7-5 lettergrepen, vaak geïnspireerd door de natuur."
    elif style == 'limerick':
        return "Gebruik de limerickvorm: 5 regels met rijmschema aabba, humoristisch van toon."
    elif style == 'sonnet':
        return "Gebruik een sonnetvorm: 14 regels met rijmschema abab cdcd efef gg, vaak over liefde of natuur."
    elif style == 'acrostichon':
        return "Maak een acrostichon: de eerste letters van elke regel vormen samen een woord (bijv. het thema)."
    elif style == 'kinderlijk':
        return "Maak het gedicht kinderlijk: eenvoudige woorden, speels, makkelijk te begrijpen."
    elif style == 'grappig':
        return "Maak het gedicht grappig: luchtige toon, humoristische elementen."
    elif style == 'romantisch':
        return "Maak het gedicht romantisch: focus op liefde, warme gevoelens."
    elif style == 'nostalgisch':
        return "Maak het gedicht nostalgisch: roep herinneringen en verlangen naar vroeger op."
    elif style == 'inspirerend':
        return "Maak het gedicht inspirerend: motiverend, positief, opbeurend."
    elif style == 'meditatief':
        return "Maak het gedicht meditatief: rustig, beschouwend, zet aan tot nadenken."
    elif style == 'modern':
        return "Maak het gedicht modern: vrije vorm, geen vast rijmschema, hedendaagse thema's."
    elif style == 'eenvoudig':
        return "Maak het gedicht eenvoudig: simpele taal, door iedereen te begrijpen."
    elif style == 'rijmend':
        return "Maak het gedicht rijmend: traditioneel met een duidelijk hoorbaar rijmschema."
    # Als er geen specifieke stijl wordt gevonden, default naar rijmend
    return "Gebruik een passende stijl bij het gekozen thema en stemming, met duidelijke vorm."

@retry_with_exponential_backoff(max_retries=3, initial_wait=5)
def _process_user_input(data):
    """
    Verwerk gebruikersinvoer tot gestructureerde instructies.
    """
    client = get_openai_client()
    user_input = f"""
    Thema: {data.get('theme', '')}
    Stijl: {data.get('style', 'rijmend')}
    Mood: {data.get('mood', '')}
    Ontvanger: {data.get('recipient', '')}
    Seizoen: {data.get('season', '')}
    Lengte: {data.get('length', '')}
    Uit te sluiten woorden: {data.get('excluded_words', '')}
    """

    system_prompt = """Je bent een planner die op basis van gebruikersinvoer een duidelijke instructie maakt om een perfect gedicht te schrijven.
Specificeer minimaal:
 - een rijmschema of geef aan als er geen vast schema is (afh. van stijl)
 - aantal strofen of regels
 - toon (afhankelijk van mood of stijl)
 - thema
 - eventueel extra instructies

Output in exact JSON formaat:
{
 "rijmschema": "aabb",
 "aantal_strofen": 4,
 "toon": "speels",
 "thema": "...",
 "excluded_words": "...",
 "extra_instructies": "..."
}
Zorg dat de output strikt valide JSON is, zonder extra tekst.
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    structured_input = json.loads(completion.choices[0].message.content)
    return structured_input

def _bepaal_aantal_strofen_op_basis_van_lengte(data):
    length = data.get('length', 'medium')
    if length == 'kort':
        return 4
    elif length == 'lang':
        return 12
    return 8

def _generate_poem_prompt(structured_input, data):
    aantal_strofen = _bepaal_aantal_strofen_op_basis_van_lengte(data)
    style_instructies = beschrijf_stijl_op_basis_van_de_user_input(data)
    excluded_words = structured_input.get('excluded_words', '')
    if excluded_words.strip():
        excluded_text = f"Gebruik onder geen beding de volgende woorden: {excluded_words}. Als een woord zou rijmen maar staat in deze lijst, kies een alternatief."
    else:
        excluded_text = "Geen uitgesloten woorden specifiek."

    prompt = f"""
Schrijf een Nederlands gedicht over het thema: {structured_input.get('thema', '')}.
Toon: {structured_input.get('toon', 'neutraal')}.
Rijmschema: {structured_input.get('rijmschema', 'aabb')}.
Aantal strofen: {aantal_strofen}.
Stemming: {data.get('mood', '')}.
Ontvanger: {data.get('recipient', '')}.
Seizoen: {data.get('season', '')}.
{excluded_text}

{style_instructies}

Extra instructies: {structured_input.get('extra_instructies', '')}

Geef je antwoord uitsluitend in onderstaand JSON-formaat zonder extra tekst:
{{
  "title": "<Titel van het gedicht>",
  "verses": [
    "<vers 1>",
    "<vers 2>",
    ...
  ]
}}

Zorg ervoor dat het duidelijk hoorbaar rijmt indien een rijmschema is opgegeven, dat het familie-vriendelijk is, en volledig aansluit bij de gekozen stijl en mood.
""".strip()
    return prompt

@retry_with_exponential_backoff(max_retries=3, initial_wait=5)
def _generate_draft_poem(poem_prompt):
    client = get_openai_client()
    system_prompt = """Je bent een Nederlandse dichter die perfect kan voldoen aan bovenstaande instructies.
Je geeft het antwoord uitsluitend in het JSON-formaat zoals gevraagd.
"""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": poem_prompt}
        ],
        temperature=0.7,
        max_tokens=1500,
        response_format=PoemSchema
    )
    poem_draft = completion.choices[0].message.parsed
    return poem_draft

@retry_with_exponential_backoff(max_retries=3, initial_wait=5)
def _check_and_fix_rhyme(poem_draft, structured_input, data):
    client = get_openai_client()
    check_prompt = f"""
Dit is het gedicht dat je hebt gemaakt (in JSON):
{poem_draft.json()}

Rijmschema: {structured_input.get('rijmschema', 'aabb')}

Controleer of elke strofe het juiste rijmschema volgt (indien opgegeven). Als er regels niet rijmen of niet passen bij de instructies, herschrijf alleen die specifieke versregels.
Behoud dezelfde titel, thema en stijl. Hou rekening met uitgesloten woorden: {structured_input.get('excluded_words','')}

Antwoord opnieuw in exact hetzelfde JSON-formaat (title, verses) zonder extra tekst.
"""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content":"Je bent een strenge redacteur die erop let dat elk gedicht perfect voldoet aan het schema en instructies."},
            {"role": "user", "content": check_prompt}
        ],
        temperature=0.5,
        max_tokens=1500,
        response_format=PoemSchema
    )
    final_poem = completion.choices[0].message.parsed
    return final_poem

class PoemCreateView(View):
    template_name = 'poems/create_poem.html'

    def get(self, request, *args, **kwargs):
        # Render de HTML pagina met het formulier
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        try:
            # Lees JSON data
            body = request.body.decode('utf-8')
            data = json.loads(body)

            ip_address = get_client_ip(request)
            user = request.user if request.user.is_authenticated else None

            # Check gratis limiet
            now = timezone.now()
            if user and user.is_authenticated:
                # Limiet per maand
                poem_count = Poem.objects.filter(user=user, created_at__year=now.year, created_at__month=now.month).count()
                if poem_count >= 2:
                    # Check of er credits zijn
                    if user.profile.credits < 1:
                        return JsonResponse({'status': 'error', 'message': 'Je hebt je gratis maandlimiet bereikt. Koop credits om meer gedichten te genereren.'}, status=402)
                    # Trek 1 credit af als straks opslaan slaagt.
            else:
                # Anoniem: limit per dag (24 uur)
                past_24h = now - timedelta(days=1)
                poems_count = Poem.objects.filter(ip_address=ip_address, created_at__gte=past_24h).count()
                if poems_count >= 2:
                    return JsonResponse({'status': 'error', 'message': 'Je hebt het maximale aantal gedichten (2) voor vandaag bereikt. Maak een account en koop credits om meer te genereren.'}, status=429)

            # Genereer het gedicht
            structured_input = _process_user_input(data)
            poem_prompt = _generate_poem_prompt(structured_input, data)
            poem_draft = _generate_draft_poem(poem_prompt)

            combined_text = poem_draft.title + " " + " ".join(poem_draft.verses)
            if contains_blocked_content(combined_text):
                return JsonResponse({'status': 'error', 'message': 'Gegenereerde inhoud bevat ongepaste termen'}, status=400)

            final_poem = _check_and_fix_rhyme(poem_draft, structured_input, data)
            combined_text_final = final_poem.title + " " + " ".join(final_poem.verses)
            if contains_blocked_content(combined_text_final):
                return JsonResponse({'status': 'error', 'message': 'Gegenereerde inhoud bevat ongepaste termen'}, status=400)

            # Gedicht opslaan in de database
            poem = Poem(
                theme=data.get('theme', ''),
                style=data.get('style', ''),
                mood=data.get('mood', ''),
                season=data.get('season', ''),
                length=data.get('length', ''),
                recipient=data.get('recipient', ''),
                excluded_words=data.get('excluded_words', ''),
                generated_text=json.dumps(final_poem.dict(), ensure_ascii=False),
                ip_address=ip_address,
                created_at=now
            )

            if user and user.is_authenticated:
                poem.user = user
                # Trek 1 credit af als user al over limiet is
                poem_count = Poem.objects.filter(user=user, created_at__year=now.year, created_at__month=now.month).count()
                if poem_count >= 2:
                    user.profile.credits -= 1
                    user.profile.save()

            poem.full_clean()
            poem.save()

            return JsonResponse({'status': 'success', 'poem': poem.generated_text})
        except ValidationError as e:
            logger.error(f"Validatie fout: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Fout bij genereren gedicht: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



class CreditPurchaseView(LoginRequiredMixin, View):
    def get(self, request):
        credit_packages = [
            {'name': 'Starter', 'credits': 1, 'price_cents': 50},
            {'name': 'Economie', 'credits': 15, 'price_cents': 500},
        ]
        
        # Beschikbare betaalmethoden per land
        payment_methods = {
            'nl': ['ideal', 'card'],
            'be': ['bancontact', 'card'],
            'other': ['card']
        }
        
        return render(request, 'poems/purchase_credits.html', {
            'credit_packages': credit_packages,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'payment_methods': payment_methods,
        })

    def post(self, request):
        try:
            data = json.loads(request.body)
            package = next((p for p in [
                {'name': 'Starter', 'credits': 1, 'price_cents': 50},
                {'name': 'Economie', 'credits': 15, 'price_cents': 500},
            ] if p['name'] == data['package']), None)

            if not package:
                return JsonResponse({'error': 'Ongeldig pakket'}, status=400)

            # Create PaymentIntent with automatic payment methods
            payment_intent = stripe.PaymentIntent.create(
                amount=package['price_cents'],
                currency='eur',
                metadata={
                    'user_id': request.user.id,
                    'credits': package['credits']
                },
                automatic_payment_methods={
                    'enabled': True,
                }
            )

            return JsonResponse({
                'clientSecret': payment_intent.client_secret,
                'amount': package['price_cents'],
                'currency': 'eur'
            })

        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )

            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                
                # Verwerk de succesvolle betaling
                user_id = payment_intent.metadata.get('user_id')
                credits = int(payment_intent.metadata.get('credits', 0))
                
                if user_id and credits:
                    user = User.objects.get(id=user_id)
                    profile = user.profile
                    profile.credits += credits
                    profile.save()

            return JsonResponse({'status': 'success'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class CustomLoginView(View):
    def get(self, request):
        # Toon het loginformulier
        form = AuthenticationForm()
        return render(request, 'registration/login.html', {'form': form})

    def post(self, request):
        # Verwerk het loginformulier
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('poem_create')
        # Als inloggen mislukt, toon opnieuw het formulier met foutmeldingen
        return render(request, 'registration/login.html', {'form': form})
    

class SignupView(View):
    def get(self, request):
        form = SignupForm()
        return render(request, 'registration/signup.html', {'form': form})
    
    def post(self, request):
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log de gebruiker direct in na registratie
            login(request, user)
            # Redirect naar homepage in plaats van login pagina
            return redirect('poem_create')
        return render(request, 'registration/signup.html', {'form': form})

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        # Haal de gedichten van de ingelogde gebruiker op
        poems = Poem.objects.filter(user=user)
        return render(request, 'dashboard.html', {
            'poems': poems,
            'credits': user.profile.credits
        })
        
        
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
            model="gpt-4o",
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

class CheckoutCompleteView(LoginRequiredMixin, View):
    def get(self, request):
        payment_intent_id = request.GET.get('payment_intent')
        payment_intent_client_secret = request.GET.get('payment_intent_client_secret')
        
        try:
            # Verify the payment intent
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status == 'succeeded':
                # Add credits to user's account
                credits = payment_intent.metadata.get('credits', 0)
                profile = request.user.profile
                profile.credits += int(credits)
                profile.save()
                
                return render(request, 'poems/purchase_complete.html', {
                    'success': True,
                    'credits_added': credits,
                    'total_credits': profile.credits
                })
            else:
                return render(request, 'poems/purchase_complete.html', {
                    'success': False,
                    'error': 'Betaling niet voltooid'
                })
                
        except Exception as e:
            logger.error(f"Error processing checkout completion: {str(e)}")
            return render(request, 'poems/purchase_complete.html', {
                'success': False,
                'error': 'Er is een fout opgetreden bij het verwerken van de betaling'
            })