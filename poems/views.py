import logging
import json
import re
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, View
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.exceptions import ValidationError
from pydantic import BaseModel
from .models import Poem, Profile
from .forms import PoemForm, SinterklaasPoemForm
from .utils import contains_blocked_content, retry_with_exponential_backoff, generate_image_with_fal
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

PLANNER_JSON_SCHEMA = {
    "name": "poem_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "rijmschema": {"type": "string"},
            "aantal_strofen": {"type": "integer"},
            "toon": {"type": "string"},
            "thema": {"type": "string"},
            "excluded_words": {"type": "string"},
            "eindklanken_per_strofe": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "extra_instructies": {"type": "string"},
        },
        "required": [
            "rijmschema",
            "aantal_strofen",
            "toon",
            "thema",
            "excluded_words",
            "eindklanken_per_strofe",
            "extra_instructies",
        ],
        "additionalProperties": False,
    },
}

def _safe_json_loads(text: str):
    if not text or not isinstance(text, str):
        raise ValueError("Lege of ongeldige JSON-respons van model")
    try:
        return json.loads(text)
    except Exception:
        s = text.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.DOTALL)
        s = s.strip()
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"\{.*\}", s, flags=re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise

def _normalize_content(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                txt = ""
                text_field = part.get("text") or part.get("content") or part.get("value")
                if isinstance(text_field, str):
                    txt = text_field
                elif isinstance(text_field, dict):
                    txt = text_field.get("value") or text_field.get("content") or ""
                if txt:
                    parts.append(txt)
            else:
                text_attr = getattr(part, "text", None)
                if isinstance(text_attr, str):
                    parts.append(text_attr)
                else:
                    parts.append(str(part))
        return "".join(parts).strip()
    if isinstance(value, dict):
        for key in ("text", "value", "content"):
            v = value.get(key)
            if isinstance(v, str):
                return v
        return ""
    return str(value)

def _get_choice_content(choice) -> str:
    try:
        msg = getattr(choice, "message", None)
        if msg is not None:
            c = getattr(msg, "content", None)
            text = _normalize_content(c)
            if text:
                return text
    except Exception:
        pass
    try:
        t = getattr(choice, "text", None)
        text = _normalize_content(t)
        if text:
            return text
    except Exception:
        pass
    return ""

def _model_supports_json_mode(model: str) -> bool:
    if not model:
        return False
    return not model.startswith("google/")

def get_client_ip(request):
    """Haal het IP-adres van de gebruiker op."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_openai_client():
    """Stel de OpenAI client in voor gebruik via OpenRouter."""
    api_key = getattr(settings, 'OPENROUTER_API_KEY', None) or getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError("Geen OpenRouter of OpenAI API-key gevonden in settings.")

    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    default_headers = {}

    http_referer = getattr(settings, 'OPENROUTER_HTTP_REFERER', None)
    if http_referer:
        default_headers['HTTP-Referer'] = http_referer

    title = getattr(settings, 'OPENROUTER_TITLE', None)
    if title:
        default_headers['X-Title'] = title

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers or None,
        timeout=getattr(settings, 'OPENROUTER_TIMEOUT', 25),
    )
    return client

def test_openai_connection():
    """Test of de OpenAI API goed werkt."""
    try:
        client = get_openai_client()
        model = getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview')
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'API connection successful'"}],
            max_tokens=10,
            timeout=10,
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
def _generate_poem_simple(data):
    client = get_openai_client()

    theme = data.get('theme', '')
    style = data.get('style', 'rijmend')
    mood = data.get('mood', '')
    recipient = data.get('recipient', '')
    season = data.get('season', '')
    length = data.get('length', 'medium')
    excluded_words = data.get('excluded_words', '').strip() or 'geen specifiek'

    style_instruction = beschrijf_stijl_op_basis_van_de_user_input(data)

    system_prompt = (
        "Je bent een Nederlandse dichter.\n"
        "Je schrijft veilige, familie-vriendelijke gedichten zonder ongepaste inhoud.\n"
        "Geef ALLEEN het volledige gedicht terug, als platte tekst, zonder uitleg of JSON."
    )

    user_prompt = f"""
Thema: {theme}
Stijl: {style}
Stemming (mood): {mood}
Ontvanger: {recipient}
Seizoen: {season}
Gewenste lengte: {length}
Uit te sluiten woorden: {excluded_words}

Extra stijlinstructies:
{style_instruction}

Schrijf nu direct het volledige gedicht in het Nederlands.
""".strip()

    model = getattr(
        settings,
        'GENERATOR_MODEL',
        getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview'),
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1200,
        timeout=getattr(settings, 'OPENROUTER_TIMEOUT', 25),
    )

    text = _get_choice_content(completion.choices[0]) or ""
    text = text.strip()
    if not text:
        raise ValueError("Lege respons van model bij het genereren van het gedicht.")
    return text

@retry_with_exponential_backoff(max_retries=3, initial_wait=5)
def _process_user_input(data):
    """
    Verwerk gebruikersinvoer tot gestructureerde instructies.
    """
    user_input = f"""
    Thema: {data.get('theme', '')}
    Stijl: {data.get('style', 'rijmend')}
    Mood: {data.get('mood', '')}
    Ontvanger: {data.get('recipient', '')}
    Seizoen: {data.get('season', '')}
    Lengte: {data.get('length', '')}
    Uit te sluiten woorden: {data.get('excluded_words', '')}
    """

    system_prompt = """Je bent een strenge planner voor rijmende Nederlandstalige gedichten.
Maak voor elke aanvraag een concreet plan en lever ALLEEN het volgende JSON-object terug:
{
 "rijmschema": "aabb",
 "aantal_strofen": 4,
 "toon": "speels",
 "thema": "...",
 "excluded_words": "...",
 "eindklanken_per_strofe": [
   ["al", "al"],
   ["oot", "oot"],
   ...
 ],
 "extra_instructies": "..."
}
Regels:
1. "eindklanken_per_strofe" is een lijst met lijsten; elke binnenste lijst bevat de exacte klank (of eindwoord) waarop de regels van de strofe moeten eindigen, in volgorde volgens het rijmschema.
2. Als er geen uitgesloten woorden zijn, zet "excluded_words" op een lege string.
3. Toon, thema en extra instructies moeten de gegeven mood/style/seizoen verwerken.
4. Output MOET harde JSON zijn zonder extra tekst.
"""

    model = getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview')

    api_key = getattr(settings, 'OPENROUTER_API_KEY', None) or getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError("Geen OpenRouter of OpenAI API-key gevonden in settings.")

    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    http_referer = getattr(settings, 'OPENROUTER_HTTP_REFERER', None)
    if http_referer:
        headers["HTTP-Referer"] = http_referer
    title = getattr(settings, 'OPENROUTER_TITLE', None)
    if title:
        headers["X-Title"] = title

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }

    if model.startswith("google/"):
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": PLANNER_JSON_SCHEMA,
        }

    timeout = getattr(settings, 'OPENROUTER_TIMEOUT', 25)
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("choices"):
        raise ValueError("Lege of ongeldige JSON-respons van model")

    message = data["choices"][0].get("message", {})
    raw_content = message.get("content")

    if isinstance(raw_content, dict):
        structured_input = raw_content
    else:
        content = _normalize_content(raw_content)
        structured_input = _safe_json_loads(content)

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
    model = getattr(settings, 'GENERATOR_MODEL', getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview'))
    fallback_model = getattr(settings, 'FALLBACK_MODEL', 'google/gemini-3-pro-preview')
    use_json_mode = _model_supports_json_mode(model)
    try:
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt + "\n\nEis: gebruik exact de eindklanken per strofe zoals aangeleverd. Elke regel moet eindigen op die klank of een woord dat duidelijk rijmt."},
                {"role": "user", "content": poem_prompt}
            ],
            "temperature": 0.6,
            "max_tokens": 1200,
            "timeout": 40,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = client.chat.completions.create(**kwargs)
        content = _get_choice_content(completion.choices[0]) or ""
        data = _safe_json_loads(content)
    except Exception as e:
        logger.warning(f"Generator JSON-mode faalde ({type(e).__name__}): {e}. Probeer zonder response_format.")
        try:
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt + "\n\nEis: gebruik exact de eindklanken per strofe zoals aangeleverd. Elke regel moet eindigen op die klank of een woord dat duidelijk rijmt."},
                    {"role": "user", "content": poem_prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 1200,
                "timeout": 40,
            }
            completion = client.chat.completions.create(**kwargs)
            content = _get_choice_content(completion.choices[0]) or ""
            data = _safe_json_loads(content)
        except Exception as e2:
            logger.warning(f"Generator zonder JSON-mode faalde ({type(e2).__name__}): {e2}. Fallback model wordt geprobeerd.")
            kwargs = {
                "model": fallback_model,
                "messages": [
                    {"role": "system", "content": system_prompt + "\n\nEis: gebruik exact de eindklanken per strofe zoals aangeleverd. Elke regel moet eindigen op die klank of een woord dat duidelijk rijmt."},
                    {"role": "user", "content": poem_prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 1200,
                "timeout": 40,
                "response_format": {"type": "json_object"} if _model_supports_json_mode(fallback_model) else None,
            }
            if kwargs["response_format"] is None:
                del kwargs["response_format"]
            completion = client.chat.completions.create(**kwargs)
            content = _get_choice_content(completion.choices[0]) or ""
            data = _safe_json_loads(content)
    poem_draft = PoemSchema.model_validate(data)
    return poem_draft

@retry_with_exponential_backoff(max_retries=3, initial_wait=5)
def _check_and_fix_rhyme(poem_draft, structured_input, data):
    client = get_openai_client()
    poem_json_for_prompt = poem_draft.model_dump_json() if hasattr(poem_draft, 'model_dump_json') else poem_draft.json()
    check_prompt = f"""
Dit is het gedicht dat je hebt gemaakt (in JSON):
{poem_json_for_prompt}

Rijmschema: {structured_input.get('rijmschema', 'aabb')}

Controleer of elke strofe het juiste rijmschema volgt (indien opgegeven). Als er regels niet rijmen of niet passen bij de instructies, herschrijf alleen die specifieke versregels.
Behoud dezelfde titel, thema en stijl. Hou rekening met uitgesloten woorden: {structured_input.get('excluded_words','')}

Antwoord opnieuw in exact hetzelfde JSON-formaat (title, verses) zonder extra tekst.
"""
    model = getattr(settings, 'EDITOR_MODEL', getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview'))
    fallback_model = getattr(settings, 'FALLBACK_MODEL', 'google/gemini-3-pro-preview')
    use_json_mode = _model_supports_json_mode(model)
    try:
        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Je bent een Nederlandse eindredacteur. Controleer per strofe of de laatste woorden rijmen volgens het opgegeven schema en de opgegeven eindklanken. Herschrijf alleen regels die falen, en zorg dat nieuwe regels WEL rijmen."
                },
                {"role": "user", "content": check_prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 900,
            "timeout": 40,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = client.chat.completions.create(**kwargs)
        poem_json = _get_choice_content(completion.choices[0]) or ""
        final_poem = PoemSchema.model_validate(_safe_json_loads(poem_json))
    except Exception as e:
        logger.warning(f"Editor JSON-mode faalde ({type(e).__name__}): {e}. Probeer zonder response_format.")
        try:
            kwargs = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Je bent een Nederlandse eindredacteur. Controleer per strofe of de laatste woorden rijmen volgens het opgegeven schema en de opgegeven eindklanken. Herschrijf alleen regels die falen, en zorg dat nieuwe regels WEL rijmen."
                    },
                    {"role": "user", "content": check_prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 900,
                "timeout": 40,
            }
            completion = client.chat.completions.create(**kwargs)
            poem_json = _get_choice_content(completion.choices[0]) or ""
            final_poem = PoemSchema.model_validate(_safe_json_loads(poem_json))
        except Exception as e2:
            logger.warning(f"Editor zonder JSON-mode faalde ({type(e2).__name__}): {e2}. Fallback model wordt geprobeerd.")
            kwargs = {
                "model": fallback_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Je bent een Nederlandse eindredacteur. Controleer per strofe of de laatste woorden rijmen volgens het opgegeven schema en de opgegeven eindklanken. Herschrijf alleen regels die falen, en zorg dat nieuwe regels WEL rijmen."
                    },
                    {"role": "user", "content": check_prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 900,
                "timeout": 40,
                "response_format": {"type": "json_object"} if _model_supports_json_mode(fallback_model) else None,
            }
            if kwargs["response_format"] is None:
                del kwargs["response_format"]
            completion = client.chat.completions.create(**kwargs)
            poem_json = _get_choice_content(completion.choices[0]) or ""
            final_poem = PoemSchema.model_validate(_safe_json_loads(poem_json))
    return final_poem

class PoemCreateView(View):
    template_name = 'poems/create_poem.html'

    def get(self, request, *args, **kwargs):
        # Render de HTML pagina met het formulier en een teller van alle gedichten
        total_poems = Poem.objects.count()
        return render(request, self.template_name, {"total_poems": total_poems})

    @method_decorator(ratelimit(key='ip', rate='5/m', method=['POST'], block=True))
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
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Je hebt je gratis maandlimiet bereikt. Koop credits om meer gedichten te genereren.',
                            'redirect_url': reverse('purchase_credits')
                        }, status=402)
                    # Trek 1 credit af als straks opslaan slaagt.
            else:
                # Anoniem: limit per week (7 dagen)
                past_week = now - timedelta(days=7)
                poems_count = Poem.objects.filter(ip_address=ip_address, created_at__gte=past_week).count()
                if poems_count >= 2:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Je hebt het maximale aantal gedichten (2) voor deze week bereikt. Maak een account en koop credits om meer te genereren.',
                        'redirect_url': reverse('signup')
                    }, status=429)

            # Genereer het gedicht (simpele modus)
            poem_text = _generate_poem_simple(data)

            if contains_blocked_content(poem_text):
                return JsonResponse({'status': 'error', 'message': 'Gegenereerde inhoud bevat ongepaste termen'}, status=400)

            # Voor nu geen afbeelding genereren
            image_url = ""

            # Gedicht opslaan in de database
            poem = Poem(
                theme=data.get('theme', ''),
                style=data.get('style', ''),
                mood=data.get('mood', ''),
                season=data.get('season', ''),
                length=data.get('length', ''),
                recipient=data.get('recipient', ''),
                excluded_words=data.get('excluded_words', ''),
                generated_text=poem_text,
                image_url=image_url,
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

            return JsonResponse({'status': 'success', 'poem': poem.generated_text, 'image_url': image_url})
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

    @method_decorator(ratelimit(key='ip', rate='5/m', method=['POST'], block=True))
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
        model = getattr(settings, 'GENERATOR_MODEL', getattr(settings, 'PLANNER_MODEL', 'google/gemini-3-pro-preview'))
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1200,
            timeout=40,
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
            
def checkout_complete(request):
    # Lees de query parameters uit
    payment_intent_id = request.GET.get('payment_intent', None)

    if not payment_intent_id:
        # Geen payment_intent in de URL => redirect naar home of error pagina
        return redirect('poem_create')  # pas aan naar wens

    # Haal de PaymentIntent op via de Stripe API
    try:
        pi = stripe.PaymentIntent.retrieve(payment_intent_id)
    except Exception as e:
        # Kon PaymentIntent niet ophalen => foutafhandeling
        return redirect('poem_create')  # of toon een foutpagina

    # Controleer de status
    if pi.status == 'succeeded':
        # Betaling geslaagd, redirect naar schone success pagina
        return redirect('checkout_success')
    else:
        # Betaling niet geslaagd, laat dit zien of redirect naar error pagina
        # Je kunt bijvoorbeeld een melding tonen dat de betaling niet is afgerond
        return redirect('checkout_error')
    
def checkout_success(request):
    # Toon een nette pagina "Bedankt voor je aankoop!"
    return render(request, 'checkout/success.html')