# TradeWise — Deployment Guide

This guide covers deploying the TradeWise platform to production. The recommended approach uses a cloud Python host for the backend and a static CDN for the frontend.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Supabase Setup](#supabase-setup)
4. [Deploy Backend to Render](#deploy-backend-to-render)
5. [Deploy Backend to Railway](#deploy-backend-to-railway)
6. [Deploy Frontend to Vercel/Netlify](#deploy-frontend-to-vercelnetlify)
7. [Docker Deployment](#docker-deployment)
8. [Environment Variables (Production)](#environment-variables-production)
9. [Post-Deployment Verification](#post-deployment-verification)
10. [Monitoring & Logging](#monitoring--logging)

---

## Architecture Overview

```
[Learners & Traders]
        │
        ▼
┌─────────────────────┐       ┌─────────────────────┐
│ Pro-Trader Frontend │       │  Learner Frontend   │
│ (Vercel / Netlify)  │       │ (Vercel / Netlify)  │
└─────────────────────┘       └─────────────────────┘
        │                             │
        └──────────────┬──────────────┘
                       ▼
            ┌─────────────────────┐
            │   Flask Backend     │
            │  (Render / Railway) │
            └─────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
  ┌────────────┐ ┌──────────┐ ┌──────────────┐
  │  Supabase  │ │Cashfree  │ │  SMTP Email  │
  │ PostgreSQL │ │Payments  │ │   Service    │
  │ + Realtime │ │          │ │              │
  └────────────┘ └──────────┘ └──────────────┘
```

---

## Pre-Deployment Checklist

- [ ] Supabase project created and schema applied
- [ ] Cashfree LIVE account credentials obtained (or TEST for staging)
- [ ] SMTP credentials configured (Gmail App Password or SendGrid)
- [ ] All environment variables gathered
- [ ] `FLASK_ENV=production` and `FLASK_DEBUG=false`
- [ ] Strong `FLASK_SECRET_KEY` generated (32+ random characters)
- [ ] Strong `JWT_SECRET_KEY` generated
- [ ] `ENCRYPTION_KEY` generated for bank detail encryption
- [ ] `FRONTEND_URL` set to production frontend domain
- [ ] HTTPS configured on all services

### Generate Secure Keys

```bash
# Flask secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# JWT secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Fernet encryption key (for bank details)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Supabase Setup

### 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Choose region closest to your users (e.g. `ap-south-1` for India)
3. Wait for project to initialize (~2 minutes)

### 2. Apply Database Schema

1. Go to **SQL Editor** in your Supabase dashboard
2. Paste contents of `supabase/schema.sql` → **Run**
3. Paste contents of `supabase/rls-policies.sql` → **Run**
4. Verify tables are created in **Table Editor**

### 3. Enable Realtime

1. Go to **Database** → **Replication**
2. Enable replication for:
   - `notifications`
   - `trades`
   - `comments`
3. Verify in **Realtime** → **Inspector**

### 4. Set Up Storage

1. Go to **Storage** → **Create bucket**
2. Create buckets:
   - `trade-charts` (public)
   - `kyc-documents` (private)
   - `avatars` (public)
3. Set appropriate bucket policies

### 5. Configure Email Templates

1. Go to **Authentication** → **Email Templates**
2. Copy the HTML from `supabase/email-templates/confirm-signup.html`
3. Paste into the **Confirm signup** template

### 6. Get Credentials

From **Settings** → **API**:
- `SUPABASE_URL`: Your project URL
- `SUPABASE_ANON_KEY`: The `anon`/`public` key
- `SUPABASE_SERVICE_ROLE_KEY`: The `service_role` key (⚠️ keep secret)
- `SUPABASE_JWT_SECRET`: The JWT secret

---

## Deploy Backend to Render

[Render](https://render.com) is the recommended platform for the Flask backend.

### 1. Create a New Web Service

1. Go to [render.com](https://render.com) → **New Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `tradewise-backend`
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 4 -b 0.0.0.0:$PORT "run:app"`

### 2. Set Environment Variables

In Render dashboard → **Environment**:

```
FLASK_ENV=production
FLASK_SECRET_KEY=<generated-secret>
FLASK_DEBUG=false
DATABASE_URL=<supabase-postgres-connection-string>
SUPABASE_URL=<your-supabase-url>
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
JWT_SECRET_KEY=<generated-jwt-secret>
CASHFREE_APP_ID=<cashfree-live-app-id>
CASHFREE_SECRET_KEY=<cashfree-live-secret>
CASHFREE_BASE_URL=https://api.cashfree.com/pg
CASHFREE_PAYOUT_BASE_URL=https://payout.cashfree.com
ENCRYPTION_KEY=<fernet-encryption-key>
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<your-email>
MAIL_PASSWORD=<app-password>
FRONTEND_URL=https://tradewise.yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
```

### 3. Deploy

Render will automatically deploy on every push to your main branch.

**Backend URL:** `https://tradewise-backend.onrender.com`

---

## Deploy Backend to Railway

[Railway](https://railway.app) is an alternative to Render.

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Deploy
cd backend
railway up
```

Set environment variables in the Railway dashboard or via CLI:
```bash
railway variables set FLASK_ENV=production
railway variables set DATABASE_URL=<your-db-url>
# ... etc.
```

---

## Deploy Frontend to Vercel/Netlify

The frontend is static HTML/CSS/JS — no build step required.

### Vercel (Recommended)

**Pro-Trader Frontend:**

1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import your GitHub repository
3. Configure:
   - **Root Directory:** `frontend`
   - **Build Command:** (leave empty — no build needed)
   - **Output Directory:** `.` (current directory)
4. Add environment variable:
   - `VITE_API_BASE_URL` = `https://tradewise-backend.onrender.com/api`

**Learner Frontend:**

Repeat the same steps with:
- **Root Directory:** `frontend/learner`

### Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy Pro-Trader frontend
netlify deploy --dir=frontend --prod

# Deploy Learner frontend
netlify deploy --dir=frontend/learner --prod
```

### Update API Base URL in HTML Files

Since the frontend uses plain HTML without a build step, update the API base URL directly in your HTML files before deploying:

```html
<script>
  window.TW_API_BASE_URL = 'https://tradewise-backend.onrender.com/api';
  window.TW_SUPABASE_URL = 'https://your-project.supabase.co';
  window.TW_SUPABASE_ANON_KEY = 'your-production-anon-key';
</script>
```

---

## Docker Deployment

For self-hosted or VPS deployment:

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV FLASK_ENV=production
ENV FLASK_DEBUG=false

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "120", "run:app"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    env_file:
      - backend/.env
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./frontend:/usr/share/nginx/html/pro-trader
      - ./frontend/learner:/usr/share/nginx/html/learner
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - backend
    restart: unless-stopped
```

### Build and Start

```bash
docker-compose up -d --build
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name tradewise.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/tradewise.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tradewise.yourdomain.com/privkey.pem;

    # Pro-Trader Frontend
    location / {
        root /usr/share/nginx/html/pro-trader;
        try_files $uri $uri/ /index.html;
    }

    # Learner Frontend
    location /learner {
        alias /usr/share/nginx/html/learner;
        try_files $uri $uri/ /learner/index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://backend:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name tradewise.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

---

## Environment Variables (Production)

Key differences from development:

| Variable | Development | Production |
|----------|-------------|------------|
| `FLASK_ENV` | `development` | `production` |
| `FLASK_DEBUG` | `true` | `false` |
| `CASHFREE_BASE_URL` | `https://sandbox.cashfree.com/pg` | `https://api.cashfree.com/pg` |
| `CASHFREE_PAYOUT_BASE_URL` | `https://payout-gamma.cashfree.com` | `https://payout.cashfree.com` |
| `DATABASE_URL` | Local/test Supabase | Production Supabase |
| `FRONTEND_URL` | `http://localhost:3000` | `https://tradewise.yourdomain.com` |

⚠️ **Never commit `.env` files to Git.** The `.gitignore` file already excludes `.env`.

---

## Post-Deployment Verification

After deploying, verify the following:

### Backend Health Check

```bash
# Check API is responding
curl https://tradewise-backend.onrender.com/api/auth/login
# Expected: 400 (missing fields) — means server is up

# Check CORS headers
curl -I -H "Origin: https://tradewise.yourdomain.com" \
  https://tradewise-backend.onrender.com/api/auth/login
# Expected: Access-Control-Allow-Origin header present
```

### Cashfree Webhook

1. Log in to [Cashfree dashboard](https://merchant.cashfree.com)
2. Go to **Developers** → **Webhooks**
3. Set webhook URL: `https://tradewise-backend.onrender.com/api/webhooks/cashfree/payment`
4. Set payout webhook: `https://tradewise-backend.onrender.com/api/webhooks/cashfree/payout`
5. Copy the **Webhook Secret** to `CASHFREE_WEBHOOK_SECRET` env variable

### Full Flow Verification

- [ ] Register a pro-trader account
- [ ] Register a learner account
- [ ] Pro-trader posts a trade
- [ ] Learner sees trade in feed (blurred)
- [ ] Learner unlocks trade with 1 credit
- [ ] Learner subscribes to pro-trader (test payment)
- [ ] Pro-trader closes trade
- [ ] Learner receives notification

---

## Monitoring & Logging

### Backend Logging

Flask logs are written to stdout by default. On Render/Railway, view them in the dashboard under **Logs**.

For production, consider:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### Error Tracking (Optional)

Add Sentry for error tracking:

```bash
pip install sentry-sdk[flask]
```

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://your-sentry-dsn",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1
)
```

### Uptime Monitoring

Use a free service like [UptimeRobot](https://uptimerobot.com) to ping `https://tradewise-backend.onrender.com/api/auth/login` every 5 minutes.

---

## Scaling Considerations

| Concern | Solution |
|---------|---------|
| High concurrent users | Increase Gunicorn workers: `-w 8` |
| Background email sending | Add Celery + Redis (already in requirements) |
| Database connection pooling | Already configured: `pool_pre_ping=True, pool_recycle=300` |
| Large file uploads | Increase `MAX_CONTENT_LENGTH` and use chunked uploads |
| API rate limiting | Add Flask-Limiter (recommended for auth endpoints) |
| CDN for images | Supabase Storage already provides CDN |
