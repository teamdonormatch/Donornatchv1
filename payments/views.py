from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import Payment
from .serializers import PaymentSerializer, PaymentCreateSerializer
from blood_requests.models import BloodRequest, RequestDonorMatch
from blood_requests.serializers import BloodRequestSerializer
from ml_engine.engine import ml_engine
from hospitals.models import Hospital

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request, request_id):
    try:
        blood_request = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(request=blood_request, status='selected')
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Request or selected donor not found'}, status=404)

    if hasattr(blood_request, 'payment'):
        return Response({'error': 'Payment already initiated'}, status=400)

    donor = match.donor
    serializer = PaymentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    payment = serializer.save(
        request=blood_request,
        match=match,
        hospital=request.user.hospital,
        donor=donor,
        recipient_bank=donor.bank_name,
        recipient_account=donor.account_number,
        recipient_name=donor.account_name,
        status='pending',
    )

    blood_request.status = 'payment_pending'
    blood_request.save()

    return Response(PaymentSerializer(payment).data, status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_payment(request, request_id):
    try:
        blood_request = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        payment = blood_request.payment
    except (BloodRequest.DoesNotExist, Payment.DoesNotExist, AttributeError):
        return Response({'error': 'Payment not found'}, status=404)

    transfer_reference = request.data.get('transfer_reference', payment.transfer_reference)
    payment.transfer_reference = transfer_reference
    payment.status = 'confirmed'
    payment.confirmed_at = timezone.now()
    payment.save()

    blood_request.status = 'payment_confirmed'
    blood_request.save()

    # Notify donor via N8N
    from core.n8n_client import n8n_client
    match = payment.match
    n8n_client.notify_selected_donor(
        payment.donor,
        request.user.hospital,
        {'amount': str(payment.amount), 'reference': transfer_reference}
    )

    return Response(PaymentSerializer(payment).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_session(request, request_id):
    try:
        blood_request = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    blood_request.status = 'completed'
    blood_request.completed_at = timezone.now()
    blood_request.save()

    hospital = request.user.hospital
    hospital.successful_matches += 1
    hospital.save()

    # Update ML scores
    try:
        match = RequestDonorMatch.objects.get(request=blood_request, status='selected')
        ml_engine.update_donor_scores(match.donor, True, True, True)
        ml_engine.check_autonomous_eligibility()
    except RequestDonorMatch.DoesNotExist:
        pass

    return Response({
        'message': 'Session closed successfully',
        'request': BloodRequestSerializer(blood_request).data,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_detail(request, request_id):
    try:
        blood_request = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        payment = blood_request.payment
    except (BloodRequest.DoesNotExist, Exception):
        return Response({'error': 'Not found'}, status=404)
    return Response(PaymentSerializer(payment).data)
