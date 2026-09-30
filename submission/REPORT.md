# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Tuấn Đạt
- **MSSV:** 2A202602623
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/TuanDatt08/K4-L3B-DAY13-LeTuanDat-2A202602623-Monitoring-LLMOps
- **Commit SHA cuối:** `eb87ee17e17a28cc88da462bf1db66587cd1d1c9` (commit chứa toàn bộ source, config và evidence; commit sau đó chỉ điền URL/SHA vào báo cáo này)
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602623`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [`evidence/01-pytest.png`](evidence/01-pytest.png), [`.txt`](evidence/01-pytest.txt) |
| Log validator | [`evidence/02-log-validator.png`](evidence/02-log-validator.png), [`.txt`](evidence/02-log-validator.txt) |
| Dashboard validator | [`evidence/03-dashboard-validator.txt`](evidence/03-dashboard-validator.txt) |
| Structured log | [`evidence/04-structured-log.png`](evidence/04-structured-log.png) |
| PII redaction | [`evidence/05a-pii-input.png`](evidence/05a-pii-input.png) (input chứa PII giả), [`evidence/05b-pii-redacted-log.png`](evidence/05b-pii-redacted-log.png) (log đã che) |
| Trace list | [`evidence/06-trace-list.png`](evidence/06-trace-list.png) |
| Trace waterfall | [`evidence/07-trace-waterfall.png`](evidence/07-trace-waterfall.png) |
| Trace metadata | [`evidence/08a-trace-generation.png`](evidence/08a-trace-generation.png) (generation: model, token, cost, prompt), [`evidence/08b-trace-metadata.png`](evidence/08b-trace-metadata.png) (root: correlation_id, prompt name/label/version) |
| Prompt versions | [`evidence/09-prompt-versions.png`](evidence/09-prompt-versions.png), trace baseline [`09b`](evidence/09b-trace-baseline-v1.png), trace candidate [`09c`](evidence/09c-trace-candidate-v2.png) |
| Prompt rollback | trước [`10a`](evidence/10a-production-v1-before.png) → promote [`10b`](evidence/10b-production-v2-promoted.png) → rollback [`10c`](evidence/10c-production-v1-rollback.png); log [`10d`](evidence/10d-prompt-requests-log.txt); trace [`10e`](evidence/10e-trace-production-v2.png), [`10f`](evidence/10f-trace-production-v1-after-rollback.png) |
| Dashboard runtime | [`evidence/11-dashboard-overview.png`](evidence/11-dashboard-overview.png) |
| Incident metric | [`evidence/12-incident-metric.png`](evidence/12-incident-metric.png) |
| Incident log | [`evidence/13-incident-log.png`](evidence/13-incident-log.png), [`.txt`](evidence/13-incident-log.txt) |
| Incident trace | [`evidence/14a-incident-trace-tree.png`](evidence/14a-incident-trace-tree.png), [`evidence/14b-incident-trace-timeline.png`](evidence/14b-incident-trace-timeline.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (21 records; 20 thiếu required field; 20 thiếu enrichment; 0 correlation ID) | 100/100 — cuối CP1: 26 records, 10 correlation ID ([ảnh](evidence/02-log-validator.png)); trên log cuối: 127 records, 53 correlation ID, 0 thiếu field, 0 PII ([txt](evidence/02-log-validator.txt)) | Baseline thiếu `correlation_id` (middleware trả `MISSING`) và chưa bind context |
| `validate_dashboard.py` | HỢP LỆ 6/6 | HỢP LỆ 6/6 + dashboard runtime | Validator chỉ kiểm tra contract YAML; dashboard runtime dựng bằng [`scripts/build_dashboard.py`](../scripts/build_dashboard.py) |
| `pytest` | 22 passed | 27 passed | CP1 thêm test CCCD, thẻ; CP2 thêm test dashboard builder; CP4 thêm test validate `x-request-id` |
| Số traces hợp lệ | 0 (10 request có trace nhưng chỉ có root observation) | ≥ 11 trace có đủ root + `retrieval` + `llm-generation` sau CP2 (tổng 31 root trace trong project, gồm cả trace trước CP2) | [`06-trace-list`](evidence/06-trace-list.png) |
| Số PII leak | 0 | 0 (validator trên 127 records / 53 correlation ID, gồm request chứa email/SĐT/CCCD/thẻ giả) | Baseline 0 là nhờ `summarize_text`, processor `scrub_event` chưa được đăng ký; bản cuối đăng ký `scrub_event` trước khi ghi file |
| Latency P95 / TTFT P95 | 2206 ms / 50 ms (P50 385 ms, n=10) | 1265 ms / 50 ms (P50 152 ms, P99 1681 ms, 28 request trong cửa sổ 60 phút) | P95/P99 cao hơn P50 do các request đầu tiên sau mỗi lần restart API (prompt cache rỗng, phải fetch prompt từ Langfuse) — vẫn dưới SLO 3000 ms |
| Retrieval success rate | 100% (10/10, 0 `request_failed`) | 100%, error rate 0% | Chưa bật practice `tool_fail` |

Output baseline đầy đủ: [`evidence/00-baseline.txt`](evidence/00-baseline.txt). Log baseline được đổi tên thành `data/logs.baseline.jsonl` (không commit) trước khi đo lại.

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) gọi `clear_contextvars()` ở đầu mỗi request để không rò context từ request trước, nhận header `x-request-id` nếu client gửi **và đúng format** `req-<8 hex>` (regex `REQUEST_ID_PATTERN`), còn thiếu hoặc sai format thì sinh mới `req-<8 hex>` từ `uuid4` — header là input không tin cậy, không cho chuỗi tùy ý (dài, chứa PII) đi vào log/trace; có test trong [`tests/test_middleware.py`](../tests/test_middleware.py). ID được `bind_contextvars` nên mọi log trong request tự có `correlation_id`, được lưu vào `request.state` để truyền vào `LabAgent.run` (ghi vào trace metadata), và được trả lại qua response header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** [`app/main.py`](../app/main.py) bind `user_id_hash` (SHA-256 cắt 12 ký tự, không log `user_id` thô), `session_id`, `feature`, `model`, `env` trước dòng `request_received`, nên cả `request_received`, `response_sent` và `request_failed` đều có đủ context. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đăng ký trong [`app/logging_config.py`](../app/logging_config.py) **trước** `JsonlFileProcessor` và `JSONRenderer`; structlog chạy processor theo thứ tự nên payload đã được che trước khi serialize/ghi file. Ngoài ra `summarize_text` scrub và cắt preview trước khi đưa vào log. Pattern trong [`app/pii.py`](../app/pii.py) che email, SĐT Việt Nam (`0…`/`+84…` có dấu cách/chấm/gạch), CCCD 12 số và thẻ 16 số.
- **Cách kiểm chứng kết quả:** (1) `python scripts/validate_logs.py` đạt 100/100: 0 record thiếu field, 0 thiếu enrichment, 10 correlation ID khác nhau, 0 PII leak ([ảnh](evidence/02-log-validator.png)). (2) Gửi request với header `x-request-id: req-abcdef12` và message chứa email/SĐT/CCCD/thẻ giả; response trả đúng `correlation_id=req-abcdef12` ([ảnh](evidence/05a-pii-input.png)), hai dòng log `request_received`/`response_sent` cùng ID đó và PII đã thành `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`; số thẻ cũng đã bị thay bằng `[REDACTED_CREDIT_CARD]` rồi mới bị cắt ở giới hạn 80 ký tự của preview nên chỉ thấy `[REDA...` ([ảnh](evidence/05b-pii-redacted-log.png)). (3) Unit test trong [`tests/test_pii.py`](../tests/test_pii.py) cho cả 4 loại PII.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** trace được gửi bằng key của project `day13-k4-l3b-2A202602623` (thấy tên project trong [ảnh trace list](evidence/06-trace-list.png), lọc `isRootObservation:true`); workload do tôi chạy bằng `scripts/load_test.py` và `curl` với `x-request-id` tự đặt (`req-00000b02`, `req-00000c01`, `req-0000d002`, `req-0000d001`) — các ID này xuất hiện cả trong `data/logs.jsonl` và trace metadata.
- **Cấu trúc root/retrieval/generation observations:** trace `day13-agent-request` → root `lab-agent-run` (type `agent`, `@observe` trong [`app/agent.py`](../app/agent.py)) → hai child: `retrieval` (type `retriever`, `@observe` trên `retrieve()` trong [`app/mock_rag.py`](../app/mock_rag.py)) và `llm-generation` (type `generation`, `@observe` trên `FakeLLM.generate()` trong [`app/mock_llm.py`](../app/mock_llm.py)). Generation được `update_current_generation` với `model`, `usage_details` (input/output), `cost_details` ($3/1M input, $15/1M output, cùng công thức `_estimate_cost`) và `completion_start_time` (TTFT); prompt được link nhờ generation chạy trong `propagate_attributes(prompt=managed_prompt)`. `capture_input/output=False` để không đưa prompt/answer thô (có thể chứa PII) lên Langfuse; root chỉ có `query_preview` đã scrub. Ảnh: [waterfall](evidence/07-trace-waterfall.png), [generation](evidence/08a-trace-generation.png).
- **Cách nối trace với log:** middleware truyền `correlation_id` vào `LabAgent.run`, được ghi vào trace metadata qua `propagate_attributes(metadata=...)`. Ví dụ trace `a565a2cad7a92df4455904879e101458` có `correlation_id=req-2c904782` ([ảnh](evidence/08b-trace-metadata.png)); log `response_sent` cùng ID có `tokens_in=28`, `tokens_out=127` (= 155 tokens trên trace), `cost_usd=0.001989` (= $0.001989 trên trace), `user_id_hash=105a9cef3903` (= `user_id` trên trace).
- **Prompt name:** `day13-chat` (text prompt, 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** version 1, labels `baseline` (+ `production` lúc đầu và sau rollback).
- **Version/label candidate:** version 2 (thêm dòng `Answer in at most 3 sentences.`), label `candidate`. Cùng input "How do I debug tail latency?" → `tokens_in` 27 (v1) vs 35 (v2).
- **Trace ID của mỗi version:**

  | Label trong `.env` | Version | correlation_id | Trace ID | tokens_in |
  |---|---|---|---|---|
  | `baseline` | 1 | `req-00000b02` | `cb08ddcd9c6b2aefe8c13f184e750504` | 27 |
  | `candidate` | 2 | `req-00000c01` | `234dd25e0584c4895f4f237b9c7fa5ed` | 35 |
  | `production` (sau promote) | 2 | `req-0000d002` | `8d7f0a06b14fdbb62b6044274dcb267b` | 35 |
  | `production` (sau rollback) | 1 | `req-0000d001` | `2ae3c624f0f87470a22a39f2e0895ec4` | 27 |

- **Cách promote và rollback `production`:** trên Langfuse UI, gắn label `production` vào version 2 (label tự rời version 1) → [ảnh](evidence/10b-production-v2-promoted.png); restart API (prompt cache 60s) và gửi `req-0000d002` → trace ghi `production` v2. Rollback: gắn lại `production` vào version 1 → [ảnh](evidence/10c-production-v1-rollback.png); restart và gửi `req-0000d001` → trace ghi `production` v1, `tokens_in` về 27. Không sửa code: app chỉ hỏi Langfuse theo `LANGFUSE_PROMPT_NAME` + `LANGFUSE_PROMPT_LABEL`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** tự viết [`scripts/build_dashboard.py`](../scripts/build_dashboard.py) đọc `data/logs.jsonl`, đọc title/unit/threshold từ [`config/dashboard.yaml`](../config/dashboard.yaml) và ghi `data/dashboard.html` (Chart.js). Time range 60 phút kết thúc ở log mới nhất, bucket theo phút, trang tự reload 30s (`--watch` build lại mỗi 30s). Mỗi panel có đơn vị, dòng tóm tắt và đường threshold nét đứt: (1) Latency P50/P95/P99 + TTFT P95, SLO P95 ≤ 3000 ms; (2) Traffic request/phút, min ≥ 1; (3) Error rate % + retrieval success %, error ≤ 2%, kèm breakdown `error_type`; (4) Cost cộng dồn USD, budget ≤ $2.5; (5) tokens_in/tokens_out cộng dồn, limit ≤ 50 000; (6) Quality mean, SLO ≥ 0.75. Số liệu lúc chụp ([ảnh](evidence/11-dashboard-overview.png)): 28 request, P50 152 / P95 1265 / P99 1681 ms, TTFT P95 50 ms, error 0%, retrieval 100%, cost $0.0591, tokens 936 in / 3752 out, quality 0.886. Percentile dùng lại `app.metrics.percentile` để khớp endpoint `/metrics`.
- **SLO và lý do chọn:** [`config/slo.yaml`](../config/slo.yaml) — `fast_successful_requests`: 99.5% request trong 28 ngày phải có `response_sent` với `latency_ms <= 3000`. Giữ ngưỡng 3000 ms vì baseline P50 ~150–390 ms và TTFT ~50 ms, nên 3000 ms chỉ bị vượt khi có sự cố thật (ví dụ retrieval chậm thêm 2.5s như scenario `rag_slow`), không bị cold start bình thường (1–2s) làm cháy budget. Request lỗi không có `response_sent` nên tự động là bad event — một SLO bao cả latency lẫn availability.
- **Cách tính error budget:** error budget = 100% − 99.5% = 0.5%. Với 10 000 request/28 ngày → tối đa 50 request lỗi hoặc > 3000 ms. Workload lab chỉ 10 request/lượt nên 1 request xấu đã là 10% (gấp 20 lần budget) → alert dùng `duration` 5–10 phút để tránh báo động theo từng request lẻ.
- **Ba alert và runbook tương ứng:** [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook trong [`docs/alerts.md`](../docs/alerts.md), đều gửi Slack `#k4-l3b-alerts`, owner `student-2A202602623`: (1) `HighLatencyP95` — warning, P95 > 2000 ms trong 5m (ban đầu 3000 ms, hạ xuống sau challenge — xem mục 7); (2) `HighErrorRateOrRetrievalFailure` — critical, error rate > 2% hoặc retrieval success < 90% trong 5m; (3) `CostOrTokenSpike` — warning, cost/phút > 2× baseline hoặc avg `tokens_out` > 400 trong 10m. Mỗi runbook có 3 bước Metrics → Logs (`correlation_id`) → Trace (so span `retrieval` vs `llm-generation`) và mitigation (rollback prompt label, khôi phục retrieval, giới hạn token).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, seed 1312, affected feature `monitoring`, ngưỡng 2000 ms). File `config/challenge.json` nằm trong `.gitignore`, không commit.
- **Khoảng thời gian điều tra:** 2026-09-30 05:05:00 → 05:05:44 UTC (12:05:00 → 12:05:44 giờ Việt Nam), 2 lượt `python scripts/load_test.py --challenge --concurrency 5` sau `python scripts/inject_incident.py`.
- **Triệu chứng từ metrics:** panel Latency ([ảnh](evidence/12-incident-metric.png)) — phút 05:05 P50/P95 tăng từ ~150 ms lên **~2650 ms** (> ngưỡng 2000 ms), tóm tắt cửa sổ: P50 153 / P95 2653 / P99 2653 ms. **TTFT P95 vẫn 50 ms**, error rate 0%, retrieval success 100%, cost/token tăng bình thường theo traffic → sự cố chỉ là *chậm*, không lỗi, và phần chậm nằm trước bước LLM sinh token.
- **Log line và correlation ID liên quan:** cả 10/10 `response_sent` có `feature=monitoring` đều `latency_ms` 2651–2653, `ttft_ms` 50 ([ảnh](evidence/13-incident-log.png), [text](evidence/13-incident-log.txt)). Request đại diện `correlation_id=req-d2af6ac9`: `request_received` lúc 05:05:00.536Z, `response_sent` lúc 05:05:03.190Z với `latency_ms=2652`, `ttft_ms=50`, `tokens_in=34`, `tokens_out=122`, `cost_usd=0.001932`, `tool_success=true`, `session_id=k4-l3b-challenge-s02`.
- **Trace ID và span gây ảnh hưởng:** trace `2a0723a50a196d1ada0578af22b82679` (metadata `correlation_id=req-d2af6ac9`, cùng `user_id=2f2fc5ebba0b`, $0.001932, 156 tokens = 34 + 122 như log) ([tree](evidence/14a-incident-trace-tree.png), [timeline](evidence/14b-incident-trace-timeline.png)). Root `lab-agent-run` 2.65 s, trong đó span **`retrieval` = 2.50 s (~94%)**, `llm-generation` = 152 ms (bình thường, giống baseline). Prompt vẫn `production` v1 → không phải do đổi prompt.
- **Root cause:** bước retrieval (RAG/vector store) chậm thêm ~2.5 s cho mọi request trong khoảng sự cố; retrieval vẫn trả đúng tài liệu (`doc_count=1`, `tool_success=true`) nên không sinh lỗi, chỉ làm latency end-to-end vượt ngưỡng. Khớp với scenario `rag_slow` mà challenge bật (`/health` → `rag_slow: true`; [`app/mock_rag.py`](../app/mock_rag.py) `time.sleep(2.5)` khi cờ bật). Hệ quả phụ: endpoint `async def` gọi code đồng bộ nên 5 request đồng thời bị xếp hàng — client đo 10.6–13.3 s dù server ghi 2.65 s/request.
- **Fix action:** khôi phục retrieval về bình thường: `python scripts/inject_incident.py --disable` (tương đương khôi phục/scale lại vector store). Kiểm chứng: chạy lại cùng workload challenge, latency phải về ~150 ms. Kết quả sau fix (05:41:28–05:41:29 UTC, cùng 5 query challenge, concurrency 5): server `latency_ms` 151–154, `ttft_ms` 50 — về đúng baseline; client đo ~793 ms thay vì 10.6–13.3 s ([log](evidence/15-incident-recovered.txt)).
- **Preventive measure:**
  1. **Đã sửa:** alert `HighLatencyP95` ban đầu đặt > 3000 ms **không bắt được** sự cố này (P95 2650 ms). Đã hạ ngưỡng xuống **> 2000 ms** trong [`config/alert_rules.yaml`](../config/alert_rules.yaml) và runbook [`docs/alerts.md`](../docs/alerts.md) — cảnh báo sớm trước khi vi phạm SLO 3000 ms. Đề xuất tiếp: SLI theo span `p95(retrieval) > 500 ms` để chỉ thẳng thành phần hỏng.
  2. Timeout cho retrieval (ví dụ 800 ms) + fallback trả lời không kèm context / cache kết quả retrieval cho câu hỏi lặp lại, để retrieval chậm không kéo cả request.
  3. Không chặn event loop: đổi `/chat` sang `def` hoặc chạy `agent.run` qua `run_in_threadpool` để một bước chậm không làm các request đồng thời phải xếp hàng (13.3 s phía client).
  4. Runbook `HighLatencyP95` trong [`docs/alerts.md`](../docs/alerts.md) đã có bước "so TTFT với P95" và "so span retrieval vs generation" — chính là đường điều tra dùng ở đây.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** không gửi prompt/answer thô lên Langfuse. Các observation dùng `@observe(..., capture_input=False, capture_output=False)`, còn model, usage, cost và TTFT được ghi tường minh bằng `update_current_generation`. Lý do: message của người dùng có thể chứa email, SĐT, CCCD, số thẻ (chính `data/sample_queries.jsonl` có), và nếu capture tự động thì PII sẽ nằm trên một hệ thống bên ngoài dù log local đã được scrub. Đổi lại, trace không có nội dung câu hỏi/trả lời; tôi bù bằng `query_preview` đã scrub trong metadata và `correlation_id` để tra ngược sang log. Quyết định thứ hai: tự viết `scripts/build_dashboard.py` (đọc thẳng `data/logs.jsonl` + `config/dashboard.yaml`, không thêm dependency) thay vì dựng Grafana, để dashboard dùng đúng log contract và chạy lại được chỉ bằng `requirements.txt`.
- **Một lỗi/blocker đã gặp:** khi so sánh prompt, request `req-00000b01` được gửi hai lần để lấy trace cho label `baseline`, nhưng lần đầu trace ghi `prompt_label=production` (v1), lần sau ghi `prompt_label=candidate` (v2) — không lần nào là `baseline`.
- **Cách tìm nguyên nhân và xử lý:** đối chiếu `tokens_in` trong response (lần sau là 35 thay vì 27 như v1) và metadata trên trace cho thấy app không dùng label mong muốn; kiểm tra lại thì `LANGFUSE_PROMPT_LABEL` trong `.env` chưa được đổi/lưu sang `baseline` đúng lúc API khởi động, và `uvicorn --reload` chỉ theo dõi file `.py`, không đọc lại `.env` — biến môi trường chỉ được nạp khi khởi động. Xử lý: sửa `.env`, dừng hẳn API rồi chạy lại, dùng correlation ID mới (`req-00000b02`) để không lẫn với trace sai; trace mới đúng `baseline` v1. Từ đó mỗi lần đổi label (và cả khi promote/rollback trên UI, vì prompt được cache 60 s) tôi đều restart API và kiểm tra `tokens_in` ngay trong response trước khi mở trace. Blocker thứ hai: ảnh metadata trên Langfuse có dòng `scope.attributes` hiển thị public key `pk-lf-…`; tôi cắt bỏ phần đó trước khi đưa vào evidence và rà lại toàn bộ ảnh.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời *có gì bất thường và từ lúc nào* — ở challenge, panel latency cho thấy P50/P95 nhảy từ ~150 lên ~2650 ms tại 05:05 trong khi TTFT giữ 50 ms và error 0%, nên đã khoanh vùng được là "chậm, không lỗi, chậm trước bước LLM". Logs trả lời *request nào bị ảnh hưởng*: lọc `response_sent` có `latency_ms > 2000` ra 10/10 request `feature=monitoring`, chọn `req-d2af6ac9`. Traces trả lời *bước nào gây ra*: trace cùng `correlation_id` cho thấy span `retrieval` chiếm 2.50/2.65 s. `correlation_id` là khóa nối log với trace; tôi còn kiểm chứng chéo bằng token (34 + 122 = 156) và cost ($0.001932) trùng nhau ở hai nơi. Không lớp nào đủ một mình: metric không chỉ ra request, log không có thời gian từng bước, còn mở trace ngẫu nhiên thì không biết trace nào đáng xem.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt là một phần của "code" nhưng thay đổi được mà không cần deploy, nên phải truy được mỗi request dùng version nào — trong bài, cùng một câu hỏi cho `tokens_in` 27 với v1 và 35 với v2 (+30% token đầu vào chỉ vì thêm một câu), thể hiện prompt ảnh hưởng trực tiếp tới cost. Label `production` giúp rollback chỉ bằng việc chuyển label về v1 trên Langfuse, không sửa code và có trace chứng minh trước/sau (`8d7f0a06…` v2 → `2ae3c624…` v1). SLO 99.5% trong 28 ngày với error budget 0.5% cho biết khi nào sự cố đủ nghiêm trọng để dừng thay đổi và ưu tiên ổn định; token/cost được theo dõi như một chỉ số sức khỏe vì LLM có thể "đúng mà đắt".
- **Điều quan trọng nhất đã học:** con số trên log chưa chắc là thứ người dùng thấy. Trong challenge, server ghi 2.65 s/request nhưng client đo tới 10.6–13.3 s, vì endpoint `async def` gọi code đồng bộ (`time.sleep`) nên 5 request đồng thời phải xếp hàng. Tương tự, alert ban đầu (P95 > 3000 ms) không kích hoạt dù người dùng bị ảnh hưởng rõ rệt — tôi đã hạ ngưỡng xuống 2000 ms. Alert và SLO cần được kiểm chứng bằng sự cố thật, không chỉ đặt theo cảm tính.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) chưa sửa lỗi chặn event loop (đổi `/chat` sang `def` hoặc `run_in_threadpool`) vì ngoài phạm vi lab — chỉ ghi nhận làm preventive measure; (2) các request đầu tiên sau mỗi lần restart chậm 1–7 s (fetch prompt/khởi tạo client lúc cache rỗng) — chưa làm warm-up khi khởi động; (3) dashboard là trang HTML tĩnh sinh từ file log (refresh 30 s), chưa phải hệ thống alerting chạy thật, nên alert trong `config/alert_rules.yaml` mới dừng ở mức định nghĩa và runbook; (4) 20 trace đầu trong project được tạo trước CP2 nên chỉ có root observation, trace đạt yêu cầu là các trace từ 11:21 trở đi; (5) quality score là heuristic, không đo chất lượng thật.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
