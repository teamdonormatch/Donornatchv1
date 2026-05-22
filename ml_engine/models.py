from django.db import models

class MLModelVersion(models.Model):
    version = models.CharField(max_length=20)
    accuracy = models.FloatField()
    total_training_samples = models.IntegerField()
    is_active = models.BooleanField(default=False)
    is_autonomous = models.BooleanField(default=False)
    model_path = models.CharField(max_length=500)
    training_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_model_versions'

class DonorMatchOutcome(models.Model):
    donor_blood_group = models.CharField(max_length=5)
    request_blood_group = models.CharField(max_length=5)
    donor_city = models.CharField(max_length=100)
    request_city = models.CharField(max_length=100)
    donor_age = models.IntegerField()
    donor_weight = models.FloatField()
    donor_total_donations = models.IntegerField()
    donor_response_rate = models.FloatField()
    urgency_level = models.CharField(max_length=20)
    was_available = models.BooleanField()
    was_selected = models.BooleanField()
    donation_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'donor_match_outcomes'

class SystemStats(models.Model):
    date = models.DateField(unique=True)
    total_requests = models.IntegerField(default=0)
    n8n_handled = models.IntegerField(default=0)
    ml_handled = models.IntegerField(default=0)
    successful_matches = models.IntegerField(default=0)
    ml_accuracy = models.FloatField(default=0.0)
    autonomous_mode = models.BooleanField(default=False)

    class Meta:
        db_table = 'system_stats'
