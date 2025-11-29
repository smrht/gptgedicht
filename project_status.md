# Project Status

## 2025-11-29: Fix Sinterklaas 400 Bad Request

### Probleem
POST naar `/sinterklaas/` gaf 400 Bad Request door veld mismatch.

### Oorzaak
1. Template stuurde `subject`, form verwachtte `theme`
2. `additional_info` veld miste in form
3. **Template mood values (`grappig`, `lief`, `pesterig`) niet in model's MOOD_CHOICES**

### Oplossing
1. **Template** (`create_sinterklaas_poem.html`): `name="subject"` → `name="theme"`
2. **Form** (`forms.py`): 
   - `additional_info` CharField toegevoegd
   - Eigen `SINT_MOOD_CHOICES` met Sinterklaas-specifieke opties
   - `mood` field overschreven met eigen ChoiceField
   - `save()` method: mood handmatig opslaan
3. **View** (`views.py`): `data['subject']` → `data['theme']`

### Model configuratie
Sinterklaas gebruikt dezelfde modellen als poemgenerator:
- `settings.GENERATOR_MODEL` (default: `google/gemini-2.5-flash`)
