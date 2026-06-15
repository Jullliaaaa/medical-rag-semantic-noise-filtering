#!/usr/bin/env python3
"""
open-ragfilter / scripts/evaluate.py — 本地自測用評分器。

用法：
    python3 evaluate.py \
        --result aiase_result.json \
        --ground-truth ground_truth/gt_ragfilter_s01.json

輸出：
    Precision / Recall / F1 與詳細比對結果。
"""
import os
import sys
import json
import argparse


def compute_f1(result_path: str, gt_path: str) -> dict:
    # 讀結果檔
    if not os.path.exists(result_path):
        return {"error": f"result file not found: {result_path}"}
    try:
        result = json.load(open(result_path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"invalid result JSON: {e}"}

    # 讀 ground truth
    if not os.path.exists(gt_path):
        return {"error": f"ground truth file not found: {gt_path}"}
    try:
        gt = json.load(open(gt_path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"invalid ground truth JSON: {e}"}

    # 驗證 task_id
    if result.get("task_id") != gt.get("task_id"):
        return {"error": f"task_id mismatch: result={result.get('task_id')}, gt={gt.get('task_id')}"}

    kept = set(result.get("kept", []))
    essential = set(gt.get("essential", []))
    noise = set(gt.get("noise", []))
    all_ids = essential | noise

    # 驗證輸出契約
    result_all = kept | set(result.get("removed", []))
    if result_all != all_ids:
        missing = all_ids - result_all
        extra = result_all - all_ids
        return {"error": f"contract violation: missing={missing}, extra={extra}"}

    # 計算 Precision / Recall / F1
    tp = len(kept & essential)
    precision = tp / len(kept) if kept else 0.0
    recall = tp / len(essential) if essential else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "task_id": gt["task_id"],
        "kept": sorted(kept),
        "essential": sorted(essential),
        "tp": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confidence": result.get("confidence", 0.0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, help="path to aiase_result.json")
    ap.add_argument("--ground-truth", required=True, help="path to gt_ragfilter_s*.json")
    a = ap.parse_args()

    out = compute_f1(a.result, a.ground_truth)

    if "error" in out:
        print(f"ERROR: {out['error']}", file=sys.stderr)
        return 1

    print(f"task_id   : {out['task_id']}")
    print(f"kept      : {out['kept']}")
    print(f"essential : {out['essential']}")
    print(f"TP        : {out['tp']}")
    print(f"Precision : {out['precision']}")
    print(f"Recall    : {out['recall']}")
    print(f"F1        : {out['f1']}")
    print(f"confidence: {out['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
