from django.urls import path
from . import views

urlpatterns = [
    path('', views.blood_requests_list_create, name='requests-list'),
    path('<int:pk>/', views.blood_request_detail, name='request-detail'),
    path('<int:pk>/donors/', views.request_donors, name='request-donors'),
    path('<int:pk>/donors/<int:match_id>/check-availability/', views.check_donor_availability, name='check-availability'),
    path('<int:pk>/donors/<int:match_id>/select/', views.select_donor, name='select-donor'),
]
