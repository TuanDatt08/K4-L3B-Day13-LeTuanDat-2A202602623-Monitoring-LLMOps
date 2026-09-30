"""Dựng dashboard 6 panel từ data/logs.jsonl theo contract config/dashboard.yaml.

Chạy:  python scripts/build_dashboard.py            -> ghi data/dashboard.html
       python scripts/build_dashboard.py --watch    -> build lại mỗi refresh_seconds
Mở data/dashboard.html bằng trình duyệt (trang tự reload theo refresh_seconds).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
OUT_PATH = REPO_ROOT / "data" / "dashboard.html"
CONFIG = yaml.safe_load((REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]


def load_records() -> list[dict]:
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            rec["_ts"] = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            records.append(rec)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return records


def build() -> str:
    records = load_records()
    if not records:
        raise SystemExit(f"{LOG_PATH} không có log hợp lệ")
    # Cửa sổ 60 phút kết thúc ở log mới nhất để ảnh chụp luôn có dữ liệu.
    end = max(r["_ts"] for r in records).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=CONFIG["time_range_minutes"])
    records = [r for r in records if start <= r["_ts"] < end]
    minutes = [start + timedelta(minutes=i) for i in range(CONFIG["time_range_minutes"])]
    buckets: dict[datetime, list[dict]] = {m: [] for m in minutes}
    for r in records:
        buckets[r["_ts"].replace(second=0, microsecond=0)].append(r)

    def per_minute(fn):
        return [fn(buckets[m]) for m in minutes]

    def ok(rs):
        return [r for r in rs if r["event"] == "response_sent"]

    def pct(rs, field, p):
        vals = [r[field] for r in ok(rs)]
        return percentile(vals, p) if vals else None

    def error_rate(rs):
        total = sum(r["event"] == "request_received" for r in rs)
        return round(100 * sum(r["event"] == "request_failed" for r in rs) / total, 2) if total else None

    def retrieval_success(rs):
        vals = [r["tool_success"] for r in rs if r.get("tool_success") is not None]
        return round(100 * sum(vals) / len(vals), 2) if vals else None

    def cumulative(values):
        out, acc = [], 0.0
        for v in values:
            acc += v
            out.append(round(acc, 6))
        return out

    all_ok = ok(records)
    th = {p["id"]: p["threshold"]["value"] for p in CONFIG["panels"]}
    title = {p["id"]: p["title"] for p in CONFIG["panels"]}
    unit = {p["id"]: p["unit"] for p in CONFIG["panels"]}
    errors_by_type: dict[str, int] = {}
    for r in records:
        if r["event"] == "request_failed":
            errors_by_type[r.get("error_type", "unknown")] = errors_by_type.get(r.get("error_type", "unknown"), 0) + 1

    summary = {
        "latency": f"P50 {percentile([r['latency_ms'] for r in all_ok], 50):.0f} · P95 {percentile([r['latency_ms'] for r in all_ok], 95):.0f} · "
        f"P99 {percentile([r['latency_ms'] for r in all_ok], 99):.0f} · TTFT P95 {percentile([r['ttft_ms'] for r in all_ok], 95):.0f} ms",
        "traffic": f"{sum(r['event'] == 'request_received' for r in records)} requests",
        "errors": f"error rate {error_rate(records) or 0}% · retrieval success {retrieval_success(records) or 0}% · breakdown {errors_by_type or '{}'}",
        "cost": f"total ${sum(r['cost_usd'] for r in all_ok):.4f}",
        "tokens": f"in {sum(r['tokens_in'] for r in all_ok)} · out {sum(r['tokens_out'] for r in all_ok)}",
        "quality": f"mean {sum(r['quality_score'] for r in all_ok) / len(all_ok):.3f}" if all_ok else "mean n/a",
    }
    n = len(minutes)
    panels = {
        "latency": [
            ("P50", per_minute(lambda rs: pct(rs, "latency_ms", 50))),
            ("P95", per_minute(lambda rs: pct(rs, "latency_ms", 95))),
            ("P99", per_minute(lambda rs: pct(rs, "latency_ms", 99))),
            ("TTFT P95", per_minute(lambda rs: pct(rs, "ttft_ms", 95))),
            ("SLO P95 ≤ 3000", [th["latency"]] * n),
        ],
        "traffic": [
            ("requests/min", per_minute(lambda rs: sum(r["event"] == "request_received" for r in rs))),
            ("min ≥ 1", [th["traffic"]] * n),
        ],
        "errors": [
            ("error rate %", per_minute(error_rate)),
            ("retrieval success %", per_minute(retrieval_success)),
            ("error ≤ 2%", [th["errors"]] * n),
        ],
        "cost": [
            ("cumulative USD", cumulative(per_minute(lambda rs: sum(r["cost_usd"] for r in ok(rs))))),
            ("budget ≤ $2.5", [th["cost"]] * n),
        ],
        "tokens": [
            ("tokens_in (cumulative)", cumulative(per_minute(lambda rs: sum(r["tokens_in"] for r in ok(rs))))),
            ("tokens_out (cumulative)", cumulative(per_minute(lambda rs: sum(r["tokens_out"] for r in ok(rs))))),
            ("limit ≤ 50000", [th["tokens"]] * n),
        ],
        "quality": [
            ("mean quality", per_minute(lambda rs: round(sum(r["quality_score"] for r in ok(rs)) / len(ok(rs)), 3) if ok(rs) else None)),
            ("SLO ≥ 0.75", [th["quality"]] * n),
        ],
    }
    data = {
        "labels": [m.strftime("%H:%M") for m in minutes],
        "panels": [
            {"id": pid, "title": title[pid], "unit": unit[pid], "summary": summary[pid], "series": series}
            for pid, series in panels.items()
        ],
    }
    time_range = f"{start:%Y-%m-%d %H:%M} → {end:%H:%M} UTC ({CONFIG['time_range_minutes']} phút)"
    return TEMPLATE.replace("__TITLE__", CONFIG["title"]).replace("__RANGE__", time_range).replace(
        "__REFRESH__", str(CONFIG["refresh_seconds"])
    ).replace("__DATA__", json.dumps(data))


TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="__REFRESH__"><title>__TITLE__</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>body{font-family:system-ui,sans-serif;margin:16px;background:#f6f7f9;color:#1b1f24}
h1{font-size:20px;margin:0}.meta{color:#555;margin:4px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}
.card{background:#fff;border:1px solid #dde1e6;border-radius:8px;padding:12px}
.card h2{font-size:15px;margin:0}.sum{font-size:13px;color:#333;margin:4px 0 8px}</style></head><body>
<h1>__TITLE__</h1><div class="meta">Time range: __RANGE__ · refresh __REFRESH__s · source data/logs.jsonl</div>
<div class="grid" id="grid"></div><script>
const D=__DATA__, colors=["#2563eb","#f59e0b","#dc2626","#16a34a","#6b7280"];
for(const p of D.panels){
  const c=document.createElement("div");c.className="card";
  c.innerHTML=`<h2>${p.title} <small>(${p.unit})</small></h2><div class="sum">${p.summary}</div><canvas></canvas>`;
  document.getElementById("grid").appendChild(c);
  new Chart(c.querySelector("canvas"),{type:"line",data:{labels:D.labels,datasets:p.series.map(([label,data],i)=>{
    const isTh=i===p.series.length-1;
    return {label,data,borderColor:isTh?"#6b7280":colors[i],borderDash:isTh?[6,4]:[],pointRadius:isTh?0:2,spanGaps:true,borderWidth:isTh?1.5:2};
  })},options:{animation:false,scales:{y:{beginAtZero:true,title:{display:true,text:p.unit}}}}});
}
</script></body></html>"""


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Build lại mỗi refresh_seconds")
    args = parser.parse_args()
    while True:
        OUT_PATH.write_text(build(), encoding="utf-8")
        print(f"Đã ghi {OUT_PATH} lúc {datetime.now():%H:%M:%S}")
        if not args.watch:
            break
        time.sleep(CONFIG["refresh_seconds"])


if __name__ == "__main__":
    main()
