from django.urls import path
from . import views

urlpatterns = [
    # Auth routing paths
    path('api/auth/register/', views.register_hospital_user, name='auth_register'),
    path('api/auth/login/', views.login_hospital_user, name='auth_login'),
    
    # Profile management paths
    path('api/hospital/profile/create/', views.create_hospital_profile, name='profile_create'),
    path('api/hospital/profile/', views.hospital_profile, name='profile_detail'),
]
