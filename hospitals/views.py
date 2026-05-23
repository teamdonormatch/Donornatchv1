from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

# Model and Serializer Imports
from .models import Hospital
from .serializers import HospitalSerializer, HospitalCreateSerializer


# ==========================================
# 🔓 PUBLIC GUEST ENDPOINTS (Fixes 401 Error)
# ==========================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_hospital_user(request):
    """
    Handles registering a new User account.
    Open to the public; bypasses global authentication settings.
    """
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')

    if not username or not password or not email:
        return Response(
            {'error': 'Username, email, and password are required fields.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'A user with that username already exists.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Create user instance
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        return Response(
            {
                'message': 'Account created successfully.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            }, 
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        return Response(
            {'error': f'Registration failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login_hospital_user(request):
    """
    Authenticates user credentials and initiates a session.
    Open to the public; bypasses global authentication settings.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'Please provide both username and password.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        return Response(
            {
                'message': 'Login successful.',
                'username': user.username,
                'has_profile': hasattr(user, 'hospital')
            },
            status=status.HTTP_200_OK
        )
    
    return Response(
        {'error': 'Invalid username or password credentials.'}, 
        status=status.HTTP_401_UNAUTHORIZED
    )


# ==========================================
# 🔒 PROTECTED PROFILE ENDPOINTS 
# ==========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_hospital_profile(request):
    """
    Creates a detailed sub-profile linked to the logged-in user.
    """
    if hasattr(request.user, 'hospital'):
        return Response(
            {'error': 'Hospital profile already exists for this user account.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    serializer = HospitalCreateSerializer(data=request.data)
    if serializer.is_valid():
        hospital = serializer.save(user=request.user)
        return Response(HospitalSerializer(hospital).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def hospital_profile(request):
    """
    Retrieves, updates completely, or patch updates the hospital settings.
    """
    try:
        hospital = request.user.hospital
    except ObjectDoesNotExist:
        return Response(
            {'error': 'Hospital setup profile not found.'}, 
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        return Response(HospitalSerializer(hospital).data)
    
    # partial=True is isolated strictly to PATCH requests
    is_partial = (request.method == 'PATCH')
    serializer = HospitalCreateSerializer(hospital, data=request.data, partial=is_partial)
    
    if serializer.is_valid():
        updated_hospital = serializer.save()
        return Response(HospitalSerializer(updated_hospital).data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
