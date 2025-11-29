from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.conf import settings
import os
from .views import checkout_complete, checkout_success, PoemCreateView, SinterklaasPoemCreateView, ValentijnsPoemCreateView, SignupView, CreditPurchaseView, StripeWebhookView, DashboardView, CheckoutCompleteView

def ads_txt(request):
    """Serve ads.txt for Google AdSense verification"""
    ads_path = os.path.join(settings.BASE_DIR, 'ads.txt')
    with open(ads_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type='text/plain')

urlpatterns = [
    path('ads.txt', ads_txt, name='ads_txt'),
    path('', PoemCreateView.as_view(), name='poem_create'),
    path('sinterklaas/', SinterklaasPoemCreateView.as_view(), name='sinterklaas_poem_create'),
    path('valentijn/', ValentijnsPoemCreateView.as_view(), name='valentijn_poem_create'),
    path('over-ons/', TemplateView.as_view(template_name='poems/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='poems/privacy.html'), name='privacy'),
    path('voorwaarden/', TemplateView.as_view(template_name='poems/terms.html'), name='terms'),
    path('contact/', TemplateView.as_view(template_name='poems/contact.html'), name='contact'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', SignupView.as_view(), name='signup'),
    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('checkout/complete/', CheckoutCompleteView.as_view(), name='checkout_complete'),
    
    # Dashboard, credits etc. volgen verderop.
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('purchase-credits/', CreditPurchaseView.as_view(), name='purchase_credits'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('checkout/complete/', checkout_complete, name='checkout_complete'),
    path('checkout/success/', checkout_success, name='checkout_success'),
]
