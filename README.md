# Ask Stellar Backend - Vedic Astrology API

A FastAPI backend for Vedic astrology consultations with Firebase authentication, PostgreSQL, Redis caching, and AI-powered astrology agents. Includes Swiss Ephemeris data for precise calculations and Google Play webhook-based billing for credits/subscriptions.

## Features

- **FastAPI framework** with automatic OpenAPI documentation (when `DEBUG=True`)
- **Firebase Authentication** integration
- **PostgreSQL** with SQLAlchemy ORM and Alembic migrations
- **Redis caching** for performance
- **AI-powered astrology agents** (OpenAI)
- **Swiss Ephemeris-based calculations** (via `jhora`)
- **Real-time chat** with Server-Sent Events (SSE)
- **Partners & Compatibility** (Ashtakoota) with friendship mode
- **Google Play Billing (webhook-based)** for credits/subscriptions
- **Clean architecture** (routers, models, schemas, CRUD)

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (optional, recommended)
- Firebase project with Authentication enabled
- Firebase service account key (server-side Admin SDK)
- OpenAI API key
- Optional: Tavily API key (web search)

## Local Development Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-directory>/backend
```

### 2. Set up Firebase

1. Create a project in Firebase Console (`https://console.firebase.google.com`)
2. Enable Authentication
3. Generate a service account key (Project Settings → Service Accounts → Generate New Private Key)
4. Save the JSON as `backend/firebase-service-account.json`

### 3. Configure environment variables

Create a `.env` file (or export in your shell) with at least:

- Firebase:
  - `FIREBASE_PROJECT_ID`
  - `FIREBASE_SERVICE_ACCOUNT_JSON=./firebase-service-account.json` (local) or `/app/firebase-service-account.json` (in container)
  - Optionally `GOOGLE_APPLICATION_CREDENTIALS` if you prefer ADC
- AI/LLM:
  - `OPENAI_API_KEY`
  - `TAVILY_API_KEY` (optional)
- Database & Cache:
  - Either `DATABASE_URL` or `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
  - `REDIS_HOST`, `REDIS_PORT`
- App:
  - `DEBUG` (enable docs when `True`)
  - `CORS_ORIGINS` (JSON array, e.g., `["*"]` for local dev)
  - `SE_EPHE_PATH` (e.g., `/app/ephe`)
- Email/Support (Mailgun or logging):
  - `EMAIL_PROVIDER` = `mailgun` | `logging`
  - If `mailgun`: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_BASE_URL` (optional)
  - Common: `EMAIL_FROM`, `EMAIL_FROM_NAME`, `SUPPORT_TO_EMAIL`, `SUPPORT_BCC_EMAIL` (optional)
- Google Play:
  - `GOOGLE_PLAY_PACKAGE_NAME`
  - `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=./purchase-service-account.json` (local) or container path

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the application

```bash
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs` (when `DEBUG=True`)

## Docker Compose Setup

For a complete setup with PostgreSQL and Redis:

1. Ensure `backend/firebase-service-account.json` exists
2. Provide required env vars in your shell (or a `.env` file loaded by your shell)
3. Start services:
   ```bash
   docker-compose up -d
   ```
4. API: `http://localhost:8000`
5. Logs: `docker-compose logs -f`
6. Stop: `docker-compose down`

## Database Migrations

Alembic migrations are included and applied automatically by the container entrypoint.

- Create new migrations by adding a file under `migrations/versions` named `v{N}_{description}.py`
- Run manually if needed:
  ```bash
  docker exec -it backend-api alembic upgrade head
  ```

## Google Play Billing (Webhook-based)

Webhook-first integration using Real-time Developer Notifications via Pub/Sub.

- Frontend must set `obfuscatedExternalAccountId` during purchase via BillingFlowParams
- Backend identifies user from notifications and updates credits/subscriptions accordingly

Endpoints:
- `POST /payments/google-play` — Pub/Sub webhook endpoint (returns 200 quickly, processes in background)
- `POST /payments/google-play/verify` — Client-side verification after purchase; also processes pending events

Benefits:
- No service account or Console API calls required for core flows
- Real-time, reliable purchase processing and refund handling

Setup:
1. Create a Pub/Sub topic and subscription
2. Configure Google Play to send RTDN to the Pub/Sub topic
3. Point your push subscription/webhook to `/payments/google-play`
4. Frontend must set user ID during purchase (see example below)

Android example:
```kotlin
val billingFlowParams = BillingFlowParams.newBuilder()
    .setProductDetailsParamsList(productDetailsParamsList)
    .setObfuscatedAccountId(currentUserId) // Firebase user ID
    .build()

billingClient.launchBillingFlow(activity, billingFlowParams)
```

## API Endpoints

### Public
- `GET /` — Welcome
- `GET /health` — Health check
- `GET /public` — Public test route
- `GET /protected` — Protected test route (requires Firebase auth)

### Authentication
Include Firebase ID token:
```
Authorization: Bearer <firebase-id-token>
```

### Users
- `GET /users/me` — Current user info
- `PATCH /users/me` — Update user
- `GET /users/check-username?username=<name>` — Check availability
- `GET /users/search-username?username_pattern=<q>&limit=10` — Search users

