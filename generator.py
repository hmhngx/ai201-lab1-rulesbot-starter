from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are RulesBot, a board game rules assistant.

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

CITATION:
Begin your answer with "According to the [Game Name] rules:" where [Game Name]
is the game the supporting excerpt(s) come from. Use the game name exactly as
labeled in the excerpt headers. If multiple games' excerpts are needed to answer,
name each game."""


def _format_context(chunks):
    lines = [
        "The following rule excerpts were retrieved from the loaded rule books.",
        "They are the ONLY source you may use to answer.",
        "",
    ]
    for i, chunk in enumerate(chunks, start=1):
        lines.append(f"--- Excerpt {i} | Game: {chunk['game']} ---")
        lines.append(chunk["text"])
        lines.append("")
    return "\n".join(lines)


def generate_response(query, retrieved_chunks):
    """
    Generate a grounded answer from retrieved rule chunks.

    TODO — Milestone 3:

    `retrieved_chunks` is the list returned by retrieve(). Each item is a dict:
      - "text"     : the chunk text
      - "game"     : the game name
      - "distance" : similarity score (you can use this to filter weak matches)

    Before writing code, talk through these with your group:
      - How will you format the chunks into a context block for the prompt?
      - What instructions will stop the model from answering beyond what the
        rules say? (Grounding is the whole point — a confident wrong answer
        is worse than an honest "I don't know.")
      - How will you surface which game each answer comes from?

    Your response should:
      1. Answer using only the retrieved context — not the model's general knowledge
      2. Make clear which game the answer comes from
      3. Say so clearly when the answer isn't in the loaded rules

    Return the response as a plain string.
    """
    if not retrieved_chunks:
        return (
            "I couldn't find anything relevant in the loaded rule books. "
            "Try rephrasing your question — or check that your ingestion pipeline is working."
        )

    context = _format_context(retrieved_chunks)
    user_message = f"{context}\nQuestion: {query}"

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    return response.choices[0].message.content
