# RulesBot — Planning Doc

Use this file to record your design decisions as you work through the lab.
There are no wrong answers — write enough that you could explain your reasoning to another group.

---

## Chunking Strategy

**Chunk size:** 300 characters (default)

**Overlap:** 50 characters

**Why this strategy fits rule book text:**

Rule books pack complete rules into short passages. A 300-character window usually captures one rule with enough context to embed meaningfully, while staying targeted enough for Q&A. Fifty characters of overlap preserves boundary-spanning rules without bloating the index (162 chunks for 9 games vs. 608 at 75-char chunks).

---

## Ninth Game: Scrabble

**Added:** `docs/scrabble.txt` — structured like the pre-loaded summaries (OVERVIEW, COMPONENTS, section headers, TILE VALUES list, WINNING).

**Retrieval vs. pre-loaded games:** Scrabble queries work as well as the original eight when the question names the game or a Scrabble-specific term ("bingo bonus", "Q tile"). Eval hit 10/10 including two Scrabble cases. Distances are similar (~0.43–0.45) to other games.

**Does document quality matter?** Yes. Because we wrote the summary with explicit section headers (`TILE VALUES`, `BINGO BONUS`, `WINNING`) and put the Q=10 line in a dedicated block, retrieval finds the right game reliably. A vague or poorly structured doc would fragment across chunks and score worse — the top Scrabble hit for "Q tile worth" often starts mid-list (`…TILE VALUES A=1, B=3…`) rather than at the section header, but still contains the answer. Clear section labels in the source text directly improve what gets retrieved.

**To load Scrabble in the app:** delete `./chroma_db`, restart `python app.py` (ingestion skips if the DB already exists).

---

## Chunking Experiments

Compared three configs on the same 10-query eval suite (`python eval_retrieval.py --experiment`):

| Config | chunk_size | overlap | Total chunks | Eval accuracy |
|--------|------------|---------|--------------|---------------|
| default | 300 | 50 | 162 | **100%** (10/10) |
| small | 75 | 10 | 608 | **100%** (10/10) |
| large | 1200 | 100 | 39 | **80%** (8/10) |

### Same three probe queries

| Query | default (300) | small (75) | large (1200) |
|-------|---------------|------------|--------------|
| "What happens when you roll a 7?" | 1 result, Catan dist=0.466 | 3 results, Catan dist=**0.338** (best) | **0 results** — all distances > 0.5 |
| "How many points is the Q tile worth in Scrabble?" | 3 Scrabble hits | 3 Scrabble hits (more focused chunks) | 2 Scrabble hits (near-whole-doc chunks) |
| "How do you win?" | **0 results** (all > 0.5) | 1 result, Scrabble only (wrong game for generic Q) | **0 results** |

### Where small chunks (75 char) fail

- **Noise and false positives:** Roll-a-7 query also returns Pandemic (0.477) and Monopoly (0.489) chunks that mention "7" out of context — small fragments carry weak semantic signal and match on surface tokens.
- **Database bloat:** 608 chunks (~3.7× default) with heavy overlap duplication — slower ingest, more storage, more near-duplicate vectors.
- **Fragmented text:** Many chunks start mid-word or mid-sentence (`he number rolled`, `rn, add 50 bonus`), which is ugly context for the LLM even when retrieval ranks correctly.

### Where small chunks help

- **Tighter matches:** Best Catan roll-7 distance drops from 0.466 → 0.338 because a chunk aligns more closely with just the `ROLLING A 7` section.
- **Vague queries:** "How do you win?" returns *something* (Scrabble WINNING at 0.426) where default returns nothing — though it picks one arbitrary game, not a useful multi-game answer.

### Where large chunks (1200 char) fail

- **Diluted embeddings:** Each vector averages an entire rule book section (often the whole doc). "Roll a 7" is buried inside a Catan mega-chunk; cosine distance rises above the 0.5 threshold → **no results**.
- **Lost precision:** Failed on Catan roll-7 and Risk attacking (0 results). Specific questions can't pull a single rule out of a blob.
- **Wrong focus for Q&A:** Scrabble Q-tile query returns overview/setup chunks (dist 0.398) instead of the TILE VALUES line — answer may still be in the chunk, but ranking is worse.

### Where large chunks help

- **Fewer chunks (39):** Fast ingest, tiny index — fine if you always pass whole documents and ask broad questions.
- **Uno Wild Draw Four:** Uno distances improve (0.256 top hit) because the full special-card rules stay in one embedding.

### Conclusion

Default 300/50 is the best balance for this lab: highest accuracy without small-chunk noise or large-chunk dilution. Small chunks trade precision for false positives; large chunks trade recall on specific questions for document-level blur.

---

## Retrieval Observations

After implementing retrieval, try these test queries and record what comes back:

| Query | Top result game | Does it make sense? |
|-------|----------------|---------------------|
| "How do you win?" | (none at default 300) | No — all games' WINNING sections score ~0.51, just above 0.5 threshold |
| "What happens when you roll a 7?" | Catan | Yes — ROLLING A 7 section, dist ~0.47 |
| "Can two players share a route?" | Ticket To Ride | Yes — double-route rule, dist ~0.35 |

**Anything surprising?**

Automated eval (`eval_retrieval.py`) scored 100% on 10 hand-picked queries for the default chunk config, including Scrabble. The 0.5 distance threshold is doing real work: it saves specific queries from noise but kills vague cross-game questions. Small chunks lower distances but invite token-level false positives (any chunk mentioning "7").

---

## Retrieval Eval Agent

**Script:** `eval_retrieval.py`

```powershell
python eval_retrieval.py --reingest    # rebuild eval DB + score
python eval_retrieval.py --experiment  # compare chunk configs
```

Checks whether `expected_game` appears in the top-3 `retrieve()` results. Logs failures with query, expected game, and actual hits for human review. Uses isolated `./chroma_eval` so experiments don't corrupt the app's `./chroma_db`.

---

## Response Quality

After implementing generation, try 2–3 questions and assess the answers:

| Query | Answer accurate? | Properly grounded? | Cited the right game? |
|-------|-----------------|-------------------|----------------------|
| "What happens when you roll a 7 in Catan?" | Yes | Yes | Yes — Catan |
| "How many points is the Q tile worth in Scrabble?" | Yes (Q=10) | Yes | Yes — Scrabble |
| "What year was Catan invented?" | N/A (refused) | Yes — exact fallback | N/A |

**What would you change about the prompt to improve grounding?**

Current strict grounding works well. Optional improvement: instruct the model to quote or paraphrase without dropping qualifiers (e.g. "random resource card" vs. shortened "one resource"). For vague multi-game questions, improve retrieval (lower threshold, game detection) before tuning the generator prompt.
