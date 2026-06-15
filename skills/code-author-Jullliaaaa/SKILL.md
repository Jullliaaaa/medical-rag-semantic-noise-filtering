---
name: code-author-Jullliaaaa
description: Pairwise Code Author. Given a task spec, produce Python code and write the result via scripts/run.py (file-based output contract).
version: 2.0.0
metadata:
  hermes:
    tags: [code, author, pairwise, aiase]
    category: aiase
    requires_toolsets: [terminal]
---

# code-author (file-based output contract)



## When to Use
當使用者輸入 `/code-author-<Jullliaaaa> {json}` 時觸發。輸入含
`task_id` / `task_description` / `constraints`（max_loc、imports、entry_function 等）/ `sample_inputs`。

## Procedure
1. 依 `task_description` 與 `constraints` 寫出 Python code（≤ 500 S-LOC、用對 entry_function 名稱、
   只用允許的 import）。建議先在 sample_inputs 上自測。
2. **使用 `terminal` 工具（不要用 process/background 工具）**，以**絕對路徑**執行：
   ```
   python3 <skill_dir>/scripts/run.py --task_id "<task_id>" \
     --code "<your python code>" --loc <int> \
     --self_test_passed <int> --self_test_failed <int> \
     --rationale "<short reason>" --confidence 0.9
   ```
3. 執行 `scripts/run.py` 把結果寫入結果檔（路徑取自 `AIASE_RESULT_PATH`，未設定則 `./aiase_result.json`）。
   **你不需要在對話訊息中再輸出或複述 JSON。**

## Pitfalls
- 不要在 code 裡用 `print()` 或外部 I/O；不要包 markdown fence。
- 處理 empty input 等 edge case；confidence 要與實際自測一致。

## Verification
結果檔存在、為合法 JSON object、含 `task_id` / `code` / `loc` / `self_test_results` / `rationale` / `confidence`。
