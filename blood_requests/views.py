import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import BloodRequest, RequestDonorMatch
from .serializers import (BloodRequestSerializer, BloodRequestCreateSerializer,
                           RequestDonorMatchSerializer)
from hospitals.models import Hospital
from core.n8n_client import n8n_client
from ml_engine.engine import ml_engine

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def blood_requests_list_create(request):
    try:
        hospital = request.user.hospital
    except Hospital.DoesNotExist:
        return Response({'error': 'Create hospital profile first'}, status=400)

    if request.method == 'GET':
        qs = BloodRequest.objects.filter(hospital=hospital)
        s  = request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)
        return Response(BloodRequestSerializer(qs, many=True).data)

    serializer = BloodRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    blood_request = serializer.save(hospital=hospital, status='pending')
    hospital.total_requests += 1
    hospital.save()

    if ml_engine.should_use_autonomous_mode():
        # AI handles it — no n8n needed
        blood_request.status        = 'ml_processing'
        blood_request.handled_by_ml = True
        blood_request.save()

        scored = ml_engine.find_best_donors(blood_request, limit=10)
        for donor, score in scored:
            RequestDonorMatch.objects.create(
                request=blood_request, donor=donor,
                match_score=score, status='proposed'
            )
        blood_request.status              = 'donors_found'
        blood_request.ml_confidence_score = scored[0][1] if scored else 0
        blood_request.save()

        return Response({
            'request':     BloodRequestSerializer(blood_request).data,
            'handled_by':  'ml',
            'donors_found': len(scored),
        }, status=201)

    # Fire webhook to n8n — response comes back async to /webhook/n8n/donors-found/
    blood_request.status = 'sent_to_n8n'
    blood_request.save()
    n8n_client.send_blood_request(blood_request, hospital)

    return Response({
        'request':    BloodRequestSerializer(blood_request).data,
        'handled_by': 'n8n',
        'message':    'Request sent to N8N. Donors will appear once N8N responds.',
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def blood_request_detail(request, pk):
    try:
        br = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    return Response(BloodRequestSerializer(br).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_donors(request, pk):
    try:
        br = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    matches = RequestDonorMatch.objects.filter(request=br).order_by('-match_score')
    return Response({
        'request': BloodRequestSerializer(br).data,
        'donors':  RequestDonorMatchSerializer(matches, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_donor_availability(request, pk, match_id):
    """
    Fires webhook to n8n asking it to contact donor.
    N8N calls back to /webhook/n8n/availability-result/ when donor responds.
    Frontend polls every 4s for the status change.
    """
    try:
        br    = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(pk=match_id, request=br)
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    match.status = 'availability_checking'
    match.save()

    n8n_client.request_availability_check(match)

    return Response({
        'match':   RequestDonorMatchSerializer(match).data,
        'message': 'Availability check sent to N8N. Result updates automatically.',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_donor(request, pk, match_id):
    try:
        br    = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(pk=match_id, request=br)
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    RequestDonorMatch.objects.filter(request=br).exclude(pk=match_id).update(status='rejected')
    match.status      = 'selected'
    match.selected_at = timezone.now()
    match.save()

    br.status = 'donor_selected'
    br.save()

    return Response({
        'request':        BloodRequestSerializer(br).data,
        'selected_match': RequestDonorMatchSerializer(match).data,
        'donor_payment_details': {
            'bank_name':      match.donor.bank_name,
            'account_number': match.donor.account_number,
            'account_name':   match.donor.account_name,
        }
    })
