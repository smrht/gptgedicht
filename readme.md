# GedichtGPT

Een moderne webapplicatie voor het genereren van Nederlandse gedichten met behulp van AI.

## Functionaliteiten

- Genereer gedichten op basis van thema
- Kies uit verschillende stijlen (modern, klassiek, romantisch, haiku, sonnet)
- Pas de stemming aan (vrolijk, melancholisch, romantisch, etc.)
- Seizoensgebonden gedichten
- Kies de gewenste lengte van het gedicht
- Mobiel-vriendelijke interface
- Rate limiting om overbelasting te voorkomen

## Installatie

1. Clone de repository
2. Maak een virtuele omgeving aan:
```bash
python -m venv venv
source venv/bin/activate  # Voor Unix/macOS
# Windows
venv\Scripts\activate
```

3. Installeer de benodigde packages:
```bash
pip install -r requirements.txt
```

4. Maak een .env bestand aan op basis van `.env.example`:
```bash
cp .env.example .env
```

5. Vul het `.env`-bestand met jouw gegevens. De beschikbare variabelen zijn:
   - `SECRET_KEY`
   - `DEBUG`
   - `ALLOWED_HOSTS`
   - `OPENAI_API_KEY`
   - `FAL_API_KEY`
   - `STRIPE_PUBLIC_KEY`
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`

6. Voer de database migraties uit:
```bash
python manage.py migrate
```

## Gebruik

1. Start de applicatie:
```bash
python manage.py runserver
```

2. Open je browser en ga naar `http://localhost:8000`

3. Vul de gewenste velden in en klik op "Genereer Gedicht"

## Technische Details

- Backend: Python Django
- Frontend: HTML, TailwindCSS, JavaScript
- AI: OpenAI GPT-3.5
- Rate Limiting: django-ratelimit
- Caching: Redis (optioneel)
