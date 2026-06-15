---
name: text2sql-Jullliaaaa
description: Convert a natural-language question + SQLite schema into verified SQL, then write the result via scripts/run.py (file-based output contract).
version: 2.0.0
metadata:
  hermes:
    tags: [sql, text2sql, data, aiase]
    category: data
    requires_toolsets: [terminal]
---

# text2sql (file-based output contract)

## When to Use
當使用者輸入 `/text2sql-Jullliaaaa {json}` 時觸發。

## Procedure
1. 讀懂 `question`，先做語意分析：
   - 找出主體（要查什麼）、條件（過濾條件）、量詞（至少一個？每個？）
   - 「至少一個」→ EXISTS 或 IN
   - 「每個/all/every」→ NOT EXISTS（反向排除不符合的）
   - 「合併兩個集合」→ UNION
   - 多表有同名欄位 → 加表名前綴
2. 依照語意分析，由外而內逐層建構 SQL：
   - 先寫最外層 SELECT（主體）
   - 再寫 WHERE 條件（一個條件一個 subquery）
   - 最後確認所有欄位都加了正確的表名前綴
3. 使用 `terminal` 工具，以絕對路徑執行：
   python3 <skill_dir>/scripts/run.py --task_id "<task_id>" --sql "<your SQL>" --rationale "<short reason>" --confidence 0.8
4. scripts/run.py 會把結果寫入結果檔。不需要在對話訊息中再輸出 JSON。

## Pitfalls
- 多表 JOIN 欄位衝突：加表名前綴（如 doc.name），否則報 ambiguous column name。
- UNION：合併集合用 UNION（自動去重），不用 UNION ALL。
- 全稱量詞（every/all/每個都）：用 NOT EXISTS 排除「不符合條件的反例」。
- Many-to-many JOIN：語意是「列出...」時加 DISTINCT。
- 只能 SQLite，不能用 window function、CTE、recursive query。
- 單一 statement，不能用分號。
- 不能用 INSERT/UPDATE/DELETE/DDL。
- task_id 輸出必須跟輸入完全一樣。

## Verification
結果檔存在、為合法 JSON object、task_id 一致、sql 非空、confidence 在 0..1。
