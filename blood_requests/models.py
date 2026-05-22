from django.db import models
from hospitals.models import Hospital
from donors.models import Donor, BLOOD_GROUPS

URGENCY_LEVELS = [
    ('critical', 'Critical - Immediate'),
    ('urgent', 'Urgent - Within 2 hours'),
    ('standard', 'Standard - Within 24 hours'),
]

class BloodRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent_to_n8n', 'Sent to N8N'),
        ('ml_processing', 'ML Processing'),
        ('donors_found', 'Donors Found'),
        ('donor_selected', 'Donor Selected'),
        ('payment_pending', 'Payment Pending'),
        ('payment_confirmed', 'Payment Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='blood_requests')
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUPS)
    units_needed = models.IntegerField(default=1)
    urgency = models.CharField(max_length=20, choices=URGENCY_LEVELS, default='standard')
    patient_name = models.CharField(max_length=200, blank=True)
    patient_condition = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    n8n_workflow_id = models.CharField(max_length=200, blank=True, null=True)
    n8n_execution_id = models.CharField(max_length=200, blank=True, null=True)
    handled_by_ml = models.BooleanField(default=False)
    ml_confidence_score = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Request #{self.id} - {self.blood_group} by {self.hospital.name}"

    class Meta:
        db_table = 'blood_requests'
        ordering = ['-created_at']

class RequestDonorMatch(models.Model):
    STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('availability_checking', 'Checking Availability'),
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('selected', 'Selected by Hospital'),
        ('rejected', 'Rejected by Hospital'),
        ('completed', 'Completed'),
    ]

    request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name='donor_matches')
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name='request_matches')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='proposed')
    match_score = models.FloatField(default=0.0)  # ML score 0-1
    is_available = models.BooleanField(null=True)
    availability_checked_at = models.DateTimeField(null=True, blank=True)
    selected_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'request_donor_matches'
        unique_together = ['request', 'donor']
