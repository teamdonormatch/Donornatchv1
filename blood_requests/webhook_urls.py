from django.urls import path
from . import views

urlpatterns = [
    path('n8n/donors-found/', views.n8n_webhook_donors_found, name='n8n-donors-found'),
]
