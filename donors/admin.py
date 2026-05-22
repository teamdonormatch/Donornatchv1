from django.contrib import admin
from .models import Donor, DonorAvailabilityLog
admin.site.register(Donor)
admin.site.register(DonorAvailabilityLog)
