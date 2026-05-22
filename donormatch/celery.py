# ============================================================
# DonorMatch — Celery Configuration
# ============================================================
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'donormatch.settings')

app = Celery('donormatch')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Periodic Tasks (ML retraining, availability checks) ──────
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Retrain ML model every night at 2am
    'retrain-ml-nightly': {
        'task': 'ml_engine.tasks.retrain_model',
        'schedule': crontab(hour=2, minute=0),
    },
    # Check autonomous mode eligibility every hour
    'check-autonomy': {
        'task': 'ml_engine.tasks.check_autonomous_eligibility',
        'schedule': crontab(minute=0),
    },
    # Refresh donor availability scores daily at 6am
    'refresh-donor-scores': {
        'task': 'ml_engine.tasks.refresh_donor_scores',
        'schedule': crontab(hour=6, minute=0),
    },
}
