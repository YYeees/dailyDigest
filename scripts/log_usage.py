"""
把`claude -p ... --output-format json`的输出记录成运行日志，给两个定时workflow
(digest.yml/trending.yml)共用。

用法:
    python scripts/log_usage.py <claude输出的json文件路径> --label digest

写两份:
- logs/<label>.jsonl —— 每次追加一整条原始usage/cost数据(含时间戳)，永久保留，
  "更详细"的日志查阅用，不做滚动清理。
- docs/data/run_log.json —— 只保留最近RUN_LOG_KEEP条的精简摘要，给网站页面展示用。
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

RUN_LOG_KEEP = 30


def build_entries(result, label, timestamp):
    """从claude --output-format json的结果构造(详细记录, 精简摘要)这对字典。"""
    usage = result.get("usage", {})

    detail_entry = {
        "timestamp": timestamp,
        "label": label,
        "total_cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
        "usage": usage,
        "model_usage": result.get("modelUsage", {}),
    }

    summary_entry = {
        "timestamp": timestamp,
        "label": label,
        "total_cost_usd": result.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "duration_ms": result.get("duration_ms"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
    }
    return detail_entry, summary_entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_file")
    parser.add_argument("--label", required=True, help="digest 或 trending")
    args = parser.parse_args()

    result = json.loads(Path(args.result_file).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    detail_entry, summary_entry = build_entries(result, args.label, now)

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    with open(logs_dir / f"{args.label}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(detail_entry, ensure_ascii=False) + "\n")

    run_log_path = Path("docs/data/run_log.json")
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(run_log_path.read_text(encoding="utf-8")) if run_log_path.exists() else {"runs": []}
    data["runs"].insert(0, summary_entry)
    data["runs"] = data["runs"][:RUN_LOG_KEEP]
    run_log_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    cost = summary_entry["total_cost_usd"]
    cost_str = f"${cost:.4f}" if cost is not None else "未知"
    print(
        f"[OK] 记录{args.label}这次运行: 费用{cost_str}, "
        f"tokens(input={summary_entry['input_tokens']}, output={summary_entry['output_tokens']}, "
        f"cache_write={summary_entry['cache_creation_input_tokens']}, "
        f"cache_read={summary_entry['cache_read_input_tokens']})"
    )


if __name__ == "__main__":
    main()
