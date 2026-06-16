## 1. Skill 簡介

針對 RAG（Retrieval-Augmented Generation）系統檢索回來的衛教文件，自動識別並過濾「同主題但答非所問」的 noise 文件，只保留真正能回答使用者問題的文件，降低下游 LLM 因雜訊上下文而產生幻覺的風險。

## 2. Skill 名稱與目錄

`skills/open-ragfilter-Jullliaaaa/`

## 3. 呼叫方式

**Slash command:**

```
/open-ragfilter-Jullliaaaa
```

**輸入 JSON 範例:**

```json
{
  "task_id": "ragfilter_s01",
  "question": "糖尿病會造成哪些慢性器官病變？有哪些預防方法？",
  "documents": [
    {"id": "d1", "text": "糖尿病有哪些慢性合併症？一、血管病變...二、眼睛病變...三、神經病變...四、腎臟病變..."},
    {"id": "d2", "text": "深部靜脈栓塞是指深部靜脈的血液回流不良..."},
    {"id": "d3", "text": "胃內容物逆流入食道..."},
    {"id": "d4", "text": "愛滋病又稱後天免疫缺乏症候群..."},
    {"id": "d5", "text": "腎臟病飲食原則（透析患者）..."}
  ]
}
```

**輸出 JSON 範例（此即輸出 schema）:**

```json
{
  "task_id": "ragfilter_s01",
  "kept": ["d1"],
  "removed": ["d2", "d3", "d4", "d5"],
  "confidence": 0.88
}
```

**輸出契約補充:**
- `kept` 與 `removed` 為文件 `id` 字串陣列，兩者聯集必須等於輸入所有文件 id（不多不少，不重疊）
- `task_id` 必須與輸入完全相同
- `confidence` 為 0.0~1.0 之間的浮點數

## 4. 自定 Verifiable Scenario

**Scenarios（共提供 9 個 public scenario，分三種難度與 noise 類型）:**

| Scenario | 難度 | Noise 類型 | 問題主題 |
|---|---|---|---|
| ragfilter_s01 | easy | cross_department | 糖尿病慢性器官病變 |
| ragfilter_s02 | easy | cross_department | 心肌梗塞症狀與處置 |
| ragfilter_s03 | easy | cross_department | 胃食道逆流症狀與生活注意 |
| ragfilter_s04 | medium | same_department_different_aspect | 糖尿病視網膜病變分級治療 |
| ragfilter_s05 | medium | same_department_different_aspect | 心衰竭日常照護 |
| ragfilter_s06 | medium | same_department_different_aspect | 深部靜脈栓塞危險因子與預防 |
| ragfilter_s07 | hard | adjacent_department | 透析患者飲食限磷限鉀 |
| ragfilter_s08 | hard | adjacent_department | 膽囊炎飲食原則 |
| ragfilter_s09 | hard | same_department_different_disease | 白內障症狀與手術時機 |

**三層 noise 難度設計:**

1. **Easy（cross_department）**: 完全不同科別的文件 → 應輕鬆濾除
2. **Medium（same_department_different_aspect）**: 同科別但不同面向 → 關鍵字命中卻答非所問
3. **Hard（adjacent_department / same_department_different_disease）**: 相鄰科別或同科不同病，內容極相似 → 字面最相似，最易騙過 LLM

**Metric:**

把「保留 essential 文件」視為二元分類問題。對每個 scenario，以 ground truth 中的 `essential` 集合為 1，`noise` 集合為 0：

- `Precision = |kept ∩ essential| / |kept|`
- `Recall = |kept ∩ essential| / |essential|`
- 單一 scenario 分數 = `F1 = 2 · P · R / (P + R)`（若分母為 0 則該項為 0）
- 跨 scenario 總分 = 各 scenario F1 的平均

評分器從輸出 JSON 的 `kept` 陣列自動計算，無需人工判斷。

**為何不可 gameable:**

- **Ground truth 對 skill 不可見**: 文件的 `label` 與 `ground_truth` 欄位只存在於評分環境的標註檔，不會傳入 skill 的輸入 JSON。skill 看不到答案。
- **全保留 / 全剔除都拿不到高分**: 全保留 → Precision 崩；全剔除 → Recall 崩。
- **Staff perturbation 仍須重現**: 打亂文件順序、替換等價詞、改寫部分文字、加入新誘餌時，hardcode 立刻失效。
- **困難 noise 防關鍵字作弊**: hard 等級的 noise 與 essential 文件在關鍵字、句型、用詞上高度重疊（s07 透析飲食 vs 心衰竭飲食、s08 膽囊炎低脂 vs 心肌梗塞低脂），純關鍵字比對或 BM25 分數判斷會被騙，必須真正理解語意。

## 5. 預期失敗模式

- **失敗 1 — 過度剔除（over-pruning，MAST 類別 3：驗證與品質）**: LLM 把語意稍遠但其實必要的 essential 文件也濾掉 → Recall 下降。觸發點: essential 文件用字較含蓄、未直接命中問題關鍵字。處理: SKILL.md Procedure 要求逐篇判斷是否直接回答問題。

- **失敗 2 — 困難 noise 漏網（MAST 類別 1：規格與角色）**: 同病不同子題的 distracting passage 因關鍵字重疊被誤判為 essential → Precision 下降。觸發點: hard 等級的 noise（s05 心衰竭 vs s02 心肌梗塞、s07 透析飲食 vs s08 膽囊炎飲食）。處理: SKILL.md 明確列舉 noise pattern，要求 LLM 對照問題主旨而非主題關鍵字。

- **失敗 3 — 輸出契約違規（MAST 類別 3：驗證與品質）**: LLM 輸出的 `kept` 與 `removed` 聯集不等於輸入所有 id。處理: `scripts/run.py` 在寫檔前檢查 overlap，並透過嚴格 schema 約束。

## 6. 互動對象

本 skill 為 stateless 單一 skill，與評分環境直接互動。不依賴其他同學的 skill，不使用 Hermes subagent —— 任務本質是單次分類而非多步推理，符合課程「預設用 Skill」的原則。

## 7. Token Budget 估算

每個 scenario 約 5 篇文件，每篇衛教段落約 150~400 字（約 200~600 tokens）。單次呼叫輸入約 2k~3.5k tokens、輸出約 0.3~0.6k tokens，遠低於 50k/scenario 上限。

| Scenario | 預估 input tokens | 預估 output tokens | 預估 total |
|---|---:|---:|---:|
| ragfilter_s01 (easy) | ~2200 | ~500 | ~2700 |
| ragfilter_s02 (easy) | ~2100 | ~500 | ~2600 |
| ragfilter_s03 (easy) | ~2300 | ~500 | ~2800 |
| ragfilter_s04 (medium) | ~2800 | ~600 | ~3400 |
| ragfilter_s05 (medium) | ~2600 | ~600 | ~3200 |
| ragfilter_s06 (medium) | ~2500 | ~600 | ~3100 |
| ragfilter_s07 (hard) | ~3000 | ~600 | ~3600 |
| ragfilter_s08 (hard) | ~2900 | ~600 | ~3500 |
| ragfilter_s09 (hard) | ~3100 | ~600 | ~3700 |
