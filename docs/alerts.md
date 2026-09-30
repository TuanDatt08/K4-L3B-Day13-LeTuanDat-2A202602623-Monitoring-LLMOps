# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` trong `config/slo.yaml` (99.5% request có `response_sent.latency_ms <= 3000`)
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 2000ms` liên tục 5 phút — cảnh báo sớm trước khi vi phạm SLO 3000 ms. Ban đầu đặt 3000 ms nhưng challenge `rag_slow` (P95 ~2650 ms, vượt ngưỡng 2000 ms của challenge) không kích hoạt alert, nên đã hạ xuống 2000 ms.
- Ảnh hưởng tới người dùng: người dùng chờ > 3 giây mới nhận câu trả lời; error budget bị đốt nhanh
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency: xác nhận P95/P99 tăng và khoảng thời gian; so TTFT P95 — nếu TTFT bình thường thì chậm nằm trước bước LLM (retrieval/prompt fetch).
  2. Lọc log: `Get-Content data/logs.jsonl | Select-String '"response_sent"' | Select-String '"latency_ms": [3-9][0-9]{3}'`, lấy `correlation_id` của một request chậm.
  3. Trên Langfuse, lọc trace theo metadata `correlation_id`, mở waterfall và so thời lượng span `retrieval` với `llm-generation`.
- Mitigation tạm thời: nếu span `retrieval` chậm → tắt incident/khôi phục vector store (`python scripts/inject_incident.py --scenario rag_slow --disable`), giảm tải; nếu `llm-generation` chậm sau khi đổi prompt → rollback label `production` về version trước.
- Owner: `student-2A202602623`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailure`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `error_rate_pct_max: 2` và `retrieval_success_rate_pct_min: 90` trong `config/slo.yaml`; mọi request lỗi đều là bad event của SLO chính
- Điều kiện và thời gian duy trì: error rate > 2% **hoặc** retrieval success < 90% liên tục 5 phút
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500, không có câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors: xem error rate, breakdown `error_type` và retrieval success từ lúc nào.
  2. Lọc log: `Get-Content data/logs.jsonl | Select-String '"request_failed"'`, đọc `error_type`, `tool_name`, `payload.detail` và lấy `correlation_id`.
  3. Mở trace cùng `correlation_id`, xem span nào có level ERROR (ví dụ `retrieval` báo `Vector store timeout`).
- Mitigation tạm thời: nếu lỗi ở `retrieval` → khôi phục/restart vector store (`python scripts/inject_incident.py --scenario tool_fail --disable`), bật fallback trả lời không cần context; nếu lỗi sau deploy/đổi prompt → rollback.
- Owner: `student-2A202602623`

## Alert 3

- Tên: `CostOrTokenSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` trong `config/slo.yaml`; panel Cost và Tokens
- Điều kiện và thời gian duy trì: cost mỗi phút > 2 lần baseline **hoặc** trung bình `tokens_out` > 400 (baseline 80–180) liên tục 10 phút
- Ảnh hưởng tới người dùng: câu trả lời dài bất thường, chậm hơn; ngân sách cạn sớm dẫn tới phải giới hạn dịch vụ
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Cost và Tokens: xác nhận độ dốc cumulative tăng và `tokens_out` hay `tokens_in` tăng.
  2. Lọc log `response_sent` có `tokens_out` cao, lấy `correlation_id`, kiểm tra `feature` và `model` bị ảnh hưởng.
  3. Mở trace, xem generation `llm-generation`: usage/cost và prompt name/version đang dùng.
- Mitigation tạm thời: nếu tăng sau khi đổi prompt → rollback label `production`; đặt `max_tokens`; nếu do model/config → khôi phục cấu hình (`python scripts/inject_incident.py --scenario cost_spike --disable`).
- Owner: `student-2A202602623`
