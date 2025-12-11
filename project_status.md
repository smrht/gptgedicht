# Project Status

## 2025-11-29: Valentijnsgedicht Generator toegevoegd

### Nieuwe feature: `/valentijn/`
SEO-geoptimaliseerde Valentijnsgedicht generator met:

**Parameters:**
- `recipient` - Voor wie is het gedicht
- `relatie_type` - partner, crush, getrouwd, dating, afstand, geheim
- `mood` - romantisch, speels, grappig, sensueel, lief, poëtisch
- `length` - kort (3), medium (5), lang (7 strofen)
- `eigenschappen` - Wat je leuk vindt aan de persoon
- `herinneringen` - Speciale momenten

**Bestanden:**
- `poems/forms.py`: `ValentijnsPoemForm`
- `poems/views.py`: `ValentijnsPoemCreateView`
- `poems/templates/poems/create_valentijn_poem.html`
- `poems/urls.py`: route `/valentijn/`

**SEO:**
- Meta tags, Open Graph, Twitter cards
- Structured data (Schema.org)
- FAQ sectie
- Canonical URL

---

## 2025-11-29: Fix Sinterklaas 400 Bad Request

### Probleem
POST naar `/sinterklaas/` gaf 400 Bad Request door veld mismatch.

### Oorzaak
1. Template stuurde `subject`, form verwachtte `theme`
2. `additional_info` veld miste in form
3. **Template mood values niet in model's MOOD_CHOICES**

### Oplossing
1. Template: `name="subject"` → `name="theme"`
2. Form: eigen `SINT_MOOD_CHOICES`, `additional_info` veld
3. View: `data['subject']` → `data['theme']`

---

## 2025-12-11: Fix Credit Systeem Bug Sinterklaas/Valentijn

### Probleem
Ingelogde gebruikers met credits kregen foutmelding "Maak een account" bij Sinterklaas/Valentijn gedichten.

### Oorzaak
`SinterklaasPoemCreateView` en `ValentijnsPoemCreateView` koppelden `user` niet aan `Poem` object → model validatie dacht dat het anonieme gebruikers waren.

### Oplossing
In beide views toegevoegd:
1. `poem.user = request.user` (als ingelogd)
2. `poem.ip_address = get_client_ip(request)`
3. Credit check vóór generatie
4. Credit aftrek ná succesvolle generatie (als >2 gedichten/maand)

**Bestanden:** `poems/views.py` (regel 835-870 en 978-1012)

---

## 2025-12-11: Fix form prefill user/ip voor Sinterklaas & Valentijn

### Probleem
`form.is_valid()` riep `full_clean()` aan terwijl `user` nog leeg was → model dacht dat het anoniem was en gebruikte IP-rate-limit, ook bij ingelogde users met credits.

### Oplossing
Voor `form.is_valid()` in beide views:
1. `form.instance.ip_address = get_client_ip(request)`
2. `form.instance.user = request.user` (indien ingelogd)
3. Daarna `form.save(commit=False)` met fallback `poem.ip_address = poem.ip_address or get_client_ip(request)` en `user = form.instance.user`

**Bestanden:** `poems/views.py` (Sinterklaas: regel 824-845, Valentijn: regel 969-994)

---

## TODO
- [ ] Rate limit terugzetten naar 2 in `poems/models.py` regel 107
