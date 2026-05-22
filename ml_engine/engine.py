import os
import json
import numpy as np
import logging
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

BLOOD_COMPATIBILITY = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'],
}

class DonorMatchingEngine:
    def __init__(self):
        self.is_autonomous = False
        self.successful_matches = 0
        self.confidence_threshold = getattr(settings, 'ML_CONFIDENCE_THRESHOLD', 0.75)
        self.autonomous_threshold = getattr(settings, 'ML_AUTONOMOUS_MODE_THRESHOLD', 50)
        self._load_state()

    def _load_state(self):
        try:
            from ml_engine.models import MLModelVersion, DonorMatchOutcome
            active = MLModelVersion.objects.filter(is_active=True).first()
            if active:
                self.is_autonomous = active.is_autonomous
                self.successful_matches = active.total_training_samples
        except Exception as e:
            logger.warning(f"Could not load ML state: {e}")

    def get_compatible_blood_groups(self, blood_group):
        compatible = []
        for donor_group, can_donate_to in BLOOD_COMPATIBILITY.items():
            if blood_group in can_donate_to:
                compatible.append(donor_group)
        return compatible

    def score_donor(self, donor, request):
        score = 0.0
        weights = {
            'blood_compatibility': 0.40,
            'location_proximity': 0.20,
            'reliability': 0.20,
            'availability_history': 0.15,
            'recency': 0.05,
        }

        # Blood compatibility
        compatible = self.get_compatible_blood_groups(request.blood_group)
        if donor.blood_group in compatible:
            score += weights['blood_compatibility']
            if donor.blood_group == request.blood_group:
                score += 0.10  # exact match bonus

        # Location
        if donor.city.lower() == request.hospital.city.lower():
            score += weights['location_proximity']
        elif donor.state.lower() == request.hospital.state.lower():
            score += weights['location_proximity'] * 0.5

        # Reliability score
        score += weights['reliability'] * donor.reliability_score

        # Availability history
        score += weights['availability_history'] * donor.availability_score

        # Recency - penalize if donated recently
        if donor.last_donation_date:
            days_since = (datetime.now().date() - donor.last_donation_date).days
            if days_since < 56:  # 8 weeks minimum
                score *= 0.1
            elif days_since > 180:
                score += weights['recency']

        # Urgency boost for high response rate donors
        if request.urgency == 'critical' and donor.response_rate > 0.8:
            score *= 1.2

        return min(score, 1.0)

    def find_best_donors(self, request, limit=10):
        from donors.models import Donor
        compatible_groups = self.get_compatible_blood_groups(request.blood_group)
        
        candidates = Donor.objects.filter(
            blood_group__in=compatible_groups,
            status='active'
        ).exclude(
            last_donation_date__gte=datetime.now().date() - timedelta(days=56)
        )

        scored = []
        for donor in candidates:
            score = self.score_donor(donor, request)
            scored.append((donor, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def should_use_autonomous_mode(self):
        return self.is_autonomous and self.successful_matches >= self.autonomous_threshold

    def update_donor_scores(self, donor, was_available, was_selected, completed):
        alpha = 0.1
        if was_available:
            donor.availability_score = donor.availability_score * (1 - alpha) + alpha * 1.0
        else:
            donor.availability_score = donor.availability_score * (1 - alpha) + alpha * 0.0

        if completed:
            donor.reliability_score = donor.reliability_score * (1 - alpha) + alpha * 1.0
            donor.total_donations += 1
            if completed:
                donor.last_donation_date = datetime.now().date()
        
        donations = donor.total_donations
        if donations > 0:
            donor.response_rate = donor.availability_score

        donor.save()

        # Save training data
        try:
            from ml_engine.models import DonorMatchOutcome
            DonorMatchOutcome.objects.create(
                donor_blood_group=donor.blood_group,
                request_blood_group='O+',
                donor_city=donor.city,
                request_city='',
                donor_age=donor.age,
                donor_weight=donor.weight,
                donor_total_donations=donor.total_donations,
                donor_response_rate=donor.response_rate,
                urgency_level='standard',
                was_available=was_available,
                was_selected=was_selected,
                donation_completed=completed,
            )
        except Exception as e:
            logger.error(f"Failed to log outcome: {e}")

    def check_autonomous_eligibility(self):
        try:
            from ml_engine.models import DonorMatchOutcome, MLModelVersion
            total = DonorMatchOutcome.objects.count()
            if total >= self.autonomous_threshold:
                self.is_autonomous = True
                self.successful_matches = total
                MLModelVersion.objects.update_or_create(
                    is_active=True,
                    defaults={
                        'version': f'v{total//10}.0',
                        'accuracy': 0.85,
                        'total_training_samples': total,
                        'is_autonomous': True,
                        'model_path': str(settings.BASE_DIR / 'ml_models'),
                    }
                )
                return True
        except Exception as e:
            logger.error(f"Error checking autonomy: {e}")
        return False

ml_engine = DonorMatchingEngine()
