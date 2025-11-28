import stripe
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
from django.contrib import messages

from .models import BannerPosition, Banner, BannerPurchase
from .forms import BannerUploadForm, BannerPurchaseForm

# Stripe configuratie
stripe.api_key = settings.STRIPE_SECRET_KEY


def banner_positions_list(request):
    """Overzicht van alle beschikbare banner posities."""
    positions = BannerPosition.objects.filter(is_active=True)
    return render(request, 'ads/positions_list.html', {'positions': positions})


def purchase_banner(request, slug):
    """Stap 1 & 2: Kies periode en upload banner."""
    position = get_object_or_404(BannerPosition, slug=slug, is_active=True)
    
    # Check of positie al bezet is
    if position.has_active_banner():
        messages.warning(request, 'Deze positie is momenteel bezet. Probeer een andere positie.')
        return redirect('ads:positions_list')
    
    if request.method == 'POST':
        purchase_form = BannerPurchaseForm(request.POST)
        upload_form = BannerUploadForm(request.POST, request.FILES, position=position)
        
        if purchase_form.is_valid() and upload_form.is_valid():
            # Bepaal prijs op basis van periode
            period = purchase_form.cleaned_data['period']
            if period == 'month':
                price = position.price_month
            elif period == 'quarter':
                price = position.price_quarter
            else:
                price = position.price_year
            
            # Maak banner aan
            banner = upload_form.save()
            
            # Maak purchase aan
            purchase = BannerPurchase.objects.create(
                position=position,
                banner=banner,
                period=period,
                price_paid=price,
                buyer_email=purchase_form.cleaned_data['buyer_email'],
                buyer_name=purchase_form.cleaned_data.get('buyer_name', ''),
                company_name=purchase_form.cleaned_data.get('company_name', ''),
            )
            
            # Redirect naar Stripe checkout
            return redirect('ads:create_checkout', purchase_id=purchase.purchase_id)
    else:
        purchase_form = BannerPurchaseForm()
        upload_form = BannerUploadForm(position=position)
    
    return render(request, 'ads/purchase_banner.html', {
        'position': position,
        'purchase_form': purchase_form,
        'upload_form': upload_form,
    })


def create_checkout_session(request, purchase_id):
    """Maak Stripe checkout sessie aan."""
    purchase = get_object_or_404(BannerPurchase, purchase_id=purchase_id)
    
    if purchase.status != 'pending':
        messages.error(request, 'Deze aankoop is al verwerkt.')
        return redirect('ads:positions_list')
    
    try:
        # Stripe checkout sessie
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card', 'ideal'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'unit_amount': int(purchase.price_paid * 100),
                    'product_data': {
                        'name': f'Banner Advertentie: {purchase.position.name}',
                        'description': f'{purchase.get_period_display()} - {purchase.position.get_dimensions()}',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            customer_email=purchase.buyer_email,
            success_url=request.build_absolute_uri(
                reverse('ads:purchase_success', args=[purchase.purchase_id])
            ),
            cancel_url=request.build_absolute_uri(
                reverse('ads:purchase_cancel', args=[purchase.purchase_id])
            ),
            metadata={
                'purchase_id': str(purchase.purchase_id),
            }
        )
        
        # Sla session ID op
        purchase.stripe_session_id = checkout_session.id
        purchase.save()
        
        return redirect(checkout_session.url)
        
    except Exception as e:
        messages.error(request, f'Er ging iets mis bij het aanmaken van de betaling: {str(e)}')
        return redirect('ads:positions_list')


def purchase_success(request, purchase_id):
    """Succesvolle betaling afhandelen."""
    purchase = get_object_or_404(BannerPurchase, purchase_id=purchase_id)
    
    # Activeer de banner als nog niet gedaan
    if purchase.status == 'pending':
        purchase.activate()
    
    return render(request, 'ads/purchase_success.html', {'purchase': purchase})


def purchase_cancel(request, purchase_id):
    """Geannuleerde betaling."""
    purchase = get_object_or_404(BannerPurchase, purchase_id=purchase_id)
    
    # Verwijder banner en purchase bij annulering
    if purchase.status == 'pending':
        if purchase.banner:
            purchase.banner.image.delete()
            purchase.banner.delete()
        purchase.status = 'cancelled'
        purchase.save()
    
    messages.info(request, 'Je aankoop is geannuleerd.')
    return redirect('ads:positions_list')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe webhook voor betalingsbevestiging."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Handel checkout.session.completed af
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        purchase_id = session.get('metadata', {}).get('purchase_id')
        
        if purchase_id:
            try:
                purchase = BannerPurchase.objects.get(purchase_id=purchase_id)
                if purchase.status == 'pending':
                    purchase.stripe_payment_intent = session.get('payment_intent', '')
                    purchase.activate()
            except BannerPurchase.DoesNotExist:
                pass
    
    return HttpResponse(status=200)


def get_price_for_period(request, slug, period):
    """AJAX endpoint om prijs op te halen voor gekozen periode."""
    position = get_object_or_404(BannerPosition, slug=slug)
    
    if period == 'month':
        price = position.price_month
    elif period == 'quarter':
        price = position.price_quarter
    elif period == 'year':
        price = position.price_year
    else:
        return JsonResponse({'error': 'Ongeldige periode'}, status=400)
    
    return JsonResponse({
        'price': float(price),
        'formatted': f'€{price:.2f}'
    })
