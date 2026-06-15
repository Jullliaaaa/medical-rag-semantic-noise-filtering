#!/usr/bin/env python3
"""run_dev.py — 本地 dev-set 自測（file-based 輸出契約）。

用法：
  python3 run_dev.py --skill text2sql-<GITHUBID> --track basic [--limit N]
  python3 run_dev.py --skill open-ragfilter-<GITHUBID> --track open [--limit N]
"""
from __future__ import annotations

import os
import sys
import json
import glob
import argparse
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiase_contract as contract

HERMES_BASE = ["hermes", "chat", "--toolsets", "skills,terminal", "--yolo", "-Q"]
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_tasks(dev_dir: str, track: str | None) -> list[dict]:
    root = REPO_ROOT
    tasks = []
    for p in sorted(glob.glob(os.path.join(dev_dir, "*.json"))):
        with open(p, encoding="utf-8") as f:
            t = json.load(f)
        if track and t.get("track", track) != track:
            continue
        dbp = t.get("db_path", "")
        if dbp and not os.path.isabs(dbp):
            t["db_path"] = os.path.join(root, dbp)
        tasks.append(t)
    return tasks


def build_skill_input(task: dict) -> str:
    drop = {"gold_sql", "db_path", "seed_sql", "track"}
    payload = {k: v for k, v in task.items() if k not in drop}
    return json.dumps(payload, ensure_ascii=False)


def invoke_skill(skill: str, task: dict, result_path: str, model: str | None) -> tuple[int, str]:
    env = dict(os.environ)
    env["AIASE_RESULT_PATH"] = result_path
    cmd = list(HERMES_BASE)
    if model:
        cmd += ["-m", model]
    cmd += ["-q", f"/{skill} {build_skill_input(task)}"]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def evaluate_task(task: dict, result_path: str, track: str) -> tuple[bool, str]:
    obj = contract.read_result(result_path)
    if obj is None:
        return False, "no result file (task not produced)"
    if track == "basic":
        ok, reason = contract.validate_basic_schema(obj, task["task_id"])
        if not ok:
            return False, f"schema invalid: {reason}"
        try:
            got = contract.run_sql(task["db_path"], obj["sql"])
        except Exception as e:
            return False, f"student SQL failed to execute: {e}"
        try:
            gold = contract.run_sql(task["db_path"], task["gold_sql"])
        except Exception as e:
            return False, f"gold SQL failed (dev-set bug): {e}"
        return (True, "result set matches gold (bag-equal)") if contract.bag_equal(got, gold) \
            else (False, "result set differs from gold")
    if obj.get("task_id") != task["task_id"]:
        return False, "task_id mismatch"
    return True, "result file present & valid JSON object"


