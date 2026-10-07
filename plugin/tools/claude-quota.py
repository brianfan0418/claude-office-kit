"""提供 Claude 官方用量查詢入口；不把企業歷史用量當作即時剩餘額度。

用法：python tools/claude-quota.py [--json]
來源：https://code.claude.com/docs/en/costs 、https://platform.claude.com/docs/en/manage-claude/analytics-api
"""
import argparse
from office_common import emit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    info = {"ok": True, "available": False, "remaining": None,
            "note": "未查得供一般企業成員程式查詢即時剩餘額度的公開 API。建議在 Claude Code 執行 /usage，或查看 Claude 的 Usage 設定。",
            "analytics": "企業主擁有者可建立 read:analytics 金鑰查歷史用量與成本；不等於即時剩餘額度，本工具不索取管理員金鑰。",
            "sources": ["https://code.claude.com/docs/en/costs", "https://platform.claude.com/docs/en/manage-claude/analytics-api"]}
    if args.json:
        emit(info)
    else:
        print(info["note"] + "\n" + info["analytics"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
