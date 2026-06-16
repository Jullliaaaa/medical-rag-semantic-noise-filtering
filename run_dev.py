#!/usr/bin/env python3
"""run_dev.py — 本地 dev-set 自測（file-based 輸出契約與完整報表）。

結合 run_dev_v0.py 的報表功能與 run_dev.py 的檔案寫入契約 (AIASE_RESULT_PATH)。

用法範例：
  1. 測試 Basic Track:
     python run_dev.py --skill text2sql-<GITHUBID> --track basic --limit 3
  
  2. 測試 Pairwise Track (code-author 角色):
     python run_dev.py --skill code-author-<GITHUBID> --track pairwise --role code-author
     
  3. 測試 Pairwise Track (bug-hunter 角色):
     python run_dev.py --skill bug-hunter-<GITHUBID> --track pairwise --role bug-hunter

  4. 測試單一題目 (需指定精確的 task_id):
     python run_dev.py --skill text2sql-<GITHUBID> --track basic --task task_nl2sql_001
"""
from __future__ import annotations

import os
import sys
import json
import glob
import argparse
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiase_contract as contract

HERMES_BASE = ["hermes", "chat", "--toolsets", "skills,terminal", "--yolo", "-Q"]
REPO_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = REPO_ROOT / "dev_run_results"

@dataclass
class TaskResult:
    task_id: str
    passed: bool
    reason: str = ""
    sql_returned: str = ""
    elapsed_sec: float = 0.0
    extras: dict = field(default_factory=dict)

@dataclass
class TrackReport:
    track: str
    skill: str
    role: str = ""
    total: int = 0
    passed: int = 0
    results: list[TaskResult] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = (self.passed / self.total) if self.total else 0.0
        return d

def load_tasks(dev_dir: str, track: str | None) -> list[dict]:
    root = os.path.dirname(os.path.abspath(dev_dir))
    tasks = []
    for p in sorted(glob.glob(os.path.join(dev_dir, "**", "*.json"), recursive=True)):
        if p.endswith("_GROUND_TRUTH.json"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                t = json.load(f)
        except json.JSONDecodeError:
            continue
            
        file_track = t.get("track")
        if not file_track:
            file_track = "pairwise" if "pairwise" in p.replace('\\', '/') else "basic"
            
        if track and file_track != track:
            continue
        dbp = t.get("db_path", "")
        if dbp and not os.path.isabs(dbp):
            t["db_path"] = os.path.join(root, dbp)
        t["_source_path"] = p
        tasks.append(t)
    return tasks

def load_reference_ground_truth(task_id: str, dev_dir: str) -> Optional[dict]:
    base = os.path.join(dev_dir, "pairwise", "reference_tasks")
    gt = os.path.join(base, f"{task_id}_GROUND_TRUTH.json")
    if os.path.exists(gt):
        path = gt
    else:
        main = os.path.join(base, f"{task_id}.json")
        if not os.path.exists(main):
            return None
        path = main
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return None
    data.setdefault("bugs", data.get("bugs_in_buggy", []))
    return data

def build_skill_input(payload: dict) -> str:
    # 移除 track 等內部測試用的欄位再丟給 LLM
    drop = {"track", "_source_path"}
    clean_payload = {k: v for k, v in payload.items() if k not in drop}
    return json.dumps(clean_payload, ensure_ascii=False)

def invoke_skill(skill: str, payload: dict, result_path: str, model: str | None) -> tuple[int, str, float]:
    env = dict(os.environ)
    env["AIASE_RESULT_PATH"] = result_path
    cmd = list(HERMES_BASE)
    if model:
        cmd += ["-m", model]
    cmd += ["-q", f"/{skill} {build_skill_input(payload)}"]
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), time.time() - t0

