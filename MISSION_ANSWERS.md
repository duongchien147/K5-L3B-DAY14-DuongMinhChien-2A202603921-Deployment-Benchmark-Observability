# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found (`01-localhost-vs-production/develop/app.py`)

1. **Hardcode secrets trong source code (`develop/app.py` dòng 17–18):**
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - Khi push lên Git, secret bị lộ ngay lập tức. Bản `production/app.py` (dòng 24) đọc qua `settings` từ biến môi trường (`config.py`).
2. **Không có config management (`develop/app.py` dòng 21–22):**
   - `DEBUG = True`, `MAX_TOKENS = 500` viết cứng trong code, không đổi được theo từng môi trường (dev/staging/prod). Bản `production` tách ra `config.py` đọc từ env vars.
3. **Dùng `print()` và log ra secret (`develop/app.py` dòng 33–34, 38):**
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` làm lộ API key ra stdout/log hệ thống; định dạng text tự do khó parse. Bản `production/app.py` (dòng 28–31, 111–122) dùng `logging` chuẩn JSON và không log secret.
4. **Thiếu endpoint health check & readiness (`develop/app.py`):**
   - Không có `/health` và `/ready` nên platform/load balancer không biết khi nào container sống hay sẵn sàng nhận traffic. Bản `production/app.py` (dòng 135–161) cung cấp đầy đủ `/health` và `/ready`.
5. **Bind `localhost` và hardcode `port=8000` (`develop/app.py` dòng 49–54):**
   - `host="localhost"` chỉ nhận kết nối nội bộ, không chạy được trong Docker/cloud; `port=8000` không nhận `PORT` do platform cấp. Bản `production/app.py` (dòng 194–199) bind `settings.host` (`0.0.0.0`) và `settings.port` (`PORT` env var).
6. **Bật `reload=True` và không có Graceful Shutdown (`develop/app.py` dòng 53):**
   - `reload=True` tốn tài nguyên và không an toàn ở production; không bắt `SIGTERM` hay `lifespan` nên request đang xử lý sẽ bị cắt ngang khi restart. Bản `production/app.py` (dòng 39–68, 180–189) dùng `lifespan` + `signal.signal(signal.SIGTERM, handle_sigterm)` và chỉ bật `reload` khi `settings.debug=True`.

### Exercise 1.2: Kết quả chạy bản `develop`

Lệnh chạy:
```bash
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```

Output thực tế:
```text
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:41:22 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```
*(Quan sát log server: in ra `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this` bằng `print()`).*

### Exercise 1.3: Comparison table (`develop` vs `production`)

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Config & Secrets** | Hardcode trong `app.py` (`OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG = True`) | Đọc từ environment variables qua `config.py` (`settings`) | Tránh lộ secret lên Git; cùng 1 codebase chạy được trên nhiều môi trường (dev/staging/prod) |
| **Input & Validation** | Nhận `question` qua query param (`def ask_agent(question: str)`) | Đọc JSON body, kiểm tra rỗng trả `422` (`HTTPException(status_code=422)`) | API chuẩn RESTful, kiểm soát input chặt chẽ trước khi gọi LLM |
| **Health & Readiness** | Không có | Có `/health` (liveness), `/ready` (readiness, trả 503 nếu chưa sẵn sàng), `/metrics` | Cloud platform & load balancer biết khi nào cần restart container hoặc ngừng route traffic vào |
| **Logging** | `print()` tự do, in cả API key ra stdout | Structured JSON logging (`logging` + `json.dumps`), không log secret | Dễ thu thập và tìm kiếm trên log aggregator (Datadog, Loki) và bảo mật thông tin nhạy cảm |
| **Network & Server** | `host="localhost"`, `port=8000`, `reload=True` cố định | `host=settings.host` (`0.0.0.0`), `port=settings.port` (từ `PORT`), `reload=settings.debug` | Container/cloud cần bind `0.0.0.0` và nhận `PORT` động từ platform; tắt `reload` để ổn định |
| **Shutdown** | Thoát đột ngột khi bị kill | `lifespan` + `signal.signal(signal.SIGTERM, handle_sigterm)` | Hoàn thành các request đang chạy (in-flight) và đóng kết nối sạch sẽ trước khi tắt |
| **CORS** | Không cấu hình | `CORSMiddleware` giới hạn `allowed_origins` từ config | Ngăn trình duyệt từ domain lạ gọi API trái phép |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)
1. **Base image:** `python:3.11` (full Python distribution ~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` đứng trước `COPY . .` (hoặc `COPY app.py`):** Để tận dụng **Docker layer cache**. `requirements.txt` ít thay đổi hơn source code; khi chỉ sửa code (`app.py`), Docker dùng lại layer đã `pip install` trước đó thay vì cài lại toàn bộ dependencies từ đầu.
4. **`CMD` vs `ENTRYPOINT`:**
   - `ENTRYPOINT` định nghĩa file thực thi chính của container (khó bị ghi đè trừ khi truyền `--entrypoint`).
   - `CMD` định nghĩa lệnh hoặc tham số mặc định khi chạy container (`CMD ["python", "app.py"]`), dễ dàng bị ghi đè khi truyền thêm command ở cuối `docker run`.

