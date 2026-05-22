from django.urls import path
from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

urlpatterns = [
    path('', index, name='home'),
    path('login/', index),
    path('signup/', index),
    path('dashboard/', index),
    path('requests/', index),
    path('requests/<str:anything>/', index),
    path('profile/', index),
]
