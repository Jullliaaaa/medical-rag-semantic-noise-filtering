---
name: open-ragfilter-Jullliaaaa
description: RAG noise filter for health education documents. Given a user question and a list of retrieved documents (with retrieval scores), identify which documents directly answer the question and filter out noise.
version: 1.0.0
metadata:
  hermes:
    tags: [rag, filter, retrieval, healthcare, aiase]
    category: aiase
    requires_toolsets: [terminal]
---

# RAG Noise Filter Skill (Open Track)

## When to Use
Triggered when the user inputs `/open-ragfilter-Jullliaaaa {json}`.

Input format:
```json
{
  "task_id": "ragfilter_s01",
  "question": "糖尿病會造成哪些慢性器官病變？",
  "documents": [
    {"id": "d1", "text": "..."},
    {"id": "d2", "text": "..."}
  ]
}
```

The skill must classify each document as either `essential` (directly answers the question) or `noise` (irrelevant or off-topic, even if same domain).

## Procedure
1. Read the `question` carefully and identify what specific information is being asked.

2. For EACH document, judge:
   - Does this document DIRECTLY answer the question?
   - Or is it merely "same topic but answers a different aspect"?
   - High keyword overlap does NOT mean essential. A document mentioning the same disease but discussing prevention vs symptoms (when question asks symptoms) is NOISE.

3. Common noise patterns to watch for:
   - **Cross-department noise**: completely different medical field (e.g., eye disease vs diabetes question)
   - **Same-department different-aspect noise**: same disease but different sub-topic (e.g., heart failure care vs heart attack symptoms)
   - **Adjacent-department noise**: similar dietary advice but for different disease (e.g., kidney diet vs gallbladder diet)
   - **Keyword overlap noise**: shares many keywords but answers different question

4. Build two lists:
   - `kept`: documents that directly answer the question
   - `removed`: documents that are noise

5. Use terminal tool with absolute path to write result (skill_dir provided by Hermes as [Skill directory:]):
   python3 <skill_dir>/scripts/run.py --task_id "<task_id>" --kept '["d1"]' --removed '["d2","d3","d4","d5"]' --confidence 0.85

6. scripts/run.py validates that kept ∪ removed covers all input document ids exactly (no missing, no extra), then writes the result file. Do NOT output JSON in the conversation.

## Pitfalls
- `kept` and `removed` together MUST equal exactly the set of input document ids. Missing ids or extra ids = contract violation.
- Do NOT keep all documents (Precision will collapse) and do NOT remove all (Recall will collapse). Be discerning.
- "Same disease" does not mean "essential". Match question intent, not just topic.
- A document explaining heart failure care is NOT essential for a question about heart attack symptoms, even though both are heart-related.
- `task_id` in output MUST exactly equal input `task_id`.

## Verification
Result file exists, is valid JSON object, contains:
- `task_id` (equals input)
- `kept` (array of document ids)
- `removed` (array of document ids)
- `confidence` (number in 0..1)
And `kept ∪ removed` exactly equals the set of input document ids.