### Exercise 2.2: Kết quả chạy container `my-agent:develop`
Lệnh chạy:
```bash
docker run --rm -p 8000:8000 my-agent:develop
curl -i -X POST "http://localhost:8000/ask?question=What+is+Docker"
```
Output thực tế:
```text
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:49:35 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & Image size comparison
- **Stage 1 (`builder` — `python:3.11-slim`):** cài `gcc`, `libpq-dev` và `pip install --user -r requirements.txt` vào `/root/.local`. Stage này chứa build tools nên không dùng để deploy.
- **Stage 2 (`runtime` — `python:3.11-slim`):** chỉ tạo non-root user `appuser`, copy các gói đã cài từ `--from=builder /root/.local`, copy `main.py` + `utils/mock_llm.py`, cấu hình `HEALTHCHECK` và chạy `uvicorn` bằng `appuser`. Không mang theo `gcc`/build tools nên gọn và an toàn hơn.

Kích thước đo thực tế bằng `docker images my-agent`:
- **Develop (`my-agent:develop`):** `1.15 GB` (~`1150 MB`)
- **Production (`my-agent:advanced`):** `163 MB`
- **Chênh lệch:** Giảm **~85.8%** (nhỏ hơn ~987 MB, đạt chuẩn `< 500 MB`).

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

**Sơ đồ kiến trúc & giao tiếp giữa các service (mạng `internal` bridge):**
```text
Client ──(HTTP :80 / :443)──▶ [ nginx (nginx:alpine) ]
                                       │
                                       ▼ (proxy nội bộ :8000)
                               [ agent (runtime) ]
                                  │           │
                 (redis://redis:6379/0)   (http://qdrant:6333)
                                  ▼           ▼
                          [ redis:7-alpine ] [ qdrant:v1.9.0 ]
                          (vol: redis_data)  (vol: qdrant_data)
```
- `nginx` là service duy nhất mở port `80`/`443` ra ngoài, điều phối traffic vào `agent` qua mạng nội bộ `internal`.
- `agent` đợi `redis` và `qdrant` ở trạng thái `service_healthy` mới khởi động, giao tiếp qua tên service (`redis:6379`, `qdrant:6333`).

**Kết quả test qua Nginx (`docker compose -p k5-day14-docker up -d`):**
- `GET http://localhost/health`:
```text
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"status":"ok","uptime_seconds":11.3,"version":"2.0.0","timestamp":"2026-11-26T07:51:45.912720"}
```
- `POST http://localhost/ask` (`{"question": "Explain microservices"}`):
```text
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

---

## Part 3: Cloud Deployment

### Exercise 3.1/3.2: Public deployment (Part 6 agent trên Render)
- **URL:** `<Điền URL Render sau khi deploy, vd: https://production-ai-agent.onrender.com>`
- **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

**So sánh `railway.toml` và `render.yaml`:**

| Tiêu chí | `railway.toml` | `render.yaml` |
|---|---|---|
| **Định dạng & cấu trúc** | TOML (`[build]`, `[deploy]`), cấu hình ngắn gọn cho **1 service** trong thư mục hiện tại | YAML (`services:`), chuẩn **Infrastructure as Code (Blueprint)** có thể khai báo nhiều service (web + Redis/DB) trong cùng 1 file |
| **Cách build** | `builder = "DOCKERFILE"` | `runtime: docker` (trong từng item của `services`) |
| **Health check** | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| **Biến môi trường & Secret** | Không bắt buộc khai báo trong `railway.toml`; thường set qua Dashboard hoặc `railway variables set` | Khai báo trực tiếp dưới `envVars:` với `sync: false` (nhập tay trên Dashboard) hoặc `generateValue: true` (Render tự sinh secret, không lộ vào Git) |
| **Lý do khác nhau** | Railway ưu tiên trải nghiệm CLI/UI nhanh (`railway up`), config tối giản | Render Blueprint ưu tiên mô tả toàn bộ hạ tầng bằng YAML để tái tạo môi trường từ Git |

### Exercise 3.3: Cloud Run CI/CD (`03-cloud-deployment/production-cloud-run/`)
Pipeline CI/CD trong `cloudbuild.yaml` tự động chạy khi push lên nhánh `main`, gồm 4 bước tuần tự (`waitFor`):
1. **Test (`test`):** Dùng container `python:3.11-slim` cài `requirements.txt` + `pytest` và chạy `pytest tests/ -v --tb=short`.
2. **Build (`build`):** Build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from`).
3. **Push (`push`):** Đẩy toàn bộ tag image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`deploy`):** Dùng `gcloud run deploy` triển khai lên Cloud Run (`asia-southeast1`), cấu hình public (`--allow-unauthenticated`), scale `1–10` instances, `512Mi` RAM, `1` CPU và inject secret từ Secret Manager (`--set-secrets`). File `service.yaml` định nghĩa cấu hình tương đương theo chuẩn Knative/IaC (kèm `containerConcurrency: 80`, `livenessProbe` `/health`, `startupProbe` `/ready`).

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results (`401` / `200` / `429`)

**1. Exercise 4.1 — API Key Authentication (`04-api-gateway/develop`, `AGENT_API_KEY=secret-key-123`):**
- **Không có key (`401`):**
  ```text
  HTTP/1.1 401 Unauthorized
  content-type: application/json

  {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
  ```
- **Có `X-API-Key: secret-key-123` (`200`):**
  ```text
  HTTP/1.1 200 OK
  content-type: application/json

  {"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
  ```

**2. Exercise 4.2 & 4.3 — JWT (`POST /auth/token` với `student`/`demo123`, che token) & Rate Limiting (`10 req/phút`):**
- Lấy token: `POST http://localhost:8000/auth/token` → `HTTP/1.1 200 OK` (nhận `access_token: <REDACTED_JWT_TOKEN>`).
- Gọi vòng lặp `POST /ask` với `Authorization: Bearer <REDACTED_JWT_TOKEN>`:
  - **Request 1 (`200`):**
    ```text
    HTTP/1.1 200 OK
    content-type: application/json

    {"question":"Test 1","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
    ```
  - **Request 10 (`200`, còn 0 lượt):**
    ```text
    HTTP/1.1 200 OK
    content-type: application/json

    {"question":"Test 10","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":0,"budget_remaining_usd":0.000181}}
    ```
  - **Request 11 (`429`, vượt giới hạn 10 req/60s):**
    ```text
    HTTP/1.1 429 Too Many Requests
    x-ratelimit-limit: 10
    x-ratelimit-remaining: 0
    x-ratelimit-reset: 1795679877
    retry-after: 57
    content-type: application/json

    {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":57}}
    ```

- **Thuật toán trong `rate_limiter.py`:** Dùng **Sliding Window Counter** (lưu `deque` các timestamp trong `window_seconds=60`; trước khi đếm sẽ loại bỏ timestamp cũ ngoài cửa sổ; tài khoản `user` giới hạn `10 req/phút`, `admin` giới hạn `100 req/phút`).

### Exercise 4.4: Cost guard implementation
- **Vai trò:** Rate limit chỉ giới hạn *tốc độ* (requests/phút), còn Cost Guard giới hạn *chi phí tiền* (USD/ngày hoặc USD/tháng) dựa trên số `input_tokens` và `output_tokens` tiêu thụ để tránh vượt ngân sách LLM.
- **Cách hoạt động (`cost_guard.py`):**
  1. Trước khi gọi LLM (`check_budget`): kiểm tra tổng chi phí hiện tại của user so với `daily_budget_usd` (cảnh báo ở mức `80%`, trả về **`HTTP 402 Payment Required`** nếu vượt budget user; trả **`503`** nếu vượt global budget).
  2. Sau khi gọi LLM (`record_usage`): cộng dồn số token và chi phí phát sinh.
  3. **Trong production (stateless):** Không lưu trong RAM (`_records` dict) mà lưu counter trong **Redis** theo key `budget:{user_id}:{YYYY-MM-DD}` (hoặc theo tháng `YYYY-MM`), cập nhật bằng `INCRBYFLOAT` và đặt `EXPIRE` để tự động reset khi sang chu kỳ mới và đồng bộ giữa nhiều instance.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes & `test_stateless.py`

**1. Phân biệt `/health` (Liveness) vs `/ready` (Readiness):**
- **`GET /health` (Liveness probe):** Kiểm tra xem process của agent còn sống hay không (không phụ thuộc Redis/DB ngoài). Nếu `/health` lỗi hoặc timeout, orchestrator (Docker/K8s/cloud platform) sẽ **restart container**.
- **`GET /ready` (Readiness probe):** Kiểm tra xem agent đã sẵn sàng nhận traffic chưa (đã load xong và kết nối được tới Redis/dependencies). Nếu mất kết nối Redis, `/ready` trả về **`503 Service Unavailable`** để load balancer (Nginx) tạm ngừng route request mới vào instance đó (nhưng không restart oan nếu `/health` vẫn 200).

**2. Graceful shutdown (`SIGTERM` + `lifespan`):**
- Khi nhận `SIGTERM` (lúc deploy bản mới hoặc scale down), app đặt cờ `is_ready = False` để load balancer ngừng gửi request mới, đợi các request đang xử lý (`_in_flight_requests`) hoàn thành (tối đa timeout) rồi mới đóng kết nối và thoát êm với exit code `0`.

**3. Vì sao state trong RAM bị hỏng khi scale nhiều instance (Stateless vs Stateful):**
- Nếu lưu `conversation_history` (hoặc rate limit / budget) trong RAM của từng container (`dict` in-memory), mỗi instance chỉ thấy bộ nhớ riêng của mình. Khi Nginx cân bằng tải gửi Request 1 vào `agent-1` và Request 2 vào `agent-2`, `agent-2` sẽ không thấy lịch sử của `agent-1` → mất ngữ cảnh hội thoại và đếm sai limit.
- **Giải pháp:** Chuyển toàn bộ shared state sang **Redis** (`redis://redis:6379/0`) để mọi instance cùng đọc/ghi một nguồn dữ liệu chung.

**4. Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python test_stateless.py` (cổng `8080`, endpoint `POST /chat`):**
```text
Session ID: e7adf9b4-d741-493a-9131-be05369bd5bc

Request 1: [instance-b52c93]  Q: What is Docker?
Request 2: [instance-de74be]  Q: Why do we need containers?
Request 3: [instance-560be1]  Q: What is Kubernetes?
Request 4: [instance-b52c93]  Q: How does load balancing work?
Request 5: [instance-de74be]  Q: What is Redis used for?

Total requests: 5
Instances used: {'instance-560be1', 'instance-de74be', 'instance-b52c93'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```
- **Giải thích:** Nginx phân phối 5 request qua cả 3 container (`instance-b52c93`, `instance-de74be`, `instance-560be1`), nhưng khi truy vấn `GET /chat/{session_id}/history` vẫn đọc đủ toàn bộ 10 message (5 câu hỏi + 5 câu trả lời) vì toàn bộ lịch sử được lưu tập trung trong Redis. (Đã chạy `docker compose -p k5-day14-scaling down` sau khi test xong).

---

## Part 6: Final Project (`06-lab-complete/check_production_ready.py`)

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI log

| Thời điểm / Phần | Đã hỏi AI gì | Nhận được gì | Tự kiểm tra / Chỉnh sửa |
|---|---|---|---|
| Part 1 (CP1) | Hướng dẫn & kiểm tra thực thi CP1 (`01-localhost-vs-production`) | Phân tích 6 anti-pattern trong `develop/app.py`, chạy test `POST /ask?question=Hello` và lập bảng so sánh với `production/app.py` | Đã đối chiếu trực tiếp dòng code trong `develop/app.py`, `production/app.py` và kiểm chứng output `HTTP 200 OK` thực tế từ server |
| Part 2 (CP2) | Hỗ trợ build & test Docker images, Compose stack (`02-docker`) | Trả lời 4 câu hỏi Dockerfile, build `my-agent:develop` & `my-agent:advanced`, test container và stack Nginx/Agent/Redis/Qdrant | Đã tự chạy `docker images`, `docker run` và `docker compose -p k5-day14-docker` để lấy số đo thật (`1.15 GB` vs `163 MB`, giảm ~85.8%) và output `HTTP 200 OK` qua Nginx |
| Part 4 (CP3) | Hỗ trợ chạy & phân tích API Security (`04-api-gateway`) | Chạy test API Key (`401`/`200`), JWT (`student`/`demo123`), vòng lặp Rate Limit (`200`→`429`) và giải thích `rate_limiter.py` + `cost_guard.py` | Đã kiểm chứng output `curl -i` thực tế (request 1–10 trả `200`, request 11 trả `429`), che JWT token trước khi lưu |
| Part 5 (CP4) | Hỗ trợ chạy stack scale 3 instance & `test_stateless.py` (`05-scaling-reliability`) | Giải thích `/health` vs `/ready`, graceful shutdown, stateless + Redis, và chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` | Đã chạy thực tế `test_stateless.py` qua Nginx `:8080`, thấy cả 3 instance (`b52c93`, `de74be`, `560be1`) cùng phục vụ và giữ đủ 10 messages trong Redis |
| Part 6 (CP5) | Hỗ trợ hoàn thiện toàn bộ `TODO` trong `06-lab-complete/` | Viết `config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml` | Đã chạy đầy đủ `python check_production_ready.py` trong WSL2 Ubuntu với Docker & Redis và đạt `PASS 12/12` (`43/43 checks passed`, image `160 MB`, `docker stop` 0.6s) |
| Part 3 (CP6) | So sánh `railway.toml` vs `render.yaml` và tóm tắt Cloud Run CI/CD | Bảng so sánh 2 file config deploy và tóm tắt 4 bước CI/CD từ `cloudbuild.yaml` & `service.yaml` | Đã đối chiếu trực tiếp nội dung `06-lab-complete/railway.toml`, `render.yaml`, `cloudbuild.yaml`, `service.yaml` |