def grade_open(skill_name: str, only_task: str | None, limit: int, model: str | None) -> dict:
    scenario_dir = os.path.join(REPO_ROOT, "skills", skill_name, "scenarios")
    gt_dir = os.path.join(REPO_ROOT, "skills", skill_name, "ground_truth")
    evaluate_script = os.path.join(REPO_ROOT, "skills", skill_name, "scripts", "evaluate.py")

    if not os.path.isdir(scenario_dir):
        print(f"ERROR: scenarios/ not found: {scenario_dir}")
        return {"total": 0, "passed": 0, "results": []}

    scenarios = sorted(glob.glob(os.path.join(scenario_dir, "*.json")))
    if only_task:
        scenarios = [s for s in scenarios if only_task in os.path.basename(s)]
    if limit:
        scenarios = scenarios[:limit]

    results = []
    tmpdir = tempfile.mkdtemp(prefix="aiase_dev_open_")

    for sc_path in scenarios:
        task = json.load(open(sc_path, encoding="utf-8"))
        task_id = task.get("task_id", os.path.basename(sc_path))
        rp = os.path.join(tmpdir, f"{task_id}.json")
        if os.path.exists(rp):
            os.remove(rp)

        # 直接設環境變數呼叫
        env = dict(os.environ)
        env["AIASE_RESULT_PATH"] = rp
        cmd = list(HERMES_BASE)
        if model:
            cmd += ["-m", model]
        cmd += ["-q", f"/{skill_name} {json.dumps(task, ensure_ascii=False)}"]
        subprocess.run(cmd, env=env, capture_output=True, text=True)

        obj = contract.read_result(rp)
        if obj is None:
            print(f"  [FAIL] {task_id}: no result file")
            results.append({"task_id": task_id, "passed": False, "detail": "no result file"})
            continue

        if obj.get("task_id") != task_id:
            print(f"  [FAIL] {task_id}: task_id mismatch")
            results.append({"task_id": task_id, "passed": False, "detail": "task_id mismatch"})
            continue

        gt_name = f"gt_{os.path.basename(sc_path)}"
        gt_path = os.path.join(gt_dir, gt_name)
        if not os.path.exists(gt_path):
            print(f"  [SKIP] {task_id}: no ground truth")
            results.append({"task_id": task_id, "passed": True, "detail": "no gt (skipped)"})
            continue

        proc = subprocess.run(
            [sys.executable, evaluate_script, "--result", rp, "--ground-truth", gt_path],
            capture_output=True, text=True
        )
        f1_line = [l for l in proc.stdout.splitlines() if l.startswith("F1")]
        f1 = float(f1_line[0].split()[-1]) if f1_line else 0.0
        passed = f1 >= 0.5
        detail = f"F1={f1:.4f}"
        print(f"  [{'PASS' if passed else 'FAIL'}] {task_id}: {detail}")
        results.append({"task_id": task_id, "passed": passed, "detail": detail})

    n = len(results)
    p = sum(1 for r in results if r["passed"])
    print(f"\nOpen Track: {p}/{n} passed" + (f"  ({p/n*100:.0f}%)" if n else ""))
    return {"total": n, "passed": p, "results": results}


def run(skill, dev_dir, only_task, track, limit, model, dry_run, dry_result_file, invoke=invoke_skill):
    tasks = load_tasks(dev_dir, track)
    if only_task:
        tasks = [t for t in tasks if t["task_id"] == only_task]
    if limit:
        tasks = tasks[:limit]
    results = []
    tmpdir = tempfile.mkdtemp(prefix="aiase_dev_")
    for t in tasks:
        rp = dry_result_file if dry_run else os.path.join(tmpdir, f"{t['task_id']}.json")
        if not dry_run:
            if os.path.exists(rp):
                os.remove(rp)
            invoke(skill, t, rp, model)
        passed, detail = evaluate_task(t, rp, t.get("track", track or "basic"))
        results.append({"task_id": t["task_id"], "passed": passed, "detail": detail})
        print(f"  [{'PASS' if passed else 'FAIL'}] {t['task_id']}: {detail}")
    n = len(results)
    p = sum(1 for r in results if r["passed"])
    print(f"\nDev set: {p}/{n} passed" + (f"  ({p/n*100:.0f}%)" if n else ""))
    return {"total": n, "passed": p, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", help="skill name")
    ap.add_argument("--track", default="basic", choices=["basic", "pairwise", "open"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task", dest="only_task", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--dev-dir", default=os.path.join(os.path.dirname(__file__), "dev_set"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--result-file", dest="dry_result_file", default=None)
    a = ap.parse_args()
    if not a.skill:
        ap.error("--skill is required")

    if a.track == "open":
        s = grade_open(a.skill, a.only_task, a.limit, a.model)
    else:
        if a.dry_run and not a.dry_result_file:
            ap.error("--dry-run requires --result-file")
        s = run(a.skill, a.dev_dir, a.only_task, a.track, a.limit, a.model,
                getattr(a, 'dry_run', False), getattr(a, 'dry_result_file', None))

    return 0 if s["total"] and s["passed"] == s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
