"""
跑批之后的自检——把"跑挂了"和"跑了但什么都没干成"都变成workflow的红叉。

存在的理由(2026-08-21)：08-18~08-20连着三次跑批，Actions全是绿的success，实际上
- 08-20那次claude卡在"锚点清单读不到，你想怎么办"的提问上就结束了。fetch已经把6条新内容
  写进了runner上的digest.db，但没走到commit，随容器一起销毁——用户三天后才发现。
- 08-18起TwitterAPI.io欠费，4个X源全部HTTP 402，前两次跑批的总结里都写了，但总结没人看。

`claude -p`只要正常退出就是exit 0(哪怕它一条都没排、只是在那问问题)，`is_error`也是false，
所以光靠claude自己的退出码永远发现不了这类空转。这份脚本查的是**结果状态**，不是退出码。

用法(在digest.yml里claude那步之后跑)：
    python3 scripts/health_check.py [--claude-result /tmp/claude_result.json]

任一检查不通过就exit 1 —— GitHub Actions变红，默认会给仓库owner发邮件，这就是告警。
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, DIGEST_START_DATE  # noqa: E402
from sources import X_SOURCES  # noqa: E402

# 本地跑时从.env读TWITTERAPI_IO_KEY(跟fetch_x.py一致)；CI里是env传进来的，load_dotenv无害
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# fetch_x.py每个源每次取一页(最多20条推文)，TwitterAPI.io按返回的推文条数计费，
# 15 credits/条(2026-08-21实测标定：karpathy一页20条，余额正好掉300)。
CREDITS_PER_TWEET = 15
TWEETS_PER_CALL = 20
MIN_RUNWAY_DAYS = 30  # 余额撑不到30天就报警，留足充值的时间
X_SILENCE_LIMIT_DAYS = 7  # 4个活跃账号一周一条都没有，基本可以确定是抓取坏了而不是真没发


def _fail(msg):
    print(f"[FAIL] {msg}")
    return False


def _ok(msg):
    print(f"[OK] {msg}")
    return True


def check_worktree_clean():
    """跑批改了库/导出文件却没提交 —— 这些改动会随runner容器一起丢，等于整次白跑。"""
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if dirty:
        return _fail(
            "跑批留下了未提交的改动，这些改动会随runner销毁而丢失(整次跑批白跑)：\n"
            + "\n".join(f"    {line}" for line in dirty.splitlines())
        )
    return _ok("工作区干净，跑批产出的改动都已提交")


def check_no_pending():
    """排完序之后不该再有可排序的待处理条目。有就说明排序那步没干完(卡住/崩了/漏了一批)。"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT source_name, title FROM items "
        "WHERE ranked_at IS NULL AND published >= ? ORDER BY published",
        (DIGEST_START_DATE,),
    ).fetchall()
    conn.close()
    if rows:
        listed = "\n".join(f"    {s} — {t[:60]}" for s, t in rows[:10])
        more = f"\n    ...另有{len(rows) - 10}条" if len(rows) > 10 else ""
        return _fail(f"还有{len(rows)}条抓到了但没排序，排序那步没干完：\n{listed}{more}")
    return _ok("没有积压的待排序条目")


def check_x_credits():
    """X抓取靠TwitterAPI.io的预付费额度，余额见底会让4个X源静默全挂(2026-08-18踩过)。"""
    api_key = os.environ.get("TWITTERAPI_IO_KEY")
    if not api_key:
        return _fail("没有TWITTERAPI_IO_KEY，X源这次根本没抓(CI里应该在repo secrets里配)")

    import requests

    try:
        resp = requests.get(
            "https://api.twitterapi.io/oapi/my/info",
            headers={"X-API-Key": api_key}, timeout=30,
        )
        credits = resp.json()["recharge_credits"]
    except Exception as exc:  # 查不到余额本身就是个需要人看一眼的信号
        return _fail(f"查TwitterAPI.io余额失败：{exc}")

    daily = len(X_SOURCES) * TWEETS_PER_CALL * CREDITS_PER_TWEET
    days = credits // daily if daily else 0
    if days < MIN_RUNWAY_DAYS:
        return _fail(
            f"TwitterAPI.io余额{credits} credits，按每天{daily}只够{days}天(低于{MIN_RUNWAY_DAYS}天)，去充值"
        )
    return _ok(f"TwitterAPI.io余额{credits} credits，按每天{daily}够用约{days}天")


def check_x_not_silent():
    """余额正常但X内容长期不进库 —— 说明挂在别的地方(接口变了/账号被封/参数失效)。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT max(first_seen_at) FROM items WHERE source_type = 'x'"
    ).fetchone()
    conn.close()
    latest = row[0] if row else None
    if not latest:
        return _fail("库里一条X内容都没有")

    seen = datetime.fromisoformat(latest)
    age = datetime.now(timezone.utc) - seen
    if age > timedelta(days=X_SILENCE_LIMIT_DAYS):
        return _fail(
            f"最近一条X内容是{age.days}天前入库的({latest[:16]})，"
            f"{len(X_SOURCES)}个账号连着{X_SILENCE_LIMIT_DAYS}天没有新内容，八成是抓取坏了"
        )
    return _ok(f"X最近入库 {latest[:16]}({age.days}天前)")


def check_claude_result(path):
    """claude -p的结果里如果自己报了错，也要让job红——虽然它退出码是0。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return _fail(f"读不到claude运行结果{path}：{exc}")
    if data.get("is_error"):
        return _fail(f"claude自报运行出错：{str(data.get('result'))[:300]}")
    return _ok("claude运行结果无自报错误")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-result", help="claude -p --output-format json的输出文件")
    args = parser.parse_args()

    checks = [check_worktree_clean, check_no_pending, check_x_credits, check_x_not_silent]
    results = [c() for c in checks]
    if args.claude_result:
        results.append(check_claude_result(args.claude_result))

    failed = results.count(False)
    if failed:
        print(f"\n{failed}/{len(results)} 项自检未通过 —— 这次跑批需要人工看一眼", file=sys.stderr)
        sys.exit(1)
    print(f"\n全部{len(results)}项自检通过")


if __name__ == "__main__":
    main()
