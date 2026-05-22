from rest_framework import serializers
from .models import BloodRequest, RequestDonorMatch
from donors.serializers import DonorSerializer

class RequestDonorMatchSerializer(serializers.ModelSerializer):
    donor = DonorSerializer(read_only=True)

    class Meta:
        model = RequestDonorMatch
        fields = '__all__'

class BloodRequestSerializer(serializers.ModelSerializer):
    donor_matches = RequestDonorMatchSerializer(many=True, read_only=True)

    class Meta:
        model = BloodRequest
        fields = '__all__'
        read_only_fields = ['hospital', 'status', 'n8n_workflow_id', 'n8n_execution_id', 'handled_by_ml']

class BloodRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodRequest
        fields = ['blood_group', 'units_needed', 'urgency', 'patient_name', 'patient_condition', 'notes']
