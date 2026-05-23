import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class N8NWebhookClient:
    """
    All communication with n8n is pure webhooks.
    App fires POST to n8n and forgets.
    N8N calls back to the app's inbound webhook endpoints with results.
    """

    def __init__(self):
        # The n8n worker gave us this base:
        # https://donormatch.app.n8n.cloud/webhook-test/emergency-blood-request
        # So base = https://donormatch.app.n8n.cloud/webhook-test
        self.base_url = getattr(settings, 'N8N_WEBHOOK_URL', 
                                 'https://donormatch.app.n8n.cloud/webhook-test').rstrip('/')
        self.app_url  = getattr(settings, 'BASE_URL', 
                                 'http://localhost:8000').rstrip('/')
        self.timeout  = 10  # fire-and-forget, short timeout

    def _post(self, path, payload):
        url = f'{self.base_url}/{path.lstrip("/")}'
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            logger.info(f'N8N webhook → {url} : {resp.status_code}')
            return resp.status_code in (200, 201, 202)
        except requests.exceptions.ConnectionError:
            logger.warning(f'N8N not reachable at {url}')
            return False
        except Exception as e:
            logger.error(f'N8N webhook error: {e}')
            return False

    def send_blood_request(self, blood_request, hospital):
        """
        App → N8N
        Fires to: {base}/emergency-blood-request
        N8N calls back to: {app_url}/webhook/n8n/donors-found/
        """
        return self._post('emergency-blood-request', {
            'request_id':        blood_request.id,
            'blood_group':       blood_request.blood_group,
            'units_needed':      blood_request.units_needed,
            'urgency':           blood_request.urgency,
            'hospital_name':     hospital.name,
            'hospital_city':     hospital.city,
            'hospital_state':    hospital.state,
            'hospital_phone':    hospital.phone,
            'patient_condition': blood_request.patient_condition,
            'callback_url':      f'{self.app_url}/webhook/n8n/donors-found/',
        })

    def request_availability_check(self, match):
        """
        App → N8N
        Fires to: {base}/check-donor-availability
        N8N calls back to: {app_url}/webhook/n8n/availability-result/
        """
        donor = match.donor
        return self._post('check-donor-availability', {
            'match_id':     match.id,
            'donor_id':     donor.id,
            'donor_phone':  donor.phone,
            'donor_name':   f'{donor.first_name} {donor.last_name}',
            'blood_group':  donor.blood_group,
            'callback_url': f'{self.app_url}/webhook/n8n/availability-result/',
        })

    def notify_selected_donor(self, donor, hospital, amount, reference):
        """
        App → N8N
        Fires to: {base}/notify-donor
        No callback needed.
        """
        return self._post('notify-donor', {
            'donor_name':        f'{donor.first_name} {donor.last_name}',
            'donor_phone':       donor.phone,
            'hospital_name':     hospital.name,
            'hospital_address':  hospital.address,
            'payment_amount':    str(amount),
            'payment_reference': reference,
        })


n8n_client = N8NWebhookClient()