# Google Play Payments System

This document describes the new Google Play payments system that handles Real-time Developer Notifications (RTDN) and purchase verification without background processing.

## Architecture Overview

The system uses a hybrid approach:
1. **RTDN Webhook** (`/payments/google-play`): Receives and stores Google Play notifications
2. **Verify Endpoint** (`/payments/google-play/verify`): Client calls this to complete purchases
3. **Purchase Events Table**: Stores RTDN events and their processing status
4. **Google Play API Client**: Validates purchases and acknowledges them

## Key Benefits

- **No Background Jobs**: Everything is synchronous and immediate
- **Idempotent**: Safe to retry and handles duplicates
- **Secure**: Always validates with Google Play Developer API
- **Reliable**: RTDN events are stored even if user can't be resolved immediately

## Flow Diagram

```
App Purchase → RTDN Webhook → Store Event → Try Immediate Processing
     ↓              ↓              ↓              ↓
Verify Call → Check Pending Events → Process Events → Grant Entitlements
     ↓              ↓              ↓              ↓
Acknowledge → Update Status → Return Success → Frontend ACKs
```

## Database Schema

### purchase_events Table
```sql
CREATE TABLE purchase_events (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE,  -- Pub/Sub dedupe
    purchase_token VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),  -- NULL until resolved
    product_id VARCHAR(255),
    event_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    raw_payload JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);
```

## API Endpoints

### 1. RTDN Webhook: `POST /payments/google-play`

**Purpose**: Receives Google Play notifications via Pub/Sub

**Flow**:
1. Validate Pub/Sub message structure
2. Decode base64 notification data
3. Extract purchase token and event type
4. Store event in database
5. Try to resolve user immediately if possible
6. Process event if user is known
7. Return success (required for Pub/Sub)

**Security**: 
- Validates Pub/Sub OIDC/JWT (handled by Google Cloud)
- Stores raw payload for audit

### 2. Verify Endpoint: `POST /payments/google-play/verify`

**Purpose**: Client calls this to complete purchase verification

**Flow**:
1. Validate purchase token with Google Play Developer API
2. Create/update purchase mapping
3. Process any pending RTDN events for this token
4. Grant entitlements based on current state
5. Acknowledge purchase with Google Play
6. Return verification status

**Security**:
- Always calls Google Play API to validate
- Uses authenticated user context
- Idempotent operations

## Configuration

### Environment Variables
```bash
GOOGLE_PLAY_PACKAGE_NAME=com.your.app
GOOGLE_PLAY_SERVICE_ACCOUNT_PATH=./purchase-service-account.json
```

### Product Configuration
```python
PRODUCT_TO_CREDITS = {
    "credits_3": 3,
    "credits_5": 5,
    "credits_10": 10,
    "credits_20": 20,
}

SUBSCRIPTION_PRODUCTS = {
    "unlimited_monthly": "monthly",
    "unlimited_yearly": "yearly",
}
```

## Setup Instructions

### 1. Google Cloud Console
- Enable "Google Play Android Developer API"
- Create service account with appropriate permissions
- Download service account JSON key

### 2. Google Play Console
- Link to Google Cloud project
- Grant service account access to your app
- Set up RTDN webhook URL: `https://your-domain.com/payments/google-play`
- Configure Pub/Sub topic

### 3. Backend Setup
- Place service account JSON in project root
- Run database migration: `alembic upgrade head`
- Install dependencies: `pip install -r requirements.txt`

### 4. Test Setup
```bash
python test_google_play_api.py
```

## Testing

### 1. Test Service Account
```bash
python test_google_play_api.py
```

### 2. Test Webhook (Local)
Use ngrok to expose local server:
```bash
ngrok http 8000
```
Then set webhook URL in Play Console to your ngrok URL.

### 3. Test Purchase Flow
1. Make test purchase in app
2. Check webhook receives RTDN
3. Call verify endpoint
4. Verify credits/subscription activated
5. Check purchase acknowledged

## Error Handling

### Common Issues

1. **Service Account Not Working**
   - Check JSON file path
   - Verify GCP project linking
   - Check API permissions

2. **RTDN Not Received**
   - Verify webhook URL is accessible
   - Check Pub/Sub topic configuration
   - Monitor Play Console logs

3. **Purchase Verification Fails**
   - Check purchase token validity
   - Verify product ID mapping
   - Check Google Play API response

### Monitoring

- Log all RTDN events with message IDs
- Track event processing status
- Monitor Google Play API calls
- Alert on failed verifications

## Security Considerations

1. **Always validate with Google Play API** - never trust RTDN alone
2. **Use authenticated user context** for verify endpoint
3. **Store raw RTDN payloads** for audit purposes
4. **Implement rate limiting** on verify endpoint
5. **Log all operations** for security monitoring

## Migration from Old System

1. **Database**: Run new migration
2. **Code**: Update to use new endpoints
3. **Frontend**: Update to call verify endpoint
4. **Testing**: Verify end-to-end flow works
5. **Monitoring**: Watch for any issues

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify Google Play API client is working
3. Test with known good purchase tokens
4. Check Play Console for webhook delivery status 