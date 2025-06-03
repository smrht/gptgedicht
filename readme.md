# GedichtGPT

Een moderne web applicatie voor het genereren van Nederlandse gedichten met behulp van AI.

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
```
3. Installeer de benodigde packages:
```bash
pip install -r requirements.txt
```
4. Maak een .env bestand aan op basis van `.env.example` en vul de benodigde sleutels in:
```bash
cp .env.example .env
```

## Gebruik

1. Voer de database migraties uit:
```bash
python manage.py migrate
```
2. Start de applicatie lokaal:
```bash
python manage.py runserver
```
3. Open je browser en ga naar `http://localhost:8000`
4. Vul de gewenste velden in en klik op "Genereer Gedicht"

## Technische Details

- Backend: Python Django
- Frontend: HTML, TailwindCSS, JavaScript
- AI: OpenAI GPT-3.5
- Rate Limiting: django-ratelimit
- Caching: Redis (optioneel)
