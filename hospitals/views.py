from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Hospital
from .serializers import HospitalSerializer, HospitalCreateSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_hospital_profile(request):
    if hasattr(request.user, 'hospital'):
        return Response({'error': 'Hospital profile already exists'}, status=400)
    serializer = HospitalCreateSerializer(data=request.data)
    if serializer.is_valid():
        hospital = serializer.save(user=request.user)
        return Response(HospitalSerializer(hospital).data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def hospital_profile(request):
    try:
        hospital = request.user.hospital
    except Hospital.DoesNotExist:
        return Response({'error': 'Hospital profile not found'}, status=404)

    if request.method == 'GET':
        return Response(HospitalSerializer(hospital).data)
    
    serializer = HospitalCreateSerializer(hospital, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(HospitalSerializer(hospital).data)
    return Response(serializer.errors, status=400)
