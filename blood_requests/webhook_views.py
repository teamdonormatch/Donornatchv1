"""
Inbound webhooks — N8N calls these endpoints with results.
No auth required. Returns immediately so n8n never times out.
"""
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .models import BloodRequest, RequestDonorMatch
from donors.models import Donor
from ml_engine.engine import ml_engine

logger = logging.getLogger(__name__)


def _body(request):
    try:
        return json.loads(request.body)
    except Exception:
        return {}


@csrf_exempt
@require_POST
def donors_found(request):
    """
    N8N calls this after finding donors.

    N8N sends:
    {
        "request_id": 42,
        "donors": [
            {
                "first_name": "Chidi",
                "last_name": "Okonkwo",
                "email": "chidi@example.com",
                "phone": "+2348012345678",
                "blood_group": "O+",
                "age": 28,
                "weight": 72,
                "city": "Lagos",
                "state": "Lagos",
                "bank_name": "GTBank",
                "account_number": "0123456789",
                "account_name": "Chidi Okonkwo",
                "score": 0.88
            }
        ]
    }
    """
    data = _body(request)
    request_id  = data.get('request_id')
    donors_data = data.get('donors', [])

    if not request_id:
        return JsonResponse({'error': 'request_id required'}, status=400)

    try:
        blood_request = BloodRequest.objects.get(pk=request_id)
    except BloodRequest.DoesNotExist:
        return JsonResponse({'error': 'request not found'}, status=404)

    saved = 0
    for d in donors_data:
        email = d.get('email', '').strip()
        if not email:
            continue

        donor, _ = Donor.objects.get_or_create(
            email=email,
            defaults={
                'first_name':     d.get('first_name', ''),
                'last_name':      d.get('last_name', ''),
                'phone':          d.get('phone', ''),
                'blood_group':    d.get('blood_group', ''),
                'age':            int(d.get('age', 25)),
                'weight':         float(d.get('weight', 70)),
                'city':           d.get('city', ''),
                'state':          d.get('state', ''),
                'bank_name':      d.get('bank_name', ''),
                'account_number': d.get('account_number', ''),
                'account_name':   d.get('account_name', ''),
                'n8n_donor_id':   str(d.get('n8n_id', '')),
                'source':         'n8n',
            }
        )

        RequestDonorMatch.objects.get_or_create(
            request=blood_request,
            donor=donor,
            defaults={
                'match_score': float(d.get('score', 0.7)),
                'status':      'proposed',
            }
        )
        saved += 1

    blood_request.status = 'donors_found'
    blood_request.save()

    logger.info(f'donors_found webhook: request {request_id} — {saved} donors saved')
    return JsonResponse({'status': 'ok', 'donors_saved': saved})


@csrf_exempt
@require_POST
def availability_result(request):
    """
    N8N calls this after contacting a donor.

    N8N sends:
    {
        "match_id": 15,
        "available": true,
        "notes": "Donor confirmed via SMS"
    }
    """
    data        = _body(request)
    match_id    = data.get('match_id')
    is_available = bool(data.get('available', False))
    notes       = data.get('notes', '')

    if not match_id:
        return JsonResponse({'error': 'match_id required'}, status=400)

    try:
        match = RequestDonorMatch.objects.select_related('donor').get(pk=match_id)
    except RequestDonorMatch.DoesNotExist:
        return JsonResponse({'error': 'match not found'}, status=404)

    from django.utils import timezone
    match.is_available           = is_available
    match.availability_checked_at = timezone.now()
    match.status                 = 'available' if is_available else 'unavailable'
    match.notes                  = notes
    match.save()

    ml_engine.update_donor_scores(match.donor, is_available, False, False)
    ml_engine.check_autonomous_eligibility()

    logger.info(f'availability_result webhook: match {match_id} — available={is_available}')
    return JsonResponse({'status': 'ok', 'match_id': match_id, 'available': is_available})