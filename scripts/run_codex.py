"""Run subscription-authenticated Codex and emit the existing run-log format.

Authentication stays in a temporary directory outside the checkout and is never
included in logs or artifacts. A completed turn and exit status 0 are both required.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def summarize(events, returncode, duration_ms):
    completed = [e for e in events if e.get("type") == "turn.completed"]
    errors = [e for e in events if e.get("type") in {"error", "turn.failed"}]
    usage = {"input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}
    for event in completed:
        tokens = event.get("usage", {})
        usage["input_tokens"] += tokens.get("input_tokens", 0)
        usage["cache_read_input_tokens"] += tokens.get("cached_input_tokens", 0)
        usage["output_tokens"] += tokens.get("output_tokens", 0)
    failed = returncode != 0 or not completed or bool(errors)
    error_text = json.dumps(errors).lower()
    reason = "Codex failed; see the Actions runner stderr/authentication status"
    if any(word in error_text for word in ("401", "403", "unauthorized", "authentication", "refresh token")):
        reason = "Codex authentication failed; sign in again and update GitHub Secret CODEX_AUTH_JSON"
    elif any(word in error_text for word in ("429", "usage limit", "quota", "rate limit")):
        reason = "Codex subscription usage/rate limit reached; check the account and retry later"
    return {
        "provider": "codex-chatgpt",
        "is_error": failed,
        # Do not publish raw model/tool output; it can contain fetched content.
        "result": reason if failed else "Codex completed",
        "duration_ms": duration_ms,
        "num_turns": len(completed),
        "total_cost_usd": None,  # Subscription usage is not a per-call API bill.
        "usage": usage,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=["digest", "trending"])
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    result = summarize([], 1, 0)
    try:
        auth = json.loads(os.environ.get("CODEX_AUTH_JSON", "{}"))
        tokens = auth.get("tokens") or {}
        if auth.get("OPENAI_API_KEY") or not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise ValueError("Set GitHub Secret CODEX_AUTH_JSON from your own ChatGPT-authenticated Codex auth.json")
        skill = "run-digest" if args.workflow == "digest" else "rank-github-trending"
        prompt = (
            f"Read .agents/skills/{skill}/SKILL.md and execute its complete pipeline. "
            "You are Codex CLI, using ChatGPT subscription authentication. "
            "Use the repository ranking criteria and reason about content yourself. "
            "Fetch pages with requests/curl when needed; do not invoke Claude or a separate LLM API. "
            "This is an authorized unattended GitHub Actions run: finish exports, commit and push "
            "only digest.db and docs/data changes. Do not modify code, workflows or credentials. "
            "Do not print secrets or read any auth.json. Report failures clearly. "
            "If nothing changed, skip the empty commit. Do not read machine-specific Mac paths."
        )
        with tempfile.TemporaryDirectory(prefix="digest-codex-") as home:
            auth_path = Path(home) / "auth.json"
            auth_path.touch(mode=0o600)
            auth_path.write_text(json.dumps(auth))
            env = os.environ.copy()
            env.pop("CODEX_AUTH_JSON", None)
            env.pop("OPENAI_API_KEY", None)
            env.pop("CODEX_API_KEY", None)
            env["CODEX_HOME"] = home
            # CLI may refresh local OAuth tokens; GitHub Secrets are not updated.
            proc = subprocess.run(
                ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox",
                 "-c", 'cli_auth_credentials_store="file"', prompt],
                env=env, stdout=subprocess.PIPE, text=True, check=False,
            )
            events = []
            for line in proc.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            result = summarize(events, proc.returncode, int((time.monotonic() - started) * 1000))
    except (ValueError, OSError) as exc:
        # Configuration errors do not include the credential contents.
        print(f"Codex setup failed ({type(exc).__name__}). Check CODEX_AUTH_JSON and CLI installation.", flush=True)
    finally:
        args.result.write_text(json.dumps(result), encoding="utf-8")
    if result["is_error"]:
        print(result["result"], flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
