from django.db import models

BLOOD_GROUPS = [
    ('A+', 'A+'), ('A-', 'A-'),
    ('B+', 'B+'), ('B-', 'B-'),
    ('AB+', 'AB+'), ('AB-', 'AB-'),
    ('O+', 'O+'), ('O-', 'O-'),
]

class Donor(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive'), ('blacklisted', 'Blacklisted')]
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUPS)
    age = models.IntegerField()
    weight = models.FloatField(help_text='Weight in kg')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Nigeria')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_donation_date = models.DateField(null=True, blank=True)
    total_donations = models.IntegerField(default=0)
    response_rate = models.FloatField(default=0.0)  # 0-1 score
    availability_score = models.FloatField(default=0.5)  # ML computed
    reliability_score = models.FloatField(default=0.5)  # ML computed
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    n8n_donor_id = models.CharField(max_length=200, blank=True, null=True)  # ID from n8n workflow
    source = models.CharField(max_length=20, choices=[('n8n', 'N8N'), ('direct', 'Direct'), ('ml', 'ML Discovered')], default='n8n')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.blood_group})"

    class Meta:
        db_table = 'donors'

class DonorAvailabilityLog(models.Model):
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name='availability_logs')
    checked_at = models.DateTimeField(auto_now_add=True)
    is_available = models.BooleanField()
    response_time_seconds = models.IntegerField(null=True, blank=True)
    check_method = models.CharField(max_length=20, choices=[('call', 'Phone Call'), ('sms', 'SMS'), ('api', 'API')])
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'donor_availability_logs'
