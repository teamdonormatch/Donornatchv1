from rest_framework import serializers
from .models import Hospital
from core.serializers import UserSerializer

class HospitalSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Hospital
        fields = '__all__'
        read_only_fields = ['user', 'is_verified', 'total_requests', 'successful_matches']

class HospitalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        exclude = ['user', 'is_verified', 'total_requests', 'successful_matches']
