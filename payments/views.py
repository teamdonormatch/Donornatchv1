import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import Payment
from .serializers import PaymentSerializer, PaymentCreateSerializer
from blood_requests.models import BloodRequest, RequestDonorMatch
from blood_requests.serializers import BloodRequestSerializer
from core.n8n_client import n8n_client
from ml_engine.engine import ml_engine

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request, request_id):
    try:
        br    = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        match = RequestDonorMatch.objects.get(request=br, status='selected')
    except (BloodRequest.DoesNotExist, RequestDonorMatch.DoesNotExist):
        return Response({'error': 'Request or selected donor not found'}, status=404)

    if hasattr(br, 'payment'):
        return Response({'error': 'Payment already initiated'}, status=400)

    serializer = PaymentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    donor = match.donor
    payment = serializer.save(
        request=br,
        match=match,
        hospital=request.user.hospital,
        donor=donor,
        recipient_bank=donor.bank_name,
        recipient_account=donor.account_number,
        recipient_name=donor.account_name,
        status='pending',
    )

    br.status = 'payment_pending'
    br.save()

    return Response(PaymentSerializer(payment).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_payment(request, request_id):
    try:
        br      = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        payment = br.payment
    except (BloodRequest.DoesNotExist, Exception):
        return Response({'error': 'Payment not found'}, status=404)

    reference = request.data.get('transfer_reference', payment.transfer_reference)
    payment.transfer_reference = reference
    payment.status             = 'confirmed'
    payment.confirmed_at       = timezone.now()
    payment.save()

    br.status = 'payment_confirmed'
    br.save()

    # Fire webhook to n8n — notify the donor, no callback needed
    n8n_client.notify_selected_donor(
        donor=payment.donor,
        hospital=request.user.hospital,
        amount=payment.amount,
        reference=reference,
    )

    return Response(PaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_session(request, request_id):
    try:
        br = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
    except BloodRequest.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    br.status       = 'completed'
    br.completed_at = timezone.now()
    br.save()

    hospital = request.user.hospital
    hospital.successful_matches += 1
    hospital.save()

    try:
        match = RequestDonorMatch.objects.get(request=br, status='selected')
        ml_engine.update_donor_scores(match.donor, True, True, True)
        ml_engine.check_autonomous_eligibility()
    except RequestDonorMatch.DoesNotExist:
        pass

    return Response({
        'message': 'Session closed successfully',
        'request': BloodRequestSerializer(br).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_detail(request, request_id):
    try:
        br      = BloodRequest.objects.get(pk=request_id, hospital=request.user.hospital)
        payment = br.payment
    except (BloodRequest.DoesNotExist, Exception):
        return Response({'error': 'Not found'}, status=404)
    return Response(PaymentSerializer(payment).data)