### User Data & Features
- `GET /users/me/messages` — List my messages (latest first, paginated)
- `GET /users/me/threads/{thread_id}/messages` — Messages in a thread
- `GET /users/me/daily-facts?day=yesterday|today|tomorrow|all` — Daily facts (cached until next IST day)
- `POST /users/me/charts` — Get divisional charts by names (e.g., `["D1","D9"]`)
- `GET /users/me/life-events` — Significant life events (cached 24h)
- `GET /users/me/compatibility/{partner_id}?compatibility_type=love|friendship` — User ↔ Partner analysis
- `GET /users/me/compatibility-with-user/{other_user_id}?compatibility_type=love|friendship` — User ↔ Another user (friends only)
- `GET /users/me/compatibility-reports` — All saved compatibility reports

### Partners
- `POST /partners` — Create partner (returns `moon_sign`)
- `GET /users/me/partners` — My partners
- `GET /partners/{partner_id}` — Partner details (with `moon_sign`)
- `DELETE /partners/{partner_id}` — Delete partner

### Threads
- `GET /users/me/threads` — List my threads (paginated)
- `POST /users/me/threads` — Create thread (max 1 additional participant; optional `compatibility_type`)
- `GET /users/me/threads/{thread_id}` — Get thread
- `PATCH /users/me/threads/{thread_id}` — Update title/participants (`compatibility_type` allowed only with exactly one participant)
- `DELETE /users/me/threads/{thread_id}` — Delete thread

### Chat (SSE)
- `GET /chat/stream` — Stream responses
  - Query params: `message`, optional `thread_id`, optional `participant_user_ids` (CSV), optional `participant_partner_ids` (CSV)
  - Deducts 1 credit per request; validates ownership/friendship/participants

- `GET /chat/suggestions` — Follow-up question suggestions based on last assistant answer (requires `thread_id`)

### Credits
- `GET /credits/balance` — Current user credit balance

### Friends
- `POST /friends/request` — Send request by recipient username (requires you to have a username)
- `POST /friends/request/{request_id}/accept` — Accept request
- `POST /friends/request/{request_id}/reject` — Reject request
- `DELETE /friends/request/{request_id}` — Cancel sent request
- `GET /friends/requests` — Incoming requests (paginated)
- `GET /friends/requests/sent` — Sent requests (paginated)
- `GET /friends/list` — Friends list with optional username/display_name search
- `DELETE /friends/{friend_username}` — Remove a friend

### Payments (Google Play)
- `POST /payments/google-play` — Pub/Sub webhook
- `POST /payments/google-play/verify` — Verify purchase and grant entitlements

### Devices
- `POST /devices/register` — Register or update device token (FCM)
- `DELETE /devices/unregister` — Remove device token
- `POST /devices/heartbeat` — Update device heartbeat
- `GET /devices` — List my device tokens

### Support
- `POST /support/help-email` — Send a help email to support (rate limited)

### Streaks
- `GET /streaks/me` — Get my streak info (subscription can protect streak)

### Rants
- `POST /rants/` — Submit a rant and receive a therapeutic response (updates streak if valid)

## Astrology Features

- Precise planetary positions
- Divisional charts (Vargas): D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12, D16, D20, D24, D27, D30, D40, D45, D60
- Panchanga: Tithi, Nakshatra, Yoga, Karana, Vara
- Special Lagnas: Hora, Ghati, Vighati, etc.
- Yogas: Raja, Dhana, and others
- Dashas: Vimsottari and more
- Transit analysis

## Caching Strategy

- Daily facts: cached until next IST day
- Compatibility: cached until data changes
- Chart calculations: cached to reduce computation
- Redis persistence via Docker volume

## Authentication Flow

1. User signs in via Firebase (client)
2. Client receives Firebase ID token
3. Include token in headers:
   ```
   Authorization: Bearer <firebase-id-token>
   ```
4. Backend validates token and loads user

## Project Structure

```
backend/
├── app/
│   ├── agents/
│   ├── crud/
│   ├── llm/
│   ├── models/
│   ├── routers/
│   │   ├── api.py
│   │   ├── users.py
│   │   ├── partners.py
│   │   ├── chat.py
│   │   ├── payments.py
│   │   ├── friends.py
│   │   ├── credits.py
│   │   ├── streaks.py
│   │   ├── devices.py
│   │   ├── support.py
│   │   └── rants.py
│   ├── schemas/
│   ├── utils/
│   ├── auth.py
│   ├── cache.py
│   ├── config.py
│   ├── database.py
│   └── main.py
├── jhora/
├── ephe/
├── migrations/
├── deployment/
├── docker-compose.yaml
├── Dockerfile
└── requirements.txt
```

## Development Guide

- Extend astrology tools in `app/agents/tools.py`
- Update agent prompts in `app/agents/prompts.py`
- Add schemas in `app/llm/schemas.py` as needed
- Create API routes under `app/routers`
- Add models when persistence is required

## Testing

- Unit tests for calculations (add under `tests/` as needed)
- Integration tests for API endpoints
- End-to-end checks for chat streaming and payments webhook

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

## License

MIT License - see LICENSE file for details.

## Support

- Open issues on GitHub
- Check OpenAPI docs at `/docs` (when `DEBUG=True`)
- See `jhora/README.md` for astrology calculation details 