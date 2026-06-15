#!/usr/bin/env python3
"""bug-hunter / scripts/run.py — file-based 輸出契約入口（原子寫入結果檔）。

⚠️ 自帶 resolve_result_path，不 import aiase_contract（安裝後找不到 repo 根模組）。
--bugs 傳入一段 JSON 陣列字串。
"""
import os, sys, json, argparse


def resolve_result_path() -> str:
    return os.environ.get("AIASE_RESULT_PATH") or os.path.join(os.getcwd(), "aiase_result.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--verdict", required=True, choices=["buggy", "clean"])
    ap.add_argument("--bugs", default="[]", help="JSON array string of bug objects")
    ap.add_argument("--confidence", type=float, default=0.5)
    a = ap.parse_args()
    try:
        bugs = json.loads(a.bugs)
        if not isinstance(bugs, list):
            raise ValueError("bugs must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: --bugs is not a valid JSON array: {e}", file=sys.stderr)
        return 2
    result = {"task_id": a.task_id, "verdict": a.verdict, "bugs": bugs, "confidence": a.confidence}
    path = resolve_result_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)  # 原子寫入
    print(f"written ok -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
