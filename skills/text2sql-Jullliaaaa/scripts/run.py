#!/usr/bin/env python3
"""text2sql / scripts/run.py — file-based 輸出契約入口（原子寫入結果檔）。

⚠️ 自帶 resolve_result_path，不 import aiase_contract（安裝後找不到 repo 根模組）。
"""
import os, json, argparse


def resolve_result_path() -> str:
    return os.environ.get("AIASE_RESULT_PATH") or os.path.join(os.getcwd(), "aiase_result.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--sql", required=True)
    ap.add_argument("--rationale", default="")
    ap.add_argument("--confidence", type=float, default=0.5)
    a = ap.parse_args()
    result = {"task_id": a.task_id, "sql": a.sql, "rationale": a.rationale, "confidence": a.confidence}
    path = resolve_result_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)  # 原子寫入，避免讀到寫一半的檔
    print(f"written ok -> {path}")


if __name__ == "__main__":
    main()
