#!/usr/bin/env python3
"""open-ragfilter / scripts/run.py — file-based 輸出契約入口（原子寫入結果檔）。

驗證 kept ∪ removed 是否涵蓋所有輸入 id（不多不少），然後原子寫入結果檔。

⚠️ 自帶 resolve_result_path，不 import aiase_contract（安裝後找不到 repo 根模組）。
"""
import os
import sys
import json
import argparse


def resolve_result_path() -> str:
    """結果檔路徑：優先環境變數 AIASE_RESULT_PATH，否則工作目錄下的 aiase_result.json。"""
    return os.environ.get("AIASE_RESULT_PATH") or os.path.join(os.getcwd(), "aiase_result.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--kept", required=True, help="JSON array of document ids to keep")
    ap.add_argument("--removed", required=True, help="JSON array of document ids to remove")
    ap.add_argument("--confidence", type=float, default=0.5)
    a = ap.parse_args()

    # 解析 kept / removed
    try:
        kept = json.loads(a.kept)
        removed = json.loads(a.removed)
        if not isinstance(kept, list) or not isinstance(removed, list):
            raise ValueError("kept and removed must be JSON arrays")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: invalid --kept or --removed: {e}", file=sys.stderr)
        return 2

    # 確保都是字串
    kept = [str(x) for x in kept]
    removed = [str(x) for x in removed]

    # 檢查重疊（同一個 id 不能同時在兩邊）
    overlap = set(kept) & set(removed)
    if overlap:
        print(f"WARNING: documents in both kept and removed: {overlap}", file=sys.stderr)

    # confidence 限制在 0..1
    confidence = max(0.0, min(1.0, float(a.confidence)))

    result = {
        "task_id": a.task_id,
        "kept": kept,
        "removed": removed,
        "confidence": confidence,
    }

    path = resolve_result_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)  # 原子寫入，避免讀到寫一半的檔
    print(f"written ok -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
