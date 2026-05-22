from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from .models import BloodRequest, RequestDonorMatch
from .serializers import BloodRequestSerializer, BloodRequestCreateSerializer, RequestDonorMatchSerializer
from hospitals.models import Hospital
from donors.models import Donor
from core.n8n_client import n8n_client
from ml_engine.engine import ml_engine
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def blood_requests_list_create(request):
    try:
        hospital = request.user.hospital
    except Hospital.DoesNotExist:
        return Response({'error': 'Create hospital profile first'}, status=400)

    if request.method == 'GET':
        requests_qs = BloodRequest.objects.filter(hospital=hospital)
        status_filter = request.query_params.get('status')
        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)
        return Response(BloodRequestSerializer(requests_qs, many=True).data)

    if request.method == 'POST':
        serializer = BloodRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        blood_request = serializer.save(hospital=hospital, status='pending')
        hospital.total_requests += 1
        hospital.save()

        # Decide: ML autonomous or send to N8N
        use_ml = ml_engine.should_use_autonomous_mode()

        if use_ml:
            blood_request.status = 'ml_processing'
            blood_request.handled_by_ml = True
            blood_request.save()

            scored_donors = ml_engine.find_best_donors(blood_request, limit=10)
            for donor, score in scored_donors:
                RequestDonorMatch.objects.create(
                    request=blood_request,
                    donor=donor,
                    match_score=score,
                    status='proposed'
                )
            
            blood_request.status = 'donors_found'
            blood_request.ml_confidence_score = scored_donors[0][1] if scored_donors else 0
            blood_request.save()

            return Response({
                'request': BloodRequestSerializer(blood_request).data,
                'handled_by': 'ml',
                'donors_count': len(scored_donors),
            }, status=201)
        else:
            # Send to N8N
            blood_request.status = 'sent_to_n8n'
            blood_request.save()

            n8n_response = n8n_client.send_blood_request(blood_request, hospital)
            
            if n8n_response.get('success'):
                blood_request.n8n_execution_id = n8n_response.get('execution_id')
                blood_request.save()

                # If mock (N8N not connected), use ML as fallback
                if n8n_response.get('mock'):
                    scored_donors = ml_engine.find_best_donors(blood_request, limit=10)
                    for donor, score in scored_donors[:5]:
                        RequestDonorMatch.objects.create(
                            request=blood_request,
                            donor=donor,
                            match_score=score,
                            status='proposed'
                        )
                    blood_request.status = 'donors_found'
                    blood_request.save()

            return Response({
                'request': BloodRequestSerializer(blood_request).data,
                'handled_by': 'n8n',
                'n8n_response': n8n_response,
            }, status=201)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def blood_request_detail(request, pk):
    try:
        blood_request = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    return Response(BloodRequestSerializer(blood_request).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_donors(request, pk):
    try:
        blood_request = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    
    matches = RequestDonorMatch.objects.filter(request=blood_request).order_by('-match_score')
    return Response({
        'request': BloodRequestSerializer(blood_request).data,
        'donors': RequestDonorMatchSerializer(matches, many=True).data,
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_donor_availability(request, pk, match_id):
    try:
        blood_request = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(pk=match_id, request=blood_request)
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    match.status = 'availability_checking'
    match.save()

    result = n8n_client.verify_donor_availability(match.donor, pk)
    is_available = result.get('available', False)
    
    match.is_available = is_available
    match.availability_checked_at = timezone.now()
    match.status = 'available' if is_available else 'unavailable'
    match.save()

    ml_engine.update_donor_scores(match.donor, is_available, False, False)
    ml_engine.check_autonomous_eligibility()

    return Response({
        'match': RequestDonorMatchSerializer(match).data,
        'is_available': is_available,
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_donor(request, pk, match_id):
    try:
        blood_request = BloodRequest.objects.get(pk=pk, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(pk=match_id, request=blood_request)
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Not found'}, status=404)

    # Reject other matches
    RequestDonorMatch.objects.filter(request=blood_request).exclude(pk=match_id).update(status='rejected')
    
    match.status = 'selected'
    match.selected_at = timezone.now()
    match.save()

    blood_request.status = 'donor_selected'
    blood_request.save()

    return Response({
        'request': BloodRequestSerializer(blood_request).data,
        'selected_match': RequestDonorMatchSerializer(match).data,
        'donor_payment_details': {
            'bank_name': match.donor.bank_name,
            'account_number': match.donor.account_number,
            'account_name': match.donor.account_name,
        }
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def n8n_webhook_donors_found(request):
    """Webhook endpoint for N8N to push donor results back"""
    request_id = request.data.get('request_id')
    donors_data = request.data.get('donors', [])
    
    try:
        blood_request = BloodRequest.objects.get(pk=request_id)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)

    for d in donors_data:
        donor, created = Donor.objects.get_or_create(
            email=d.get('email', ''),
            defaults={
                'first_name': d.get('first_name', ''),
                'last_name': d.get('last_name', ''),
                'phone': d.get('phone', ''),
                'blood_group': d.get('blood_group', ''),
                'age': d.get('age', 25),
                'weight': d.get('weight', 70),
                'city': d.get('city', ''),
                'state': d.get('state', ''),
                'bank_name': d.get('bank_name', ''),
                'account_number': d.get('account_number', ''),
                'account_name': d.get('account_name', ''),
                'n8n_donor_id': d.get('n8n_id', ''),
                'source': 'n8n',
            }
        )
        
        RequestDonorMatch.objects.get_or_create(
            request=blood_request,
            donor=donor,
            defaults={'match_score': d.get('score', 0.7), 'status': 'proposed'}
        )

    blood_request.status = 'donors_found'
    blood_request.save()

    return Response({'status': 'ok', 'donors_added': len(donors_data)})
