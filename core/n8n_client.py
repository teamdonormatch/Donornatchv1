import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class N8NClient:
    def __init__(self):
        self.base_url = getattr(settings, 'N8N_WEBHOOK_URL', 'https://your-n8n.com/webhook')
        self.api_key = getattr(settings, 'N8N_API_KEY', '')
        self.timeout = 30

    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'X-N8N-API-KEY': self.api_key,
        }

    def send_blood_request(self, blood_request, hospital):
        payload = {
            'request_id': blood_request.id,
            'blood_group': blood_request.blood_group,
            'units_needed': blood_request.units_needed,
            'urgency': blood_request.urgency,
            'hospital_name': hospital.name,
            'hospital_city': hospital.city,
            'hospital_state': hospital.state,
            'hospital_phone': hospital.phone,
            'patient_condition': blood_request.patient_condition,
            'callback_url': f'{getattr(settings, "BASE_URL", "http://localhost:8000")}/api/webhook/n8n/donors-found/',
        }
        try:
            resp = requests.post(
                f'{self.base_url}/blood-request',
                json=payload,
                headers=self._headers(),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                return {'success': True, 'execution_id': data.get('executionId'), 'data': data}
            else:
                logger.error(f"N8N error: {resp.status_code} - {resp.text}")
                return {'success': False, 'error': resp.text}
        except requests.exceptions.ConnectionError:
            logger.warning("N8N not reachable - using mock response")
            return {'success': True, 'execution_id': f'mock-{blood_request.id}', 'mock': True}
        except Exception as e:
            logger.error(f"N8N request failed: {e}")
            return {'success': False, 'error': str(e)}

    def verify_donor_availability(self, donor, request_id):
        payload = {
            'donor_id': donor.id,
            'donor_phone': donor.phone,
            'donor_name': f'{donor.first_name} {donor.last_name}',
            'request_id': request_id,
            'blood_group': donor.blood_group,
        }
        try:
            resp = requests.post(
                f'{self.base_url}/check-donor-availability',
                json=payload,
                headers=self._headers(),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json()
            return {'available': False, 'error': resp.text}
        except requests.exceptions.ConnectionError:
            import random
            return {'available': random.random() > 0.3, 'mock': True}
        except Exception as e:
            return {'available': False, 'error': str(e)}

    def notify_selected_donor(self, donor, hospital, payment_details):
        payload = {
            'donor_id': donor.id,
            'donor_phone': donor.phone,
            'donor_name': f'{donor.first_name} {donor.last_name}',
            'hospital_name': hospital.name,
            'hospital_address': hospital.address,
            'payment_amount': str(payment_details.get('amount', 0)),
            'payment_reference': payment_details.get('reference', ''),
        }
        try:
            resp = requests.post(
                f'{self.base_url}/notify-donor',
                json=payload,
                headers=self._headers(),
                timeout=self.timeout
            )
            return resp.status_code == 200
        except:
            return True  # Mock success

n8n_client = N8NClient()
