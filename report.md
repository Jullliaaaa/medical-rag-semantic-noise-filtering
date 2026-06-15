# 期末報告 — AIASE 2026 Final Project

> 學生：蕭妙宣 / GitHub: `Jullliaaaa`

---

## 1. 設計決策

### 1.1 Basic — Text2SQL Skill

**為何這樣設計 SKILL.md：**

Procedure 在讓 LLM 產生 SQL 之前，要求它先做語意分析——識別量詞（「每個/all/every」→ NOT EXISTS）、集合操作（UNION）、以及多表同名欄位（需加表名前綴）。這個「先分析再寫 SQL」的設計，是因為開發測試時發現 LLM 在沒有引導的情況下會直接套用最簡單的 WHERE 過濾，無法處理全稱量詞（task_nl2sql_020）和多表欄位衝突（task_nl2sql_019）。

**harness 設計：**

`scripts/validate_sql.py` 用 SQLite 的 `EXPLAIN` 在記憶體 DB 上驗證 SQL 語法，確保欄位和表名真的存在於 schema。若驗證失敗，SKILL.md 要求最多 retry 3 次並帶入錯誤訊息。這個確定性驗證層讓 LLM 能在送出結果前自我修正，不依賴評分器才發現語法錯誤。

**為何不加更複雜的 harness：**

規格書 §2.2 限制了 Difficulty Envelope（不考 CTE、window function、recursive），所以 validate_sql.py 只需要做基礎的語法和欄位驗證即可，不需要模擬完整的查詢優化器。

### 1.2 Pairwise — Code Author + Bug Hunter

**Code Author 設計：**

SKILL.md 的 Procedure 要求 LLM 依照 `constraints`（entry_function、max_loc、allowed imports）精確實作，並在 sample_inputs 上自測。設計重點在「不要過度複雜」——LLM 傾向生成帶有額外 helper function 的複雜程式，但超過 500 S-LOC 會被評分器拒絕。SKILL.md 明確要求「優先考慮正確性，再考慮簡潔性」。

**Bug Hunter 設計：**

兩步驟架構：先用 `scripts/analyze.py` 做確定性的靜態分析（AST 解析 + 邊界輸入探測），取得 suspicious_lines 和 crash 信號；再讓 LLM 做語意判斷，決定是否為真正的 bug。這樣設計是因為純靠 LLM 語意分析容易誤報（false positive），但 analyze.py 的 crash 信號能有效過濾掉明顯的邊界問題，讓 LLM 只需要對 suspicious 的地方做深度分析。

SKILL.md 特別強調「task_description 裡說要支援的功能，但 code 沒實作 → 這就是 bug（type: unhandled_input）」，這個指引是為了修復 task_pair_003（CSV quoted field 未實作）的失敗。

### 1.3 Open Track — open-ragfilter-Jullliaaaa

**題目動機：**

在開發衛教 RAG 系統時，實際觀察到 retriever 會把向量相似度 0.85 的文件撈回來，但該文件是「同主題不同面向」的 distracting passage（例如問糖尿病慢性合併症，撈到的文件是透析患者飲食限制），送給 LLM 後會導致回答偏離。這個 skill 的設計初衷是解決「retriever 撈得到但 LLM 會被帶偏」的痛點。

**為何設計三層難度 noise：**

- Easy（cross_department）：不同科別，LLM 應輕鬆辨識
- Medium（same_department_different_aspect）：同科別不同面向，關鍵字重疊但問題核心不同
- Hard（adjacent_department）：相鄰科別，食物禁忌清單幾乎相同但限制原因不同（如透析限磷 vs 膽囊炎限脂），必須真正理解語意才能過濾

**harness 設計（scripts/run.py + evaluate.py）：**

`run.py` 在寫結果前驗證 `kept ∪ removed == 所有輸入 id`（不多不少、不重疊），確保 LLM 不會漏掉文件或重複標記。`evaluate.py` 計算 Precision/Recall/F1，用 F1 ≥ 0.5 作為 PASS 門檻，避免 LLM 靠「全保留」或「全剔除」矇分。

---

## 2. 實際遭遇之失敗與分析

### 失敗 1 — task_nl2sql_019 ambiguous column name

- **觸發場景**：問題需要 UNION 兩個涉及多表 JOIN 的子查詢，Doctors 和 Departments 兩個表都有 `name` 欄位。
- **log 片段**：
  ```
  [FAIL] task_nl2sql_019: student SQL failed to execute: ambiguous column name: name
  ```
- **成因分析**：LLM 在 SELECT 和 JOIN 時未加表名前綴（如 `doc.name`），SQLite 無法判斷要用哪個表的 `name`。
- **修正方式**：在 SKILL.md Pitfalls 加入「多表 JOIN 欄位衝突」提示，要求在 SELECT 和 WHERE 中加表名前綴。修正後單題測試 PASS。
- **MAST 分類**：(3) 驗證與品質

### 失敗 2 — task_nl2sql_006/017 timeout（no result file）

- **觸發場景**：全套測試時，LiteLLM 伺服器負載高，部分題目回應時間超過 120 秒，導致沒有產出結果檔。
- **log 片段**：
  ```
  [FAIL] task_nl2sql_006: no result file (task not produced)
  [FAIL] task_nl2sql_017: no result file (task not produced)
  real    92m51.954s  (全套 21 題共耗時 92 分鐘)
  ```
