# Spec: `retrieve()`

**File:** `retriever.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user's natural language query, find the most relevant chunks from the vector store using semantic similarity search. Return them ranked by relevance so that `generate_response()` can use them as context.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's natural language question |
| `n_results` | `int` | Maximum number of chunks to return (default: `N_RESULTS` from `config.py`) |

**Output:** `list[dict]`

Each dict in the returned list must contain exactly these keys:

| Key | Type | Description |
|-----|------|-------------|
| `"text"` | `str` | The chunk text |
| `"game"` | `str` | The game name this chunk came from |
| `"distance"` | `float` | Cosine distance score — lower means more similar to the query |

Results should be ordered from most to least relevant (lowest to highest distance). Returns an empty list `[]` if the collection contains no documents.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Query approach

*Describe how you will use `_collection.query()` to find relevant chunks. What arguments will you pass, and why?*

```
[your answer here]
```

---

### Return structure

*Sketch out what one item in your return list looks like as a concrete example. Where does each field come from in the query results?*

```
One item in the returned list looks like:

{
    "text": "If you roll a 7, the active player moves the robber...",
    "game": "Catan",
    "distance": 0.31
}

Built by zipping the three parallel inner lists at the same index `i`
(best match is i=0):

  "text"     ← results["documents"][0][i]   # the stored chunk text
  "game"     ← results["metadatas"][0][i]["game"]  # set during embed_and_store()
  "distance" ← results["distances"][0][i]   # cosine distance; lower = more similar

The final list is ordered most-to-least relevant (lowest distance first),
matching ChromaDB's default ranking within the inner list.
```

---

### Handling the nested result structure

*`_collection.query()` returns nested lists. Describe what index you need to access to get the actual list of results for a single query, and why the nesting exists.*

```
_collection.query() accepts query_texts as a list so it can embed and search
multiple queries in one call (batch mode). The response mirrors that shape:
documents, metadatas, and distances are each a list-of-lists — the outer list
has one entry per input query, and the inner list holds that query's ranked hits.

We pass a single query (query_texts=[query]), so we index [0] on each field
to unwrap the outer list:

  results["documents"][0]   → list of chunk text strings
  results["metadatas"][0]   → list of metadata dicts
  results["distances"][0]   → list of float distance scores

All three inner lists are the same length and aligned by index — result i in
documents corresponds to result i in metadatas and distances.
```

---

### Relevance threshold

*Will you filter out results above a certain distance score, or return all `n_results` regardless of how relevant they are? What are the tradeoffs of each approach?*

```
Filter out chunks with cosine distance > 0.5 before returning. Keep only
results at or below the threshold, still ordered lowest-distance first.

Tradeoffs:
  - Return all n_results: simpler code, always gives generate_response()
    something to work with — but weak matches (distance > ~0.5 for this
    embedding model, per system-design.md) can pollute the LLM context and
    invite confident wrong answers.
  - Filter in retrieve(): retrieve() acts as a quality gate — only
    semantically plausible chunks reach the generator. May return fewer than
    n_results or an empty list when nothing matches well, which is correct
    for grounding: better to say "not found" than to answer from noise.

We filter here (0.5) so retrieve()'s contract is "relevant chunks only."
generate_response() can apply the same threshold again as a safety net, but
retrieve() is the first line of defense.
```

---

### Edge cases

*How does your implementation behave when: (a) the collection is empty, (b) the query matches no chunks well, (c) the query matches chunks from multiple games?*

```
[your answer here]
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 3.*

**Test query and top result returned:**

```
Query: What happens when you roll a 7?
Top result game: Catan
Distance score: 0.466
Does it make sense? Yes — the top chunk contains the "ROLLING A 7" section
("When a 7 is rolled, no resources are produced…"). The two runners-up were
Risk dice-combat rules (dist 0.597, 0.610) and were correctly filtered out
by the 0.5 threshold. Only one chunk passed the filter for this query.
```

**One thing about the query results that surprised you:**

```
"How do you win?" returned sensible raw hits from three different games
(Monopoly, Risk, Ticket to Ride — each chunk contained a WINNING section),
but all three scored just above the 0.5 cutoff (0.507, 0.509, 0.522), so
retrieve() returned an empty list. The chunks themselves were fine; the
vague query just didn't embed close enough to any single game's winning rule.
Distance scores did reflect relevance — specific queries score lower and
land on the right game; vague cross-game queries cluster near the threshold.
```
