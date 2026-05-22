from django.urls import path
from . import views

urlpatterns = [
    path('<int:request_id>/initiate/', views.initiate_payment, name='initiate-payment'),
    path('<int:request_id>/confirm/', views.confirm_payment, name='confirm-payment'),
    path('<int:request_id>/close/', views.close_session, name='close-session'),
    path('<int:request_id>/', views.payment_detail, name='payment-detail'),
]
