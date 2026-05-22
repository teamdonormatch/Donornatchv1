from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.hospital_profile, name='hospital-profile'),
    path('create/', views.create_hospital_profile, name='hospital-create'),
]