def grade_basic(skill_name: str, dev_dir: str, only_task: str | None, limit: int, model: str | None) -> TrackReport:
    rep = TrackReport(track="basic", skill=skill_name)
    tasks = load_tasks(dev_dir, "basic")
    if only_task:
        tasks = [t for t in tasks if t.get("task_id") == only_task]
    if limit:
        tasks = tasks[:limit]
        
    rep.total = len(tasks)
    if not tasks:
        rep.note = "no basic tasks loaded"
        return rep

    tmpdir = tempfile.mkdtemp(prefix="aiase_dev_")
    for task in tasks:
        task_id = task.get("task_id", "<missing>")
        db_path = Path(task.get("db_path", ""))
        gold_sql = task.get("gold_sql", "")
        
        rp = os.path.join(tmpdir, f"{task_id}.json")
        if os.path.exists(rp):
            os.remove(rp)

        payload = {
            "task_id": task_id,
            "question": task.get("question", ""),
            "db_schema": task.get("db_schema", ""),
            "dialect": task.get("dialect", "sqlite"),
        }
        retcode, outerr, elapsed = invoke_skill(skill_name, payload, rp, model)
        
        obj = contract.read_result(rp)
        if obj is None:
            rep.results.append(TaskResult(task_id, False, reason="no result file / invalid json", elapsed_sec=elapsed))
            continue
            
        ok, reason = contract.validate_basic_schema(obj, task_id)
        if not ok:
            rep.results.append(TaskResult(task_id, False, reason=f"schema invalid: {reason}", elapsed_sec=elapsed))
            continue
            
        student_sql = obj.get("sql", "")
        try:
            got = contract.run_sql(str(db_path), student_sql)
        except Exception as e:
            rep.results.append(TaskResult(task_id, False, reason=f"student SQL execution failed: {e}", sql_returned=student_sql, elapsed_sec=elapsed))
            continue
            
        try:
            gold = contract.run_sql(str(db_path), gold_sql)
        except Exception as e:
            rep.results.append(TaskResult(task_id, False, reason=f"gold SQL execution failed: {e}", sql_returned=student_sql, elapsed_sec=elapsed))
            continue
            
        passed = contract.bag_equal(got, gold)
        reason_msg = "result set matches gold (bag-equal)" if passed else "result set differs from gold"
        rep.results.append(TaskResult(
            task_id, passed, reason=reason_msg, sql_returned=student_sql, elapsed_sec=elapsed,
            extras={"student_rowcount": len(got), "gold_rowcount": len(gold)}
        ))

    rep.passed = sum(1 for r in rep.results if r.passed)
    return rep

def _bug_set_from_obj(obj: dict) -> set[tuple[int, str]]:
    out = set()
    for b in obj.get("bugs", []) or []:
        try:
            ls = int(b.get("line_start"))
            t = str(b.get("type", "")).strip()
            out.add((ls, t))
        except (TypeError, ValueError):
            continue
    return out

def _run_code_test_cases(code: str, constraints: dict, test_cases: list[dict]) -> tuple[int, int]:
    entry = constraints.get("entry_function", "")
    if not entry or not code:
        return 0, len(test_cases)
    ns: dict = {}
    try:
        exec(compile(code, "<student_code>", "exec"), ns)
    except Exception:
        return 0, len(test_cases)
    fn = ns.get(entry)
    if not callable(fn):
        return 0, len(test_cases)
    passed = 0
    for tc in test_cases:
        args = tc.get("input", [])
        expected = tc.get("expected")
        try:
            got = fn(*args) if isinstance(args, list) else fn(args)
            if got == expected:
                passed += 1
        except Exception:
            pass
    return passed, len(test_cases) - passed

