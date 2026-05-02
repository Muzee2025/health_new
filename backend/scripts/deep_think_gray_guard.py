import json
import sys
from pathlib import Path


def main() -> int:
    """
    输入示例:
      python scripts/deep_think_gray_guard.py metrics.json

    metrics.json:
      {
        "rollout_ratio": 0.1,
        "template_reply_rate_current": 0.0,
        "template_reply_rate_week_ago": 0.12
      }
    """
    if len(sys.argv) < 2:
        print("usage: python scripts/deep_think_gray_guard.py <metrics.json>")
        return 2

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rollout_ratio = float(data.get("rollout_ratio", 0.0))
    current = float(data.get("template_reply_rate_current", 1.0))
    week_ago = float(data.get("template_reply_rate_week_ago", 1.0))

    print(
        json.dumps(
            {
                "rollout_ratio": rollout_ratio,
                "template_reply_rate_current": current,
                "template_reply_rate_week_ago": week_ago,
                "guard_rule": "灰度10%时，template_reply_rate_current必须为0%",
            },
            ensure_ascii=False,
        )
    )

    if abs(rollout_ratio - 0.1) > 1e-6:
        print("WARN: rollout ratio is not 10%")

    if current > 0:
        print("ALERT: template reply rate is not zero, trigger rollback")
        return 1

    print("OK: template reply rate is zero, keep rollout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
