from django.contrib import admin
from .models import BloodRequest, RequestDonorMatch
admin.site.register(BloodRequest)
admin.site.register(RequestDonorMatch)
