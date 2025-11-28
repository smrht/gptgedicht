from django.urls import path
from . import views

app_name = 'ads'

urlpatterns = [
    path('', views.banner_positions_list, name='positions_list'),
    path('<slug:slug>/', views.purchase_banner, name='purchase_banner'),
    path('checkout/<uuid:purchase_id>/', views.create_checkout_session, name='create_checkout'),
    path('success/<uuid:purchase_id>/', views.purchase_success, name='purchase_success'),
    path('cancel/<uuid:purchase_id>/', views.purchase_cancel, name='purchase_cancel'),
    path('api/price/<slug:slug>/<str:period>/', views.get_price_for_period, name='get_price'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]
