---
name: bug-hunter-Jullliaaaa
description: Pairwise Bug Hunter. Given code + task, produce a structured bug report and write the result via scripts/run.py (file-based output contract).
version: 2.0.0
metadata:
  hermes:
    tags: [bug, review, pairwise, aiase]
    category: aiase
    requires_toolsets: [terminal]
---

# Bug Hunter Skill (Pairwise Track)

## When to Use
Triggered when the user inputs `/bug-hunter-Jullliaaaa {json}`.
Input contains: `task_id` / `task_description` / `code` / `constraints` / `sample_inputs`.

## Procedure
1. **Read task_description carefully** and list ALL requirements (e.g., "must handle empty input", "must support quoted fields", "must run in O(log n)").

2. Run static analysis and edge-case probing using terminal tool with absolute path:
   python3 <skill_dir>/scripts/analyze.py '{"code": "<code>", "entry_function": "<entry_function>", "edge_inputs": []}'
   Read the returned `suspicious_lines` and `probes` as evidence.

3. **Compare task requirements with code implementation** line by line:
   - For each requirement in task_description, find the corresponding code that handles it
   - If a requirement is NOT implemented in the code → that's a bug (likely unhandled_input or edge_case)
   - Example: task says "support quoted fields with commas" but code uses simple `split(',')` → bug
   - Example: task says "empty input returns []" but code does `intervals[0]` → bug

4. Check common bug patterns:
   - **off_by_one**: loop condition `<` vs `<=`? binary search `lo < hi` vs `lo <= hi`? Try single-element edge case.
   - **edge_case**: empty input? single element? None? boundary values?
   - **unhandled_input**: special characters (quotes, commas, escapes)? missing format handling?
   - **logic_error**: condition direction correct? wrong return value?
   - **null_deref**: accessing attribute/index without None check?

5. Build the bug list. Each bug must have:
   - `line_start` / `line_end`: 1-indexed
   - `severity`: critical / high / medium / low
   - `type`: off_by_one / null_deref / type_error / logic_error / edge_case / api_misuse / inefficient / unhandled_input
   - `description`: specific explanation
   - `suggested_fix`: concrete fix

6. Use terminal tool to write result:
   python3 <skill_dir>/scripts/run.py --task_id "<task_id>" \
     --verdict "buggy" --confidence 0.75 \
     --bugs '[{"line_start":3,"line_end":3,"severity":"high","type":"off_by_one","description":"...","suggested_fix":"..."}]'
   If no bugs found, use --verdict "clean" --bugs '[]'.

7. scripts/run.py writes the result file. Do NOT output JSON in the conversation.

## Pitfalls
- `line_start` is 1-indexed.
- When verdict=clean, bugs MUST be empty array [].
- Do not hardcode verdict=buggy — clean code false positives are heavily penalized.
- `suggested_fix` must be specific.
- **A missing feature from task_description IS a bug** (type: unhandled_input or edge_case).

## Verification
Result file exists, is valid JSON object, contains `task_id` / `verdict` / `bugs` (array) / `confidence`.

## Critical Check: Missing Feature = Bug
Before running analyze.py, always read task_description and list every feature requirement.
Then check if the code implements each one.

Example:
- task says "support double-quoted fields with commas inside"
- code has NO quote handling at all
→ This is a bug (type: unhandled_input, severity: high)
  Even if analyze.py shows no crash on default probes,
  a missing required feature IS a bug.

## Line Number Guidance
- Point to the SMALLEST line range that contains the actual bug logic.
- For missing feature bugs: point to the specific condition/branch that SHOULD handle it, not the outer loop.
- Example: if comma-split bug is in `if c == ','` at line 5, report line_start=5, NOT the `for` loop at line 4.
