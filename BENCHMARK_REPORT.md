# Benchmark & Observability Report — Day 14

**Họ tên:** Dương Minh Chiến — 2A202603921
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11, Python 3.10, agent `develop/app.py` chạy local (v1 cổng 8001, v2 cổng 8002), mock LLM

> Số liệu mục 2–3 lấy từ `06-lab-complete/benchmark-observability/develop/reports/*.json`.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mặc định của `load_test.py`; p50 thực đo ~200 ms nên 500 ms chừa đủ chỗ cho retrieval + LLM mà người dùng vẫn thấy nhanh |
| Error rate `/ask` | < 2 % | Mock có lỗi 503 ngẫu nhiên ~1–2%; ngưỡng 2% bắt được khi lỗi tăng bất thường mà không báo động giả liên tục |
| Accuracy trên golden dataset | ≥ 80 % (gate CI), mục tiêu 100 % | 80% là mặc định quality gate của `run_eval.py`; sau khi sửa KB v2 đạt 23/23 nên dùng `--min-accuracy 1.0` + `--baseline` để chặn mọi regression |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2, 300 request/mức)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.55 | 200.4 | 233.9 | 1682.5 | 0.33% | ✅ PASS |
| 10 | 42.95 | 199.4 | 251.3 | 1698.1 | 2.00% | ✅ PASS |
| 50 | 56.05 | 492.5 | 2032.8 | 2680.7 | 2.33% | ❌ FAIL (p95 + error) |
| 100 | 37.87 | 1034.2 | 5714.8 | 6007.4 | 0.33% | ❌ FAIL (p95) |

**Nhận xét:** RPS chỉ tăng gần tuyến tính từ 1 → 10 (4.55 → 42.95, ×9.4) vì lúc đó mỗi request vẫn ~200 ms, server còn dư năng lực. Từ 10 → 50 RPS chỉ tăng thêm ~30% rồi **giảm** ở 100 (37.87): một process uvicorn đã bão hoà, request phải xếp hàng nên latency tăng (p50 từ 200 → 1034 ms) thay vì throughput tăng. Theo định luật Little, RPS ≈ concurrency / latency: khi latency tăng cùng tốc độ với concurrency thì RPS đứng yên. Điểm gãy SLO nằm giữa 10 và 50 concurrency, nên muốn phục vụ nhiều hơn phải scale ngang (CP8, mục 5).

### 2.2 Tail latency (concurrency 20, 300 request)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 210.7 | 449.1 | 501.9 |
| 0.03 (mặc định) | 260.0 | 483.8 | 1704.2 |
| 0.1 | 347.1 | 1684.4 | 1720.2 |

