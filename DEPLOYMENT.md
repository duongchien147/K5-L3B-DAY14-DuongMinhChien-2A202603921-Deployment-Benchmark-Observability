# Deployment Information

## Public URL
<!-- Điền URL sau khi deploy, ví dụ: https://production-ai-agent.onrender.com -->
https://REPLACE_WITH_YOUR_RENDER_URL

## Platform
Render (Blueprint via `render.yaml`)

## Test Commands

```bash
BASE="https://REPLACE_WITH_YOUR_RENDER_URL"
AGENT_API_KEY="REPLACE_WITH_YOUR_KEY"

# 1. Health check → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# 2. Readiness → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# 3. No API key → 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" -d '{"question":"Hello"}'

# 4. With API key → 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Environment Variables Set on Render
- `PORT` — do Render inject tự động
- `ENVIRONMENT` = `production`
- `REDIS_URL` — URL Redis service trên Render (set qua Dashboard, `sync: false`)
- `AGENT_API_KEY` — secret key (set qua Dashboard, `sync: false`)
- `RATE_LIMIT_PER_MINUTE` = `10`
- `DAILY_BUDGET_USD` = `1.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
