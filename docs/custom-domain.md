# TaxBot — Custom Domain and HTTPS Setup

This guide covers adding a custom domain and ensuring HTTPS is active for
all three supported hosting paths: Vercel (frontend), Render (backend), and AWS.

After completing any path here, update `ALLOWED_ORIGINS` in the backend and
rebuild/redeploy the frontend with the new `NEXT_PUBLIC_API_URL`.

---

## 1. Vercel (frontend)

Vercel provisions TLS automatically via Let's Encrypt.

1. In the Vercel dashboard → your project → **Settings → Domains**.
2. Click **Add** and enter your domain (e.g. `taxmitra.yourdomain.com`).
3. Vercel shows a CNAME record: add it to your DNS registrar:
   ```
   CNAME  taxmitra  cname.vercel-dns.com
   ```
4. Wait for DNS propagation (up to 24 h, usually < 5 min).
5. Vercel auto-issues and renews the certificate. HTTPS is automatic.

**CLI alternative:**
```bash
vercel domains add taxmitra.yourdomain.com
```

---

## 2. Render (backend)

Render provisions TLS automatically via Let's Encrypt.

1. In the Render dashboard → your service → **Settings → Custom Domains**.
2. Click **Add Custom Domain** and enter `api.yourdomain.com`.
3. Add the DNS record Render shows you:
   ```
   CNAME  api  yourdomain.onrender.com
   ```
   (Render provides the exact target — copy it from the dashboard.)
4. Click **Verify** in Render. TLS is provisioned within minutes.

---

## 3. AWS (App Runner or ALB)

See [aws-deployment.md](aws-deployment.md) Step 4 for the ACM certificate
request and DNS validation process.

Summary:
- Request certificate in ACM → add the CNAME validation record to DNS.
- Attach the certificate ARN to your App Runner custom domain or ALB HTTPS listener.
- For App Runner: **Service → Custom domains → Add → paste domain → Attach**.

```bash
# Check certificate status
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:REGION:ACCOUNT:certificate/ID \
  --query CertificateDetail.Status
```

---

## 4. After adding a custom domain — required follow-up steps

### 4a. Update ALLOWED_ORIGINS on the backend

Set the `ALLOWED_ORIGINS` environment variable to your production frontend URL:

```
ALLOWED_ORIGINS=https://taxmitra.yourdomain.com
```

Do **not** leave it as `*` in production — this allows any website to call
your API and depletes your rate-limit quota.

| Hosting | Where to update |
|---------|----------------|
| Render  | Service → Environment → Edit `ALLOWED_ORIGINS` → Save → auto-redeploy |
| App Runner | Service → Configuration → Environment variables → Update → Deploy |
| ECS Fargate | Update task definition, create new revision, force new deployment |

### 4b. Update NEXT_PUBLIC_API_URL on the frontend

The frontend must know the backend's new HTTPS URL.

**Vercel:**
1. Project → Settings → Environment Variables.
2. Set `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`.
3. Trigger a new deployment (push a commit or redeploy manually).

**Docker (self-hosted):**
```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
  -t taxbot-web:latest taxmitra-web/
```

### 4c. Update vercel.json rewrites

Replace `BACKEND_URL` in `taxmitra-web/vercel.json` with your backend URL:

```json
"destination": "https://api.yourdomain.com/chat"
```

---

## 5. Verifying everything works

```bash
# Backend health
curl https://api.yourdomain.com/health

# Frontend loads
curl -I https://taxmitra.yourdomain.com/

# CORS check (should not get a CORS error)
curl -s -X POST https://api.yourdomain.com/chat \
  -H "Origin: https://taxmitra.yourdomain.com" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is 80C limit?"}' | python3 -m json.tool
```