def grade_pairwise(skill_name: str, role: str, dev_dir: str, only_task: str | None, limit: int, model: str | None) -> TrackReport:
    rep = TrackReport(track="pairwise", skill=skill_name, role=role)
    tasks = load_tasks(dev_dir, "pairwise")
    if only_task:
        tasks = [t for t in tasks if t.get("task_id") == only_task]
    if limit:
        tasks = tasks[:limit]

    rep.total = len(tasks)
    if not tasks:
        rep.note = "no pairwise tasks loaded"
        return rep

    tmpdir = tempfile.mkdtemp(prefix="aiase_dev_pairwise_")
    
    if role == "code-author":
        for task in tasks:
            task_id = task["task_id"]
            rp = os.path.join(tmpdir, f"{task_id}.json")
            if os.path.exists(rp): os.remove(rp)
            
            payload = {
                "task_id": task_id,
                "task_description": task.get("task_description", ""),
                "constraints": task.get("constraints", {}),
            }
            retcode, outerr, elapsed = invoke_skill(skill_name, payload, rp, model)
            obj = contract.read_result(rp)
            
            if obj is None or obj.get("task_id") != task_id or "code" not in obj:
                rep.results.append(TaskResult(task_id, False, reason="contract violation or missing file", elapsed_sec=elapsed))
                continue
                
            code = obj.get("code", "")
            gt = load_reference_ground_truth(task_id, dev_dir) or {}
            test_cases = gt.get("test_cases", [])
            passed_cases, failed_cases = _run_code_test_cases(code, task.get("constraints", {}), test_cases)
            
            all_pass = (failed_cases == 0 and passed_cases == len(test_cases))
            rep.results.append(TaskResult(
                task_id, all_pass,
                reason=("" if all_pass else f"{failed_cases}/{len(test_cases)} hidden-style cases failed"),
                elapsed_sec=elapsed,
                extras={"passed_cases": passed_cases, "total_cases": len(test_cases)},
            ))

    elif role == "bug-hunter":
        for task in tasks:
            task_id = task["task_id"]
            gt = load_reference_ground_truth(task_id, dev_dir) or {}
            buggy_code = gt.get("buggy_code", "")
            clean_code = gt.get("clean_code", "")
            gt_bugs = _bug_set_from_obj({"bugs": gt.get("bugs", [])})
            
            if not buggy_code:
                rep.results.append(TaskResult(task_id, False, reason="no ground-truth buggy_code"))
                continue

            rp_b = os.path.join(tmpdir, f"{task_id}_buggy.json")
            if os.path.exists(rp_b): os.remove(rp_b)
            payload_b = {
                "task_id": task_id,
                "task_description": task.get("task_description", ""),
                "code": buggy_code,
            }
            retcode, outerr, elapsed_b = invoke_skill(skill_name, payload_b, rp_b, model)
            obj_b = contract.read_result(rp_b)
            if obj_b is None or obj_b.get("task_id") != task_id:
                rep.results.append(TaskResult(task_id, False, reason="contract violation on buggy code", elapsed_sec=elapsed_b))
                continue
                
            student_bugs = _bug_set_from_obj(obj_b)
            inter = len(student_bugs & gt_bugs)
            union = len(student_bugs | gt_bugs) or 1
            recall_like = inter / max(1, len(gt_bugs))
            
            clean_fp = 0
            elapsed_c = 0.0
            if clean_code:
                rp_c = os.path.join(tmpdir, f"{task_id}_clean.json")
                if os.path.exists(rp_c): os.remove(rp_c)
                payload_c = dict(payload_b)
                payload_c["code"] = clean_code
                retcode_c, outerr_c, elapsed_c = invoke_skill(skill_name, payload_c, rp_c, model)
                obj_c = contract.read_result(rp_c) or {}
                if obj_c.get("verdict") == "buggy" or len(obj_c.get("bugs", []) or []) > 0:
                    clean_fp = 1
                    
            passed = (recall_like >= 0.5 and clean_fp == 0)
            rep.results.append(TaskResult(
                task_id, passed,
                reason=("" if passed else f"recall={recall_like:.2f}, clean_fp={clean_fp}"),
                elapsed_sec=elapsed_b + elapsed_c,
                extras={
                    "jaccard": inter / union,
                    "recall_like": recall_like,
                    "clean_fp": clean_fp,
                },
            ))
            
    rep.passed = sum(1 for r in rep.results if r.passed)
    return rep

