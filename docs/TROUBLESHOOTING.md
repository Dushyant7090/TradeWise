# TradeWise — Troubleshooting Guide

Solutions for the most common issues encountered when setting up and running the TradeWise platform.

---

## Table of Contents

1. [Backend Startup Issues](#1-backend-startup-issues)
2. [CORS Errors](#2-cors-errors)
3. [Authentication Issues](#3-authentication-issues)
4. [Database Connection Issues](#4-database-connection-issues)
5. [Credit System Issues](#5-credit-system-issues)
6. [Blurred Content Not Working](#6-blurred-content-not-working)
7. [Real-time Not Updating](#7-real-time-not-updating)
8. [Payment / Cashfree Issues](#8-payment--cashfree-issues)
9. [Image / File Upload Issues](#9-image--file-upload-issues)
10. [Notification Issues](#10-notification-issues)
11. [Test Suite Failures](#11-test-suite-failures)
12. [Frontend Issues](#12-frontend-issues)

---

## 1. Backend Startup Issues

### Error: `ModuleNotFoundError: No module named 'flask'`

**Cause:** Virtual environment not activated, or dependencies not installed.

**Fix:**
```bash
cd backend
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

---

### Error: `Error loading .env file` or missing environment variable

**Cause:** `.env` file not created from the example.

**Fix:**
```bash
cd backend
cp .env.example .env
# Edit .env with your actual values
```

---

### Error: `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server`

**Cause:** Invalid `DATABASE_URL` or Supabase database not reachable.

**Fix:**
1. Verify `DATABASE_URL` in your `.env` is correct
2. Check your Supabase project is active (not paused — free tier pauses after inactivity)
3. Test connection:
   ```bash
   python3 -c "
   import os
   from sqlalchemy import create_engine
   engine = create_engine(os.environ['DATABASE_URL'])
   with engine.connect() as conn:
       print('Connected!')
   "
   ```
4. Whitelist your IP in Supabase: **Settings** → **Database** → **Network restrictions**

---

### Error: `Address already in use :5000`

**Cause:** Another process is using port 5000.

**Fix:**
```bash
# Find the process
lsof -i :5000

# Kill it
kill -9 <PID>

# Or use a different port
python run.py --port 5001
```

---

### Error: `cryptography.fernet.InvalidToken` on startup

**Cause:** `ENCRYPTION_KEY` is missing or incorrectly formatted.

**Fix:**
```bash
# Generate a valid key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output to ENCRYPTION_KEY in .env
```

---

## 2. CORS Errors

### Error: `Access to fetch at 'http://localhost:5000/api/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Cause:** The backend's `FRONTEND_URL` doesn't match the origin making the request.

**Fix 1 — Update .env:**
```env
FRONTEND_URL=http://localhost:3000
```

**Fix 2 — If running frontend on port 8000 (learner):**
The backend allows multiple origins. Verify `FRONTEND_URL` includes both:
```env
FRONTEND_URL=http://localhost:3000
```
For the learner frontend, also add port 8000. Check `backend/app/__init__.py` for the CORS configuration and add `http://localhost:8000` to the allowed origins list.

**Fix 3 — Temporary debug fix (development only):**
```python
# In app/__init__.py, allow all origins temporarily:
CORS(app, origins="*")
```
⚠️ Never use `"*"` in production.

---

### Error in production: CORS still blocked after setting domain

**Fix:** Ensure `FRONTEND_URL` exactly matches your deployed frontend domain (include `https://`, no trailing slash):
```env
FRONTEND_URL=https://tradewise.yourdomain.com
```

---

## 3. Authentication Issues

### Error: `401 Unauthorized — Missing authorization token`

**Cause:** The request isn't including the JWT token in the header.

**Fix:** Include the `Authorization` header:
```javascript
fetch('/api/pro-trader/profile', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('tw_jwt_token')}`
  }
})
```

---

### Error: `401 Unauthorized — Token has expired`

**Cause:** Access token has expired (default: 1 hour).

**Fix:** The frontend should auto-refresh the token. If it isn't:
1. Check `frontend/js/api.js` — the `fetch` wrapper should call `POST /api/auth/refresh-token` on 401
2. Verify `tw_refresh_token` is stored in localStorage
3. Clear localStorage and log in again:
   ```javascript
   localStorage.clear();
   window.location.href = '/pages/login.html';
   ```

---

### Error: `400 — Password must contain uppercase, lowercase, and digit`

**Cause:** The registration password doesn't meet complexity requirements.

**Fix:** Use a password with at least:
- 8 characters
- 1 uppercase letter
- 1 lowercase letter
- 1 digit

Example: `TestPass1`

---

### Error: `409 Conflict — Email already registered`

**Cause:** Attempting to register with an email already in use.

**Fix:** Use a different email, or log in with the existing account.

---

### Login succeeds but user is redirected to wrong dashboard

**Cause:** Role not being stored/checked correctly after login.

**Fix:** Verify the role is stored after login:
```javascript
const data = await loginResponse.json();
localStorage.setItem('tw_user_role', data.user.role);
// Redirect based on role
if (data.user.role === 'pro_trader') {
  window.location.href = '/pages/dashboard.html';
} else {
  window.location.href = '/learner/pages/dashboard.html';
}
```

---

## 4. Database Connection Issues

### Tables don't exist after running the app

**Cause:** Schema not applied to Supabase, or `db.create_all()` not run.

**Fix:**
```bash
# Option 1: Apply schema manually in Supabase SQL Editor
# Paste and run supabase/schema.sql

# Option 2: Let SQLAlchemy create the tables
cd backend
source venv/bin/activate
python3 -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Tables created!')
"
```

---

### Supabase project is paused (free tier)

**Symptom:** `Connection refused` or `timeout` errors.

**Fix:** Log in to [supabase.com](https://supabase.com), open your project, and click **Restore project**. Free tier projects pause after 7 days of inactivity.

---

## 5. Credit System Issues

### Credits not deducting when unlocking a trade

**Cause:** The unlock endpoint isn't being called correctly, or the subscription check is bypassing the credit deduction.

**Debug:**
```bash
# Check current credits
curl http://localhost:5000/api/learner/credits \
  -H "Authorization: Bearer $TOKEN"

# Check credit log
curl http://localhost:5000/api/learner/credits/log \
  -H "Authorization: Bearer $TOKEN"
```

**Fix:** Ensure the unlock endpoint is `POST /api/learner/trades/{trade_id}/unlock`, not just a GET request.

---

### Learner not starting with 7 credits

**Cause:** New learner's profile was created without the default credit value.

**Fix:** Check the `profiles` table default:
```sql
SELECT credits FROM profiles WHERE id = '<learner-uuid>';
```

If 0, update manually:
```sql
UPDATE profiles SET credits = 7 WHERE id = '<learner-uuid>';
```

Or verify the backend sets credits=7 on registration in `app/routes/auth.py`.

---

### 402 error shown but learner has credits remaining

**Cause:** The learner might be subscribed to this trader, but subscription check logic has a bug — OR the frontend is showing stale credit data.

**Fix:**
1. Refresh the page to get latest credits from API
2. Check the subscription status:
   ```bash
   curl http://localhost:5000/api/learner/subscriptions \
     -H "Authorization: Bearer $TOKEN"
   ```
3. If `status` is `expired`, the subscription needs to be renewed

---

## 6. Blurred Content Not Working

### Trade details show without blurring for non-subscribed learners

**Cause:** Frontend is rendering the full trade without checking `is_unlocked` status.

**Fix:** Verify the conditional rendering in the trade card template:
```javascript
if (!trade.is_unlocked && !trade.is_subscribed) {
  // Apply blur CSS class
  detailsElement.classList.add('blurred');
  detailsElement.setAttribute('aria-hidden', 'true');
} else {
  detailsElement.classList.remove('blurred');
}
```

---

### Blurring shows even after unlock

**Cause:** Frontend not re-rendering after successful unlock API call.

**Fix:** After a successful unlock response, update the trade object and re-render:
```javascript
const unlockResp = await api.post(`/learner/trades/${tradeId}/unlock`);
if (unlockResp.ok) {
  trade.is_unlocked = true;
  renderTrade(trade); // Re-render with full data
}
```

---

## 7. Real-time Not Updating

### Trade status not updating in learner feed

**Cause:** Supabase Realtime not enabled, or wrong channel subscription.

**Fix:**
1. Enable Realtime in Supabase: **Database** → **Replication** → enable `trades` table
2. Verify the frontend subscribes to the right channel:
   ```javascript
   const channel = supabase
     .channel('trades-changes')
     .on('postgres_changes',
       { event: 'UPDATE', schema: 'public', table: 'trades' },
       (payload) => {
         console.log('Trade updated:', payload.new);
         updateFeedItem(payload.new);
       }
     )
     .subscribe();
   ```
3. Check browser console for `Supabase Realtime connected` message

---

### Comments not appearing in real-time

**Fix:** Ensure the `comments` table is also enabled for Replication in Supabase, and the frontend subscribes to comment changes filtered by `trade_id`.

---

### Realtime works locally but not in production

**Cause:** Supabase Anon Key is different in production, or Realtime subscription is missing the auth token.

**Fix:** Ensure the Supabase client is initialized with the production URL and anon key:
```javascript
window.TW_SUPABASE_URL = 'https://your-production-project.supabase.co';
window.TW_SUPABASE_ANON_KEY = 'production-anon-key';
```

---

## 8. Payment / Cashfree Issues

### Cashfree payment form not loading

**Cause:** Cashfree credentials not set, or using production URL for test mode.

**Fix:** Verify `.env`:
```env
CASHFREE_APP_ID=your-test-app-id
CASHFREE_SECRET_KEY=your-test-secret
CASHFREE_BASE_URL=https://sandbox.cashfree.com/pg
```

---

### Payment succeeds but subscription not created

**Cause:** Cashfree webhook not configured or not reaching the backend.

**Fix:**
1. Verify the webhook URL in Cashfree dashboard: `https://your-backend.com/api/webhooks/cashfree/payment`
2. For local testing, use [ngrok](https://ngrok.com) to expose localhost:
   ```bash
   ngrok http 5000
   # Use the ngrok URL: https://abc123.ngrok.io/api/webhooks/cashfree/payment
   ```
3. Check backend logs for incoming webhook calls:
   ```bash
   # Look for: POST /api/webhooks/cashfree/payment
   tail -f backend/logs/app.log
   ```
4. Verify `CASHFREE_WEBHOOK_SECRET` matches what's set in the Cashfree dashboard

---

### Error: `Cashfree signature mismatch`

**Cause:** `CASHFREE_WEBHOOK_SECRET` in `.env` doesn't match the one set in Cashfree dashboard.

**Fix:** Copy the exact webhook secret from Cashfree → **Developers** → **Webhooks** → **Webhook Secret** and paste it into `CASHFREE_WEBHOOK_SECRET`.

---

### Credits not deducted after resubscription attempt

This is expected behavior — subscribed learners should NOT have credits deducted. If you're seeing unexpected credit deduction for a subscribed learner:

**Fix:** Check the subscription lookup query in the backend's unlock logic. Ensure it checks both `status = 'active'` AND `end_date > NOW()`.

---

## 9. Image / File Upload Issues

### Error: `413 Request Entity Too Large`

**Cause:** Uploaded file exceeds the 10 MB limit.

**Fix:** Check the file size before uploading. The backend rejects files larger than 10 MB (`MAX_CONTENT_LENGTH = 10 * 1024 * 1024`).

---

### Uploaded images not displaying

**Cause:** Supabase Storage bucket is private, or the URL is incorrect.

**Fix:**
1. Verify the storage bucket `trade-charts` is set to **public**
2. Check that the URL stored in the database is a valid Supabase Storage public URL:
   ```
   https://[project-ref].supabase.co/storage/v1/object/public/trade-charts/filename.jpg
   ```

---

### Error: `Invalid file type`

**Cause:** Uploaded file is not a JPEG, PNG, or PDF.

**Fix:** Only upload:
- KYC documents: JPEG, PNG, or PDF
- Profile pictures: JPEG or PNG
- Trade charts: JPEG or PNG

---

## 10. Notification Issues

### Notifications not appearing

**Cause:** Notification was not created by the backend, or Realtime subscription is missing.

**Debug:**
```bash
# Check if notifications exist in database
curl http://localhost:5000/api/learner/notifications \
  -H "Authorization: Bearer $TOKEN"
```

**Fix:**
1. Verify the backend's notification service is called when events occur (trade posted, trade closed, etc.)
2. Check `backend/app/services/notification_service.py` is called from the relevant routes
3. Enable the `notifications` table in Supabase Replication for real-time delivery

---

### Email notifications not sending

**Cause:** SMTP credentials not configured or incorrect.

**Fix:**
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
```

**Gmail App Password:** Go to Google Account → Security → 2FA → App Passwords → Generate.

**Test email:**
```bash
python3 -c "
from flask_mail import Message
from app import create_app, mail
app = create_app()
with app.app_context():
    msg = Message('Test', sender='noreply@tradewise.com', recipients=['your@email.com'])
    msg.body = 'Test email from TradeWise'
    mail.send(msg)
    print('Email sent!')
"
```

---

## 11. Test Suite Failures

### Error: `ImportError: No module named 'app'`

**Cause:** Tests run from outside the `backend/` directory.

**Fix:**
```bash
cd backend
pytest tests/ -v
```

---

### Tests fail with database errors

**Cause:** SQLite in-memory database not being reset between tests.

**Fix:** The `conftest.py` uses `scope="function"` for the `db` fixture, which resets after each test. If tests are sharing state, ensure each test uses the `db` fixture:

```python
def test_something(client, db):  # Always include `db` fixture
    ...
```

---

### Error: `jwt.exceptions.DecodeError` in tests

**Cause:** JWT secret key not set for the test configuration.

**Fix:** `TestingConfig` in `app/config.py` should inherit `JWT_SECRET_KEY` from `BaseConfig`. Verify:
```python
class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=60)
    # JWT_SECRET_KEY inherited from BaseConfig
```

---

## 12. Frontend Issues

### Page shows blank / nothing loads

**Cause:** API base URL not configured, or backend server not running.

**Fix:**
1. Open browser DevTools (F12) → **Console** tab
2. Look for network errors (red text)
3. Verify backend is running: `curl http://localhost:5000/api/auth/login`
4. Verify `window.TW_API_BASE_URL` is set correctly in the HTML file

---

### Charts not rendering

**Cause:** Chart.js not loaded, or the canvas element is not found.

**Fix:**
1. Check DevTools → **Console** for `Chart is not defined` error
2. Verify Chart.js is loaded before `charts.js`:
   ```html
   <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
   <script src="../js/charts.js"></script>
   ```

---

### Sidebar not collapsing on mobile

**Cause:** JavaScript for the hamburger menu not initializing.

**Fix:**
1. Open DevTools → **Console**
2. Check for errors in `main.js`
3. Verify the hamburger button has the correct ID/class that `main.js` targets

---

### Form submission not working

**Cause:** JavaScript `fetch` call failing silently.

**Fix:** Add error handling to all fetch calls and check the **Network** tab in DevTools for failed API requests:
```javascript
try {
  const response = await api.post('/auth/login', { email, password });
  if (!response.ok) {
    const error = await response.json();
    showError(error.message || 'Login failed');
  }
} catch (err) {
  showError('Network error — is the backend running?');
  console.error(err);
}
```

---

## Still having issues?

1. Check the **backend logs** in your terminal for stack traces
2. Open browser **DevTools → Network tab** and inspect failed requests
3. Check **Supabase logs**: Your Supabase project → **Logs** → **API**
4. Ensure all environment variables are set (no empty values in `.env`)
5. Try a fresh start: delete the SQLite file (if using SQLite), restart the server, and clear browser localStorage
