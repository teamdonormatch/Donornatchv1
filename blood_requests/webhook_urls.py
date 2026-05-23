from django.urls import path
from . import webhook_views

urlpatterns = [
    # N8N calls these two endpoints
    path('n8n/donors-found/',       webhook_views.donors_found,       name='wh-donors-found'),
    path('n8n/availability-result/', webhook_views.availability_result, name='wh-availability'),
]