def grade_open(skill_name: str, only_task: str | None, limit: int, model: str | None) -> TrackReport:
    rep = TrackReport(track="open", skill=skill_name)
    scenario_dir = REPO_ROOT / "skills" / skill_name / "scenarios"
    gt_dir = REPO_ROOT / "skills" / skill_name / "ground_truth"
    evaluate_script = REPO_ROOT / "skills" / skill_name / "scripts" / "evaluate.py"

    if not scenario_dir.is_dir():
        rep.note = f"scenarios/ not found: {scenario_dir}"
        return rep

    scenarios = sorted(scenario_dir.glob("*.json"))
    if only_task:
        scenarios = [s for s in scenarios if only_task in s.name]
    if limit:
        scenarios = scenarios[:limit]

    rep.total = len(scenarios)
    if not scenarios:
        rep.note = "no scenario files found"
        return rep

    tmpdir = tempfile.mkdtemp(prefix="aiase_dev_open_")
    for sc_path in scenarios:
        task = json.loads(sc_path.read_text(encoding="utf-8"))
        task_id = task.get("task_id", sc_path.stem)
        rp = os.path.join(tmpdir, f"{task_id}.json")
        if os.path.exists(rp):
            os.remove(rp)

        env = dict(os.environ)
        env["AIASE_RESULT_PATH"] = rp
        cmd = list(HERMES_BASE)
        if model:
            cmd += ["-m", model]
        cmd += ["-q", f"/{skill_name} {json.dumps(task, ensure_ascii=False)}"]
        t0 = time.time()
        subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
        elapsed = time.time() - t0

        obj = contract.read_result(rp)
        if obj is None:
            rep.results.append(TaskResult(task_id, False, reason="no result file", elapsed_sec=elapsed))
            continue

        if obj.get("task_id") != task_id:
            rep.results.append(TaskResult(task_id, False, reason="task_id mismatch", elapsed_sec=elapsed))
            continue

        gt_path = gt_dir / f"gt_{sc_path.name}"
        if not gt_path.exists():
            rep.results.append(TaskResult(task_id, True, reason="no gt (skipped)", elapsed_sec=elapsed))
            continue

        proc = subprocess.run(
            [sys.executable, str(evaluate_script), "--result", rp, "--ground-truth", str(gt_path)],
            capture_output=True, text=True
        )
        f1_line = [l for l in proc.stdout.splitlines() if l.startswith("F1")]
        f1 = float(f1_line[0].split()[-1]) if f1_line else 0.0
        passed = f1 >= 0.5
        rep.results.append(TaskResult(task_id, passed, reason=f"F1={f1:.4f}", elapsed_sec=elapsed))

    rep.passed = sum(1 for r in rep.results if r.passed)
    return rep


def _write_report(report: TrackReport) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{report.role}" if report.role else ""
    out = RESULTS_DIR / f"{report.track}{suffix}_{report.skill}_{stamp}.json"
    out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return out

def _print_summary(report: TrackReport) -> None:
    print(f"\n=== {report.track.upper()} :: {report.skill} {('('+report.role+')') if report.role else ''} ===")
    if report.note:
        print(f"  note: {report.note}")
    print(f"  total: {report.total}  passed: {report.passed}  rate: "
          f"{(report.passed/report.total*100 if report.total else 0):.1f}%")
    if report.results:
        for r in report.results[:50]:
            mark = "[PASS]" if r.passed else "[FAIL]"
            print(f"   {mark} {r.task_id}  {r.reason}")
        if len(report.results) > 50:
            print(f"   ... ({len(report.results)-50} more)")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", help="skill name, e.g. text2sql-<GITHUBID>")
    ap.add_argument("--track", default="basic", choices=["basic", "pairwise", "open"], help="basic | pairwise | open")
    ap.add_argument("--role", default="", choices=["code-author", "bug-hunter", ""], help="required when track is pairwise")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N tasks")
    ap.add_argument("--task", dest="only_task", default=None)
    ap.add_argument("--model", default=None, help="override model")
    ap.add_argument("--dev-dir", default=os.path.join(os.path.dirname(__file__), "dev_set"))
    a = ap.parse_args()
    
    if not a.skill:
        ap.error("--skill is required")
        
    if a.track == "pairwise" and not a.role:
        ap.error("--role is required when --track pairwise")
        
    if a.track == "basic":
        rep = grade_basic(a.skill, a.dev_dir, a.only_task, a.limit, a.model)
    elif a.track == "open":
        rep = grade_open(a.skill, a.only_task, a.limit, a.model)
    else:
        rep = grade_pairwise(a.skill, a.role, a.dev_dir, a.only_task, a.limit, a.model)
        
    _print_summary(rep)
    out = _write_report(rep)
    print(f"\nreport written to: {out.relative_to(REPO_ROOT)}")
    return 0 if rep.total and rep.passed == rep.total else 1

if __name__ == "__main__":
    sys.exit(main())
