# TaxBot — Monitoring and Observability

This document describes the monitoring stack for a production TaxBot deployment.
All tools listed have free tiers sufficient for personal or small-team use.

---

## 1. Uptime monitoring

### BetterUptime (recommended) or UptimeRobot (free tier)

Both services send HTTP probes to your endpoints every 1–5 minutes and
alert you when they fail.

**Setup (BetterUptime):**
1. Sign up at [betteruptime.com](https://betteruptime.com).
2. Create a monitor: URL = `https://api.yourdomain.com/ready`, interval = 1 min.
3. Alert policy: notify after **2 consecutive failures** (avoids noise from
   transient network blips).
4. Add an on-call schedule or Slack/email alert channel.
5. Optional: add a second monitor for the frontend: `https://taxmitra.yourdomain.com/`.

**Setup (UptimeRobot — free):**
1. Sign up at [uptimerobot.com](https://uptimerobot.com).
2. Add monitor → HTTP(S) → URL: `https://api.yourdomain.com/ready`.
3. Monitoring interval: 5 minutes (free tier limit).
4. Alert contacts: email or Slack.

---

## 2. Error tracking — Sentry

Sentry captures unhandled exceptions, slow requests, and custom events with
full stack traces and contextual breadcrumbs.

### Setup

1. Create a project at [sentry.io](https://sentry.io) (Python → FastAPI).
2. Copy the DSN.
3. Set the `SENTRY_DSN` environment variable on your backend:
   - Render: Service → Environment → `SENTRY_DSN = https://xxx@sentry.io/yyy`
   - AWS Parameter Store: `aws ssm put-parameter --name /taxbot/SENTRY_DSN --value "..." --type SecureString`
4. The TaxBot backend initialises Sentry automatically when `SENTRY_DSN` is set
   (see `api/main.py`). No code changes needed.

### What is captured automatically

- Unhandled exceptions (500 errors)
- Request details (URL, method, status code) — **no PII, no question text**
- Slow transactions (> 10 s) via `traces_sample_rate=0.1`

### Setting up alerts in Sentry

1. Project → Alerts → Create Alert Rule.
2. Trigger: "An issue is seen for the first time" → notify immediately.
3. Trigger: "Issue occurs > 10 times in 1 hour" → escalate to on-call.

---

## 3. Analytics dashboard — built-in `/analytics` endpoint

TaxBot exposes in-process counters at `GET /analytics`:

```json
{
  "questions_total": 1240,
  "not_found_total": 48,
  "out_of_scope_total": 12,
  "cache_hits": 310,
  "feedback_up": 198,
  "feedback_down": 23,
  "avg_latency_ms": 1840.5,
  "p95_latency_ms": 4210.0
}
```

**Key metrics to watch:**

| Metric | Healthy range | Action if outside |
|--------|--------------|-------------------|
| `not_found_total / questions_total` | < 15 % | Ingest more source documents |
| `p95_latency_ms` | < 5 000 ms | Upgrade instance size or switch LLM |
| `feedback_down / (feedback_up + feedback_down)` | < 20 % | Review failing question categories |
| `cache_hits / questions_total` | > 20 % | Good — cache is working |

**Scraping with a cron dashboard (Grafana + Prometheus, optional):**
```yaml
# prometheus.yml scrape config
scrape_configs:
  - job_name: taxbot
    metrics_path: /analytics
    static_configs:
      - targets: ['api.yourdomain.com:443']
    scheme: https
```
*(You would need to export the JSON as Prometheus metrics — a thin adapter is trivial to add.)*

---

## 4. Render built-in metrics

Render's dashboard shows CPU, memory, request count, and error rate under
**Service → Metrics**. No configuration required.

Set a memory alert:
1. Service → Settings → Notifications.
2. Add alert: Memory usage > 80% for 5 minutes → email/Slack.

---

## 5. Vercel analytics (frontend)

Vercel provides Core Web Vitals, page-load times, and error tracking for the
Next.js frontend.

1. Vercel dashboard → Project → **Analytics** → Enable.
2. Add `@vercel/analytics` to the Next.js app (optional, for more detail):
   ```bash
   cd taxmitra-web && npm install @vercel/analytics
   ```
   Then add `<Analytics />` to `app/layout.tsx`.

---

## 6. Log aggregation

TaxBot logs JSON to stdout. Route logs to your preferred sink:

| Platform | How |
|----------|-----|
| Render | Logs auto-appear in dashboard; set up a **Log Drain** to Datadog/Papertrail |
| AWS ECS | `awslogs` driver → CloudWatch Logs (configured in task definition) |
| Docker Compose | `docker compose logs -f backend` |
| Self-hosted | Pipe stdout to a file: `uvicorn api.main:app >> /var/log/taxbot.log 2>&1` |

---

## 7. Recommended monitoring checklist for launch

- [ ] Uptime monitor on `/ready` with 2-failure alert
- [ ] Sentry DSN set and test error visible in dashboard
- [ ] `GET /analytics` polled manually after first 10 chat questions
- [ ] Render memory alert set to 80 %
- [ ] `NOTIFY_WEBHOOK_URL` set so KB-update job sends Slack/Discord notifications
- [ ] KB-update GitHub Actions workflow scheduled and manually triggered once
