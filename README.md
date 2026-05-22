# 🩸 DonorMatch — Smart Blood Donor Matching Platform

AI-powered Django application connecting hospitals with blood donors through intelligent matching, n8n workflow integration, and a self-learning ML engine.

---

## ✨ Features

- **Hospital Auth** — Secure JWT login/signup for hospital accounts
- **Blood Request Management** — Submit, track, and manage blood requests
- **N8N Workflow Integration** — Push/pull donor data from n8n automations
- **Self-Learning AI Engine** — ML model that trains on every match, eventually going fully autonomous
- **Real-time Availability Checks** — Verify each donor via n8n call before presenting to hospital
- **Donor Selection UI** — Hospital reviews scored donors, picks the best match
- **Bank Transfer Payments** — Complete payment flow with transfer confirmation
- **Session Management** — Request sessions close cleanly after payment + confirmation
- **Background Tasks** — Celery workers for nightly ML retraining and donor score refreshes

---

## 🚀 Quick Start (Docker — Recommended)

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env — set SECRET_KEY, N8N_WEBHOOK_URL, etc.

# 2. Build & launch
docker compose up --build -d

# 3. Create superuser (optional)
docker compose exec web python manage.py createsuperuser

# 4. Open in browser
open http://localhost
```

**Demo login:** `demo` / `demo1234`

---

## 🛠 Local Development (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set up DB & seed demo data
python manage.py migrate
python manage.py shell < seed_demo.py  # or run the server; demo data auto-created

# Start Django
python manage.py runserver

# (Optional) Start Celery worker for background ML tasks
celery -A donormatch worker --loglevel=info

# (Optional) Start Celery Beat for periodic tasks
celery -A donormatch beat --loglevel=info
```

---

## 🔗 N8N Integration

### How it Works
1. Hospital submits a blood request
2. App POSTs to `{N8N_WEBHOOK_URL}/blood-request` with request details + a `callback_url`
3. N8N finds donors and POSTs them back to `callback_url` → `/api/webhook/n8n/donors-found/`
4. App stores donors, scores them, displays to hospital

### Configure
Set in `.env`:
```
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/your-workflow-id
N8N_API_KEY=your-api-key
```

### Webhook Payload (App → N8N)
```json
{
  "request_id": 42,
  "blood_group": "O+",
  "units_needed": 2,
  "urgency": "urgent",
  "hospital_name": "Lagos General Hospital",
  "hospital_city": "Lagos",
  "hospital_phone": "+234801...",
  "callback_url": "https://yourapp.com/api/webhook/n8n/donors-found/"
}
```

### Callback Payload (N8N → App)
```json
{
  "request_id": 42,
  "donors": [
    {
      "first_name": "Chidi",
      "last_name": "Okonkwo",
      "email": "chidi@example.com",
      "phone": "+2348012345678",
      "blood_group": "O+",
      "age": 28,
      "weight": 72,
      "city": "Lagos",
      "state": "Lagos",
      "bank_name": "GTBank",
      "account_number": "0123456789",
      "account_name": "Chidi Okonkwo",
      "n8n_id": "n8n-donor-uuid",
      "score": 0.88
    }
  ]
}
```

---

## 🧠 ML Autonomous Mode

The AI engine goes through three phases:

| Phase | Trigger | Behaviour |
|-------|---------|-----------|
| **N8N Mode** | Default | All requests sent to n8n; outcomes stored |
| **Hybrid Mode** | 25+ matches | ML scores donors; n8n still used |
| **Autonomous Mode** | 50+ matches | ML bypasses n8n; finds donors from internal DB |

Nightly retraining runs via Celery Beat at 2am (Africa/Lagos timezone).

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register hospital account |
| POST | `/api/auth/login/` | Login, get JWT tokens |
| GET | `/api/auth/me/` | Current user + hospital info |
| GET | `/api/auth/dashboard/` | Dashboard stats + ML status |
| POST | `/api/hospital/create/` | Create hospital profile |
| GET/PATCH | `/api/hospital/profile/` | View/update hospital profile |
| GET/POST | `/api/requests/` | List / create blood requests |
| GET | `/api/requests/{id}/` | Request detail |
| GET | `/api/requests/{id}/donors/` | Matched donors for request |
| POST | `/api/requests/{id}/donors/{mid}/check-availability/` | Verify donor availability |
| POST | `/api/requests/{id}/donors/{mid}/select/` | Select a donor |
| POST | `/api/payments/{id}/initiate/` | Initiate bank transfer payment |
| POST | `/api/payments/{id}/confirm/` | Confirm payment |
| POST | `/api/payments/{id}/close/` | Close session |
| POST | `/api/webhook/n8n/donors-found/` | **N8N callback webhook** |

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────┐
│                   Nginx (Port 80)                │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│         Django + Gunicorn (Port 8000)            │
│  ┌─────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │  Auth   │ │ Requests │ │  Payments / Session│ │
│  └─────────┘ └──────────┘ └────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │         ML Engine (DonorMatchingEngine)      │ │
│  │  Phase 1: N8N → Phase 2: Hybrid → Phase 3:  │ │
│  │              Autonomous                      │ │
│  └──────────────────────────────────────────────┘ │
└──────┬─────────────────────────────┬──────────────┘
       │                             │
┌──────▼──────┐             ┌────────▼────────┐
│  PostgreSQL │             │  N8N Workflow   │
│  (donors,   │             │  (External)     │
│  requests,  │             └─────────────────┘
│  outcomes)  │
└─────────────┘
       │
┌──────▼──────┐
│  Celery     │  ← Nightly ML retraining
│  + Redis    │  ← Availability score refresh
└─────────────┘
```

---

## 📁 Project Structure

```
donormatch/
├── Dockerfile               ← Multi-stage production build
├── docker-compose.yml       ← Full stack: web, db, redis, celery, nginx
├── requirements.txt
├── .env.example
├── manage.py
├── donormatch/
│   ├── settings.py          ← Env-driven config (SQLite dev / Postgres prod)
│   ├── urls.py
│   └── celery.py            ← Celery + periodic task schedule
├── core/                    ← User auth, N8N client, dashboard
├── hospitals/               ← Hospital model + profile management
├── blood_requests/          ← Request lifecycle + donor matching
├── donors/                  ← Donor model + availability logs
├── ml_engine/               ← Scoring engine + Celery ML tasks
├── payments/                ← Bank transfer payment flow
├── templates/
│   └── index.html           ← Single-page frontend (vanilla JS)
├── static/
└── nginx/
    └── nginx.conf
```
#   D o n o r n a t c h v 1  
 