**Nhận xét:** p99 nhạy nhất: chỉ 3% request chậm (+1500 ms) đã đẩy p99 từ 502 lên 1704 ms, trong khi average chỉ tăng 49 ms (210.7 → 260.0) và trông vẫn "ổn". Ở 10% thì cả p95 vượt SLO (1684 ms) còn average 347 ms vẫn dưới 500 ms. Average gộp đuôi chậm vào số đông request nhanh nên che mất trải nghiệm của những người dùng gặp request chậm; SLO đặt theo p95/p99 mới phản ánh đúng phần người dùng bị ảnh hưởng.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.7 | 108.8 | 116.2 |
| Tổng cost (USD) | 0.000413 | 0.000757 | 0.000813 |
| Cost / câu đúng (USD) | 0.00041295 | 0.00003607 | 0.00003533 |
| Quality gate | FAIL | PASS | PASS (`--min-accuracy 1.0`, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 ("JWT khác gì API key…") | token, hết hạn, chữ ký | Thêm entry KB với từ khoá `jwt`, `api key`, `xác thực`: JWT là token có thời điểm hết hạn (exp) và chữ ký số, khác API key cố định |
| scaling-03 ("Kubernetes HPA scale dựa trên…") | cpu, memory, custom metrics | Thêm entry KB với từ khoá `hpa`, `kubernetes`, `autoscal`: HPA scale theo CPU, memory hoặc custom metrics |

Cả hai entry thêm ở **cuối** `KNOWLEDGE_BASE` để khi hoà số keyword thì entry cũ vẫn thắng, tránh làm sai câu khác (kết quả: 0 regression so với baseline `eval_v2.json`). Đã chép cùng bản sửa sang `production/utils/mock_llm.py`.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v2 dùng retrieval nên prompt dài hơn: tokens/câu gần gấp đôi (57.7 → 108.8) và tổng cost tăng 83%, p50 tăng ~30 ms do bước tìm KB. Nhưng accuracy từ 4.3% lên 91.3%, nên **cost / câu đúng giảm 11 lần** (0.000413 → 0.000036 USD). So "cost / câu" thì v1 rẻ hơn, nhưng tiền trả cho câu sai là tiền phí; "cost / câu đúng" mới cho thấy v2 rẻ hơn thực sự. p95 của v2 trong eval còn thấp hơn v1 (231.6 so với 1520.2 ms) chỉ là do v1 dính một request slow ngẫu nhiên, không phải v1 chậm hơn về bản chất.

**Chặn merge bằng exit code (Exercise 7.3):** `run_eval.py` trả exit code ≠ 0 khi quality gate FAIL (accuracy dưới `--min-accuracy` hoặc có regression so với `--baseline`). Trong CI, chạy bước eval sau khi bật agent; job fail thì PR bị chặn nhờ branch protection "required status check":

```yaml
# .github/workflows/eval.yml (rút gọn)
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r 06-lab-complete/benchmark-observability/develop/requirements.txt
      - working-directory: 06-lab-complete/benchmark-observability/develop
        run: |
          AGENT_VERSION=v2 PORT=8002 python app.py &
          sleep 5
          python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0             --baseline reports/eval_v2_fixed.json --out reports/eval_ci.json
```

---

## 4. Observability stack (production)

Stack chạy bằng `docker compose -p k5-day14-observability`. Mọi lệnh `run locust` dùng thêm `--no-deps`: nếu không, Compose tạo lại service `agent` theo `deploy.replicas: 2` và env mặc định, làm sai số instance và mất cấu hình fault injection.

Sửa một lỗi trong `production/Dockerfile`: user `agent` có home là `/app` nên Python không thấy package cài ở `/home/agent/.local` (container crash `ModuleNotFoundError: uvicorn`). Đã thêm `ENV PYTHONUSERBASE=/home/agent/.local`.

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải: [`screenshots/grafana-dashboard.png`](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger: [`screenshots/jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [`screenshots/jaeger-error-trace.png`](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus, 2 alert đang **firing**: [`screenshots/prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png)

### Exercise 7.4 — trả lời

Số đo khi 3 agent chịu tải 50 user Locust (truy vấn Prometheus, cửa sổ 1 phút):

1. **p95 = 293.9 ms, avg = 235.6 ms.** Khoảng cách nhỏ (~58 ms) nghĩa là phần lớn request đồng đều quanh 200 ms; chỉ ~3% request "slow" (+1500 ms) nằm ở đuôi và hiện ra ở p99 (~1.7 s) chứ không phải ở p95 hay avg. Nếu p95 bắt đầu tách xa avg thì đó là dấu hiệu đuôi chậm đang lan rộng.
2. **Có, Nginx chia đều:** 3 instance nhận 11.29 / 11.21 / 11.27 req/s. Nginx dùng round-robin trên upstream `agent:8000 resolve`, các instance giống hệt nhau nên tải gần như bằng nhau.
3. **Input tokens/s (2358.5) lớn hơn output (1248.7)** vì agent v2 làm RAG: prompt gửi LLM gồm câu hỏi + đoạn tài liệu retrieve từ knowledge base + system prompt, còn câu trả lời thì ngắn. Vì vậy cost của RAG chủ yếu nằm ở input.
4. **`curl http://localhost:8080/metrics` trả `404 Not Found`** từ Nginx. `nginx.conf` chặn riêng `location = /metrics` vì metrics chỉ dành cho Prometheus scrape trực tiếp từng container trong mạng Docker nội bộ (qua DNS service discovery). Không public metrics ra ngoài để tránh lộ thông tin nội bộ; ngoài ra scrape qua load balancer sẽ trúng ngẫu nhiên một instance nên số liệu sai.

### 4.2 Thí nghiệm "phá hệ thống"

Tải nền: Locust 30 user, 3 agent. Thời gian đo từ lúc tạo lại agent với cấu hình mới tới khi Prometheus báo `firing` (poll API `/api/v1/alerts` mỗi 3–5 s).

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 1 phút 23 s (pending sau ~22 s, `for: 1m`) | Error rate + Requests/s theo status code (503 tăng) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 2 phút 13 s (pending sau ~12 s, `for: 2m`) | Latency /ask p50/p95/p99 (p95 vượt đường 1 s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | 2 phút 11 s (burn rate $1.65/h → $15.85/h) | Cost burn rate (USD/giờ) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | 43 s (`for: 30s` + chu kỳ scrape) | Instances up (3 → 2) |
| E | `AGENT_VERSION=v1` | Không alert SLO nào (theo dõi 4 phút) | — | Không panel nào báo đỏ; latency, error rate vẫn bình thường |

A và B làm cùng lúc; ảnh `prometheus-alert-firing.png` chụp lúc cả 2 alert đang firing. Thời gian tới firing ≈ thời gian để rate 1 phút vượt ngưỡng + `for` của rule + chu kỳ evaluate. Lỗi tăng (A) bị phát hiện nhanh hơn latency (B) vì rule error chỉ cần `for: 1m`.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

v1 vẫn trả 200 nhanh, nên mọi chỉ số hạ tầng (latency, error, saturation) đều xanh: đây là lỗi **chất lượng**, không phải lỗi hệ thống. Cách phát hiện:
- **Chặn trước khi deploy:** quality gate `run_eval.py --baseline` trong CI (v1 chỉ 4.3% so với 100% → exit 1, không cho merge).
- **Giám sát chất lượng khi chạy:** chạy eval định kỳ (canary/synthetic) trên golden dataset với production và xuất accuracy thành metric để có alert, ví dụ `agent_eval_accuracy < 0.8`.
- **Tín hiệu gián tiếp:** feedback người dùng (thumbs down), tỉ lệ câu không retrieve được context, đếm `agent_version` trong metric để thấy version lạ đang chạy, và tokens/câu giảm đột ngột (v1 57.7 so với v2 108.8).

**Vì sao lỗi 504 ở Nginx (thí nghiệm D) không hiện trên metric của agent?**

Khi `docker pause` một instance, request mà Nginx đã gửi tới instance đó bị treo. Nginx chờ hết `proxy_read_timeout 10s` (trong `nginx/nginx.conf`) rồi tự trả **504 Gateway Timeout** cho client. Agent bị pause không chạy được dòng code nào, nên không bao giờ ghi request đó vào `http_requests_total` hay histogram latency. Các instance còn sống cũng không thấy request này. Vì vậy panel Error rate (tính từ metric của agent) vẫn xanh dù người dùng nhận lỗi: metric chỉ phản ánh những gì *chính service đó* nhìn thấy. Trong thí nghiệm này chỉ `AgentInstanceDown` báo được, và báo gián tiếp qua việc Prometheus không scrape được `/metrics`. Mình không ghi lại số lỗi 504 phía Locust trong lượt chạy D, nên phần trên là giải thích theo cấu hình Nginx chứ không kèm số đo.

Cách bắt loại lỗi này trong production:
- Đo ở **tầng load balancer**: xuất metric của Nginx (status code theo upstream, qua `nginx-prometheus-exporter` hoặc log access dạng JSON) và alert khi tỉ lệ 5xx ở Nginx tăng.
- **Synthetic check / blackbox probe** từ bên ngoài gọi `/ask` định kỳ: đo đúng trải nghiệm người dùng, kể cả lỗi xảy ra trước khi tới agent.
- Đặt **timeout ngắn hơn** và để `proxy_next_upstream` thử instance khác, kết hợp readiness probe để load balancer bỏ instance treo nhanh hơn.

### 4.3 Debug bằng trace

Chọn trace chậm nhất (Jaeger, service `observable-agent`, Longest First):

- `trace_id`: `a38a6530a3cbf5677956cb306cdbe293`
- Tổng thời gian: 2330.0 ms (Jaeger hiện 2.3 s)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (2156.5 ms, 92.6%). `agent.retrieve_context` chỉ 70.1 ms (3.0%). Nút thắt là lời gọi LLM (request rơi vào nhóm "slow" của mock), không phải retrieval.
- Dòng log tương ứng (`docker compose -p k5-day14-observability logs agent | grep a38a6530a3cbf5677956cb306cdbe293`):

```json
{"ts": "2026-11-26T09:01:20.125982+00:00", "level": "INFO", "service": "observable-agent", "instance": "025a48796cb3", "event": "llm_call", "trace_id": "a38a6530a3cbf5677956cb306cdbe293", "span_id": "385c47bee00ab828", "request_id": "8f1eef670790", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1696.6}
{"ts": "2026-11-26T09:01:20.126628+00:00", "level": "INFO", "service": "observable-agent", "instance": "025a48796cb3", "event": "http_request", "trace_id": "a38a6530a3cbf5677956cb306cdbe293", "span_id": "385c47bee00ab828", "request_id": "8f1eef670790", "method": "POST", "route": "/ask", "status": 200, "ms": 1869.7}
```

Số ms trong log (`llm_ms` 1696.6, `ms` 1869.7) thấp hơn thời lượng span vì hai bên đo ở hai điểm khác nhau: log đo trong handler, còn span tính cả phần middleware/instrumentation quanh request, trên container giới hạn 0.5 CPU khi đang chịu tải 100 user.

Trace lỗi: `f2e02c267f255007e0bde7d022732cf9` (275 ms, `POST /ask` → 503). Span `chat mock-llm-small` có status ERROR và event `exception` (`LLMError: Upstream LLM error: 503 Service Unavailable (mock)`); log cùng `trace_id` có `"event": "llm_error"` và `"status": 503`.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu dòng `/ask` trong `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`:

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 57.35 | 200 | 540 | 1700 | 80 / 7039 (1.14%) |
| 3 | 59.15 | 190 | 240 | 1700 | 69 / 7208 (0.96%) |

**Giải thích kết quả:** Scale lên 3 instance **cải thiện rõ p95** (540 → 240 ms, về dưới SLO 500 ms). Với 1 container giới hạn 0.5 CPU, 100 user làm request phải xếp hàng trong event loop; chia ra 3 container thì mỗi instance chỉ nhận ~1/3 tải nên hết xếp hàng. RPS gần như không đổi (57 → 59) vì Locust là mô hình *closed-loop*: 100 user, mỗi user chờ `wait_time` giữa các lần gọi, nên RPS bị giới hạn bởi số user chứ không phải bởi server. p99 giữ ~1700 ms ở cả hai mức vì đuôi đó do mock LLM cố ý chậm thêm 1500 ms (`MOCK_SLOW_RATE=0.03`). Scale không sửa được độ chậm của dependency: nút thắt còn lại nằm ở LLM upstream (cần timeout, retry hoặc hedging), không ở agent.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average che giấu đuôi chậm: 3% request chậm làm p99 tăng hơn 3 lần mà average chỉ tăng ~50 ms. SLO phải đặt theo p95/p99.
  2. Metrics hạ tầng không bắt được lỗi chất lượng (thí nghiệm E): cần eval trên golden dataset làm quality gate trong CI và giám sát accuracy khi chạy. "Cost / câu đúng" mới cho thấy RAG đáng tiền.
  3. Ba tín hiệu bổ sung cho nhau: metric/alert báo *có* vấn đề (p95 > 1 s), trace chỉ ra *ở đâu* (span LLM chiếm 92.6%), log JSON có `trace_id` cho *chi tiết* (model, tokens, cost) của đúng request đó.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Metric accuracy từ eval định kỳ hoặc canary, alert khi < 80%; tỉ lệ feedback xấu từ người dùng.
  - Alert theo **error budget burn rate** nhiều cửa sổ (1h/6h) thay vì ngưỡng tức thời, để giảm báo động giả.
  - Saturation: CPU/memory container, độ dài hàng đợi request, kết nối Redis; alert khi `/ready` fail.
  - Cost theo ngày/user so với budget; alert khi tokens/câu tăng hoặc giảm bất thường (dấu hiệu prompt hoặc version bị đổi).
  - Alertmanager gửi cảnh báo qua Slack/PagerDuty, kèm link dashboard và runbook.
