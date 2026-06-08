# Spec: `generate_response()`

**File:** `generator.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user query and a list of retrieved rule chunks, generate a response that directly answers the question using only the retrieved text as context. The response must be grounded — it should not draw on the model's general knowledge of board games, only on what was retrieved.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's original question |
| `retrieved_chunks` | `list[dict]` | Ranked list of chunks from `retrieve()`, each with `"text"`, `"game"`, and `"distance"` |

**Output:** `str`

A plain string containing the response to show the user. The response should:
- Answer the question using only the retrieved rule text
- Identify which game the answer comes from
- Acknowledge clearly when the answer is not found in the loaded rules

Returns a fallback string (not an error) when `retrieved_chunks` is empty.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Context formatting

*How will you format the retrieved chunks before passing them to the LLM? Describe the structure — not the code. Consider: will you label chunks by game? Include distance scores? Separate chunks with delimiters?*

```
Each chunk is placed in the user message inside a labeled, numbered block so the
model can tell sources apart (research on RAG shows explicit source labels and
clear delimiters reduce cross-source blending):

  The following rule excerpts were retrieved from the loaded rule books.
  They are the ONLY source you may use to answer.

  --- Excerpt 1 | Game: Catan ---
  {chunk text}

  --- Excerpt 2 | Game: Catan ---
  {chunk text}

Chunks are listed in retrieval order (most relevant first). Each block is
labeled with its game name so the model can cite the correct source. Distance
scores are NOT included — they are a retrieval signal, not useful context for
the LLM and may cause it to ignore weaker-but-correct excerpts. A blank line
separates each excerpt. The user's question follows after a "Question:" header.
```

---

### System prompt — grounding instruction

*Write the exact system prompt instruction you will use to prevent the model from answering beyond the retrieved text. This is the most important design decision in this function.*

```
You are RulesBot, a board game rules assistant.

STRICT GROUNDING RULES — follow these without exception:
1. Answer using ONLY the rule excerpts provided in the user message. Every fact
   in your answer must be directly supported by text in those excerpts.
2. Do NOT use your general knowledge of board games, common house rules, forum
   advice, or any information not literally present in the excerpts — even if you
   are confident you know the correct answer from outside the provided text.
3. If the excerpts do not contain enough information to fully answer the
   question, respond with exactly this sentence and nothing else:
   "I couldn't find that in the loaded rule books."
4. Do NOT guess, infer beyond what the text states, extrapolate, or fill gaps
   with outside knowledge — even when the excerpts are related but incomplete.
```

*Pressure-test notes (ways a model might still sidestep, and how the prompt counters them):*
- *Partial knowledge: model knows Catan rules but excerpt is incomplete → rule 2 forbids outside knowledge even when confident*
- *Tangential excerpts: retrieved text mentions dice but not the specific rule → rule 4 blocks inferring beyond stated text*
- *Helpful elaboration: model adds common house rules → rule 1 requires every fact be in excerpts*
- *Soft refusal: model says "typically..." from general knowledge → rule 3 forces exact fallback sentence*

---

### System prompt — citation instruction

*Write the exact instruction you will use to tell the model to identify which game its answer comes from.*

```
CITATION:
Begin your answer with "According to the [Game Name] rules:" where [Game Name]
is the game the supporting excerpt(s) come from. Use the game name exactly as
labeled in the excerpt headers. If multiple games' excerpts are needed to answer,
name each game.
```

---

### Fallback behavior

*What should the response say when the answer isn't found in the loaded rule books? Write the exact fallback message.*

```
[your answer here]
```

---

### Handling low-relevance chunks

*`retrieved_chunks` may include chunks with high distance scores (weak relevance). Will you filter these out before building context, pass them all in, or handle them another way? What are the tradeoffs?*

```
[your answer here]
```

---

### Message structure

*Describe how you will structure the messages list for the API call — what goes in the system message vs. the user message?*

```
messages = [
  {"role": "system", "content": SYSTEM_PROMPT},   # grounding + citation rules
  {"role": "user",   "content": context + question},
]

System message: the exact grounding and citation instructions (unchanged every call).
User message: formatted excerpt blocks, then "Question: {query}" on the last line.
No assistant pre-fill; single-turn completion.
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Test query and response:**

```
Query: What happens when you roll a 7 in Catan?
Response: According to the Catan rules: When a 7 is rolled, no resources are
produced. Every player with more than 7 resource cards in hand must discard
half (rounded down). The player who rolled moves the robber to any terrain hex
and steals one resource.
Correctly grounded? Yes — every claim matches the retrieved Catan excerpt
("ROLLING A 7" section); nothing added from outside knowledge.
Cited the right game? Yes — Catan.
```

**One thing you changed from your original spec after seeing the actual output:**

```
No prompt changes needed. Two behaviors worth noting: (1) when retrieve()
returns zero chunks (e.g. "How do you play chess?"), the empty-list fallback
in generate_response() fires before the LLM is called — different from the
in-prompt "I couldn't find that in the loaded rule books." used when chunks
exist but don't answer (e.g. "What year was Catan invented?"). Both are
correct; the distinction is intentional.
```
