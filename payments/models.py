from django.db import models
from blood_requests.models import BloodRequest, RequestDonorMatch
from donors.models import Donor
from hospitals.models import Hospital

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    request = models.OneToOneField(BloodRequest, on_delete=models.CASCADE, related_name='payment')
    match = models.ForeignKey(RequestDonorMatch, on_delete=models.SET_NULL, null=True, related_name='payments')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default='NGN')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Bank transfer details
    sender_bank = models.CharField(max_length=100, blank=True)
    sender_account = models.CharField(max_length=20, blank=True)
    sender_name = models.CharField(max_length=200, blank=True)
    recipient_bank = models.CharField(max_length=100)
    recipient_account = models.CharField(max_length=20)
    recipient_name = models.CharField(max_length=200)
    transfer_reference = models.CharField(max_length=200, blank=True)
    transfer_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
