# ============================================================
# DonorMatch — Celery ML Background Tasks
# ============================================================
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('ml_engine')


@shared_task(name='ml_engine.tasks.retrain_model', bind=True, max_retries=2)
def retrain_model(self):
    """
    Nightly task: retrain the donor-matching model from all
    accumulated DonorMatchOutcome records.
    """
    try:
        from ml_engine.models import DonorMatchOutcome, MLModelVersion
        from ml_engine.engine import ml_engine

        outcomes = DonorMatchOutcome.objects.all()
        total = outcomes.count()
        if total < 10:
            logger.info(f'retrain_model: only {total} samples — skipping')
            return {'status': 'skipped', 'reason': 'insufficient data', 'samples': total}

        # Feature matrix
        import numpy as np
        features, labels = [], []
        for o in outcomes:
            features.append([
                o.donor_age,
                o.donor_weight,
                o.donor_total_donations,
                o.donor_response_rate,
                1 if o.donor_city == o.request_city else 0,
                1 if o.donor_blood_group == o.request_blood_group else 0,
                {'standard': 0, 'urgent': 1, 'critical': 2}.get(o.urgency_level, 0),
            ])
            labels.append(int(o.donation_completed))

        X = np.array(features, dtype=float)
        y = np.array(labels)

        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        import joblib
        from django.conf import settings

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        clf = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
        clf.fit(X_train, y_train)
        accuracy = clf.score(X_test, y_test)

        # Persist
        model_path = settings.ML_MODEL_PATH
        model_path.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, model_path / 'donor_match_model.pkl')
        joblib.dump(scaler, model_path / 'scaler.pkl')

        version = f'v{total // 10}.{total % 10}'
        MLModelVersion.objects.filter(is_active=True).update(is_active=False)
        MLModelVersion.objects.create(
            version=version,
            accuracy=round(accuracy, 4),
            total_training_samples=total,
            is_active=True,
            is_autonomous=total >= settings.ML_AUTONOMOUS_MODE_THRESHOLD,
            model_path=str(model_path),
            training_notes=f'Trained on {total} samples. Accuracy: {accuracy:.2%}',
        )

        ml_engine.is_autonomous = (total >= settings.ML_AUTONOMOUS_MODE_THRESHOLD)
        ml_engine.successful_matches = total
        logger.info(f'retrain_model: done — {total} samples, accuracy={accuracy:.2%}')
        return {'status': 'success', 'samples': total, 'accuracy': accuracy, 'version': version}

    except Exception as exc:
        logger.error(f'retrain_model failed: {exc}', exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='ml_engine.tasks.check_autonomous_eligibility')
def check_autonomous_eligibility():
    """Hourly: flip to autonomous mode once threshold is reached."""
    from ml_engine.engine import ml_engine
    ml_engine.check_autonomous_eligibility()
    return {'autonomous': ml_engine.is_autonomous, 'matches': ml_engine.successful_matches}


@shared_task(name='ml_engine.tasks.refresh_donor_scores')
def refresh_donor_scores():
    """
    Daily: recalculate availability & reliability scores for all
    active donors using recent availability log data.
    """
    from donors.models import Donor, DonorAvailabilityLog

    updated = 0
    for donor in Donor.objects.filter(status='active'):
        logs = DonorAvailabilityLog.objects.filter(donor=donor).order_by('-checked_at')[:20]
        if not logs:
            continue
        avail_rate = logs.filter(is_available=True).count() / logs.count()
        donor.availability_score = round(avail_rate, 4)
        donor.save(update_fields=['availability_score', 'updated_at'])
        updated += 1

    logger.info(f'refresh_donor_scores: updated {updated} donors')
    return {'updated': updated}


@shared_task(name='ml_engine.tasks.batch_availability_check')
def batch_availability_check(request_id):
    """
    Triggered after donors are found: call N8N to verify availability
    for all proposed matches in parallel (one subtask each).
    """
    from blood_requests.models import RequestDonorMatch
    from core.n8n_client import n8n_client
    from django.utils import timezone

    matches = RequestDonorMatch.objects.filter(
        request_id=request_id, status='proposed'
    ).select_related('donor')

    results = []
    for match in matches:
        try:
            result = n8n_client.verify_donor_availability(match.donor, request_id)
            is_available = result.get('available', False)
            match.is_available = is_available
            match.availability_checked_at = timezone.now()
            match.status = 'available' if is_available else 'unavailable'
            match.save()
            results.append({'donor_id': match.donor.id, 'available': is_available})
        except Exception as e:
            logger.error(f'Availability check failed for donor {match.donor.id}: {e}')

    return {'request_id': request_id, 'results': results}
