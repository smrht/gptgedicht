from django.urls import path
from .views import PoemCreateView, SinterklaasPoemCreateView

urlpatterns = [
    path('', PoemCreateView.as_view(), name='poem_create'),
    path('sinterklaas/', SinterklaasPoemCreateView.as_view(), name='sinterklaas_poem_create'),
]
