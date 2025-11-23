from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from .views import checkout_complete, checkout_success, PoemCreateView, SinterklaasPoemCreateView, SignupView, CreditPurchaseView, StripeWebhookView, DashboardView, CheckoutCompleteView

urlpatterns = [
    path('', PoemCreateView.as_view(), name='poem_create'),
    path('sinterklaas/', SinterklaasPoemCreateView.as_view(), name='sinterklaas_poem_create'),
    path('over-ons/', TemplateView.as_view(template_name='poems/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='poems/privacy.html'), name='privacy'),
    path('voorwaarden/', TemplateView.as_view(template_name='poems/terms.html'), name='terms'),
    path('contact/', TemplateView.as_view(template_name='poems/contact.html'), name='contact'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('checkout/complete/', CheckoutCompleteView.as_view(), name='checkout_complete'),
    
    # Dashboard, credits etc. volgen verderop.
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('purchase-credits/', CreditPurchaseView.as_view(), name='purchase_credits'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('checkout/complete/', checkout_complete, name='checkout_complete'),
    path('checkout/success/', checkout_success, name='checkout_success'),
]
