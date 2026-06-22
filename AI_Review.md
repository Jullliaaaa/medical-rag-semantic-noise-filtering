# AIASE 2026 期末專案 — AI 評閱回饋

**GitHub ID:** `Jullliaaaa`

## 成績摘要

| 軌道 | 分數 |
|---|---|
| Basic Track(text2sql) | 30.0 / 30 |
| Pairwise Track(角色:Bug Hunter) | 8.33 / 10 |
| Open Track(設計 40% + 執行 60%) | 91.6 / 100 |
| 基礎加分(nano 第二參考) | 23.0 / 30 |
| Pairwise 加分(nano CA) | 2.5 / 10 |
| **Project 總分** | **89.67** |

- 額外榮譽 / 加分:Open 對抗穩健(輸入重排答案不變)
- 評分重試次數:Basic **0 次**(一次到位);Pairwise 採統一重試政策(no-result 重試 1 次、flaky 受害者重評取最佳),未逐人記錄次數。

## Open Track 計分明細(透明拆解)

Open 總分 = **設計審查 × 40% + 實跑驗證(60 分制)** = **91.6 / 100**

**① 設計審查(占 40 分)= 31.6 分**(LLM 閱讀你的 skill 評分:79.0/100)

- **可驗證性:9/10** — 以 F1（Precision/Recall 均衡）為客觀 metric，ground truth 存於評分環境（essential/noise 標籤不傳入 skill），evaluate.py 自動計算且有 contract 違規檢查，做到完全機器可驗證。唯一小扣分點是 ground truth JSON 檔本身未隨素材附上，無法交叉確認 essential/noise 標籤是否合理。
- **完整與清晰:8/10** — OPEN_TRACK.md 涵蓋簡介、Scenario 表（9 個、三種難度）、Metric 定義、Token Budget 估算、失敗模式分析；SKILL.md 有完整 Procedure 與 Pitfalls；scripts/run.py 與 evaluate.py 均齊全。缺少 ground truth 範例檔與完整 9 個 task JSON 輸入樣本（只給 s01 示例），讓可重現性略打折扣。
- **方法正確性:8/10** — evaluate.py 的 F1 計算公式正確（TP/kept 為 Precision、TP/essential 為 Recall）；run.py 原子寫入、overlap 檢查邏輯合理；SKILL.md Procedure 與 OPEN_TRACK.md 說明一致。run.py 中雖偵測 overlap 但只輸出 WARNING 而非直接 return error，若 kept 與 removed 真的重疊仍會寫出有問題的結果，是一處輕微邏輯缺陷。
- **失敗模式/穩健:7/10** — 設計上考量了文件順序打亂、等價詞替換、新誘餌等 perturbation，且 hard 難度刻意設計高關鍵字重疊 noise（s07 透析 vs 心衰竭飲食）以防關鍵字作弊。然而 run.py 的 overlap 警告不阻擋寫檔，且 confidence 值由 LLM 任意給定（無法被評分器利用或驗證），對健壯性有輕微影響。
- **工程嚴謹度:7/10** — 三層難度（cross_department / same_department_different_aspect / adjacent_department）設計有清晰的分類依據，並在 OPEN_TRACK.md 詳細說明為何難以 game。但未說明 9 個 ground truth 如何產生（人工標注？醫師審核？），essential 標籤的客觀性來源未交代，嚴謹度略有不足。
- **難度與原創:7/10** — 將 RAG noise filtering 包裝為可自動評分的 skill，並刻意設計三層 noise 難度（含 hard 的語意混淆類型）以挑戰純關鍵字方法，概念上有一定創意。但整體任務（文件相關性分類）屬較常見的 IR 評估框架，創新程度屬中等。

**② 實跑驗證(占 60 分)= 60 分**
- 可實際執行、輸出合法:✓ +20(滿 20)
- **確定性**(同輸入跑兩次結果一致):✓ +25(滿 25)
- 對自宣告 gold 正確:✓ +15(滿 15)

**執行診斷:** **【複核更正 2026-06-22】執行**:你的 skill 屬「LLM 產生 artifact(regex/程式/測試/查詢)→ 確定性腳本算分」設計;原評分比對的是 artifact 原始字串而非你宣告的 metric,故誤判確定性/對 gold 失敗。經實跑你的 evaluate 確認 metric 一致且達標,已將相應項目判為通過。

> 為何採「設計 + 實跑」雙軌:對齊公告「open in design, strict in verification」——設計分肯定你的構想,實跑分檢驗它**真的可重現、可驗證**(確定性 / 對得上自己的 gold)。

## 評語

你的期末專案整體表現相當亮眼！以下是具體回饋：

**優點**

- **Basic Track 滿分（30/30）**，30 題全數通過，text2sql 能力紮實。
- Open Track 設計思路清晰：以 F1 為客觀指標、ground truth 與輸入分離、三層 noise 難度（跨科別／同科不同面向／鄰近科別）有效防止關鍵字作弊，工程上也做到原子寫入與對抗穩健（輸入 key 重排答案不變，獲得額外加分）✓。
- Pairwise Bug Hunter 得分 8.33/10，clean 不誤報率達到完美 1.0，配對 CA 判定也全對，顯示你對「不誤殺正確答案」的把握度很高。

**改進建議**

1. **補交 ground truth JSON**：評分環境缺少 essential/noise 標籤檔，導致「對自宣告 gold」無法通過（✗）。下次請確認所有評分所需的設定檔都一起提交，否則再好的設計也無法完整驗證。
2. **說明 essential 標籤的標注依據**：目前文件未說明哪些文件被標為 essential 的判斷準則，建議在 OPEN_TRACK.md 中補充 annotation guideline，讓可重現性更完整。
3. **強化 overlap 邏輯**：`run.py` 目前 overlap 檢查只警告不阻擋，屬於小邏輯漏洞；建議改為硬性錯誤（raise exception），避免產生非預期的結果。

---
> 本評閱由 AIASE 2026 自動化評分系統產生,供學習回饋參考。
> 方法對齊課程公告精神「**open in design, strict in verification**」:
> Open Track 以 **LLM 設計審查(40%)+ 確定性實跑驗證(60%)** 評分;Basic 對齊權威 `run_dev.py`;Pairwise 以 sandbox 跑題與 bug 偵測 F1 計分。
> 各軌分數與權重以課程最終公告為準;加分項獨立計算。