- **成因分析**：全班同學趕 deadline 期間同時使用課程 LiteLLM Gateway，伺服器負載過高。單題重跑均可正常通過。
- **修正方式**：設定 `HERMES_TIMEOUT_SEC=110`，讓 Hermes 在接近上限前提早結束，避免卡死。
- **MAST 分類**：(2) agent 間協調

### 失敗 3 — task_nl2sql_020 全稱量詞邏輯錯誤

- **觸發場景**：問題含「every patient... is older than 60」，LLM 用 WHERE 過濾代替 NOT EXISTS，邏輯不等價。
- **log 片段**：
  ```
  [FAIL] task_nl2sql_020: result set differs from gold
  ```
- **成因分析**：全稱量詞（「每個都...」）在 SQL 中需要用「排除反例」的 NOT EXISTS 邏輯，但 LLM 傾向用更直觀的 WHERE 條件過濾，兩者在有 NULL 或邊界情況時結果不同。
- **修正方式**：在 SKILL.md Procedure 加入語意分析步驟，明確說明「全稱量詞 → NOT EXISTS（反向排除不符合條件的反例）」，並加入逐層建構 SQL 的指引。
- **MAST 分類**：(1) 規格與角色

### 失敗 4 — task_pair_003 bug-hunter recall=0.00

- **觸發場景**：parse_csv_line 的 buggy code 完全沒有實作 quoted field 處理，但 bug-hunter 回報的 line_start=4（for loop 那行），ground truth 要求 line_start=5（if 條件那行），行號差一導致 recall=0。
- **log 片段**：
  ```
  [FAIL] task_pair_003  recall=0.00, clean_fp=0
  extras: {'jaccard': 0.0, 'recall_like': 0.0, 'clean_fp': 0}
  elapsed_sec: 2840.7  (約 47 分鐘，伺服器 timeout)
  ```
- **成因分析**：LLM 把 bug 指向 for loop（第 4 行）而非 if 條件（第 5 行）。MAST 分類上屬於「規格與角色」——line_start 應指向最小的包含 bug 邏輯的行，不是外層 loop。加上伺服器 timeout 導致部分執行不完整。
- **修正方式**：在 SKILL.md 加入「Line Number Guidance」，明確說明應指向最小的 bug 邏輯行，不是外層 for/while loop。
- **MAST 分類**：(1) 規格與角色

---

## 3. 改進方向

**Basic：**
- 加入 validate_sql 的 retry 次數統計，分析哪類 SQL 最容易需要 retry，針對性加強 SKILL.md 的對應 Pitfall。
- 對「全稱量詞」類題目可以在 Procedure 加入一個明確的「是否有 every/all/每個？→ 用 NOT EXISTS」的決策樹。

**Pairwise Bug Hunter：**
- `analyze.py` 的 default battery 沒有針對「字串解析」類函式的測試（如含逗號的 quoted CSV），可以根據 entry_function 的命名和 task_description 關鍵字，動態選擇更有針對性的 edge_inputs。
- Line number 的判斷可以在 SKILL.md 加入「指向最小語義單元」的範例，減少 LLM 指向外層 loop 的機率。

**Open Track：**
- 目前 s05、s09 在全套測試時因伺服器 timeout 而 FAIL，但單題測試均 PASS。可以加入 retry 機制（最多 1 次），在結果檔不存在時重試一次。
- 未來可以加入 `retrieval_score` 欄位（模擬 RAG retriever 的向量相似度分數），讓 skill 在過濾時也能展示「高分但無關」的辨識能力，更貼近真實 RAG 場景。

---

## 4. 分工

（單人作業，無需填寫）

---

## 5. 引用說明

- **來源**：AIASE 2026 課程 starter repo（`https://github.com/Netdb-NCKU/aiase2026-final-project-Final-Project`），**使用範圍**：hello-aiase、text2sql、code-author、bug-hunter 的 SKILL.md 骨架與 scripts/run.py 範本（file-based 輸出契約），**差異**：SKILL.md 的 Procedure 與 Pitfalls 依測試失敗結果大幅修改；scripts/run.py 照新版 file-based 契約使用，未更動邏輯。

- **來源**：AI 工具（Claude，Anthropic），**使用範圍**：SKILL.md 的 Pitfalls 設計引導、OPEN_TRACK.md 七區塊草稿、report.md 草稿、run_dev.py 的 Open Track 支援（grade_open 函式）、scenarios/ground_truth JSON 的拆分腳本，**差異**：所有 AI 產出均經本人理解、測試驗證與修改；Open Track 的題目選定、衛教資料標注、三層難度 noise 設計、9 個 scenario 的具體內容為本人獨立完成；SKILL.md 的最終版本為本人根據測試失敗結果迭代修改後的版本。

- **來源**：Open Track scenario 衛教文件，詳見 `skills/open-ragfilter-Jullliaaaa/SOURCES.md`，**使用範圍**：衛教段落文字用於 scenario 的 documents 欄位，**差異**：原始文件為醫院衛教單張，自各醫院公開衛教單張中擷取段落，作為 RAG noise filter scenario 的 documents 欄位測試文件，僅用於非商業學術作業。部分段落經輕度整理（移除排版符號、合併條列），未更動原文醫學內容與建議。
