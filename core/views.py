from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from hospitals.models import Hospital
from hospitals.serializers import HospitalSerializer
from ml_engine.models import SystemStats, MLModelVersion, DonorMatchOutcome
from donors.models import Donor
from blood_requests.models import BloodRequest
from django.utils import timezone
from datetime import date

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Registration successful',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        hospital = None
        try:
            hospital = HospitalSerializer(user.hospital).data
        except:
            pass
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'hospital': hospital,
        })
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    hospital = None
    try:
        hospital = HospitalSerializer(request.user.hospital).data
    except:
        pass
    return Response({
        'user': UserSerializer(request.user).data,
        'hospital': hospital,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    try:
        hospital = request.user.hospital
        requests_qs = BloodRequest.objects.filter(hospital=hospital)
        total = requests_qs.count()
        completed = requests_qs.filter(status='completed').count()
        pending = requests_qs.filter(status__in=['pending', 'sent_to_n8n', 'ml_processing', 'donors_found']).count()
        
        ml_count = DonorMatchOutcome.objects.count()
        is_autonomous = ml_count >= 50

        from blood_requests.models import RequestDonorMatch
        recent_requests = BloodRequest.objects.filter(hospital=hospital).order_by('-created_at')[:5]
        
        from blood_requests.serializers import BloodRequestSerializer
        
        return Response({
            'total_requests': total,
            'completed_requests': completed,
            'pending_requests': pending,
            'success_rate': round((completed / total * 100) if total > 0 else 0, 1),
            'ml_training_data': ml_count,
            'ml_autonomous_mode': is_autonomous,
            'ml_threshold': 50,
            'recent_requests': BloodRequestSerializer(recent_requests, many=True).data,
        })
    except Hospital.DoesNotExist:
        return Response({'error': 'Hospital profile not found'}, status=404)
