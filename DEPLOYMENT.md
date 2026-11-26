# Deployment Information

## Public URL

https://production-ai-agent-hzfb.onrender.com

## Platform
Render (Blueprint via `render.yaml`)

## Test Commands

```bash
BASE="https://production-ai-agent-hzfb.onrender.com"
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
- `REDIS_URL` — tự nối từ Key Value `agent-redis` (`fromService` → `connectionString` trong `render.yaml`)
- `AGENT_API_KEY` — secret, nhập trên Dashboard lúc tạo Blueprint (`sync: false`), không có trong code
- `RATE_LIMIT_PER_MINUTE` = `10`
- `DAILY_BUDGET_USD` = `1.0`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
