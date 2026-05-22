from django.contrib import admin
from .models import MLModelVersion, DonorMatchOutcome, SystemStats
admin.site.register(MLModelVersion)
admin.site.register(DonorMatchOutcome)
admin.site.register(SystemStats)
