"""
Retrieval evaluation script for RulesBot.

Runs a fixed set of question -> expected-game pairs through retrieve(),
reports accuracy, and optionally logs failures for human review.

Usage:
  python eval_retrieval.py                    # eval on current chroma_db
  python eval_retrieval.py --reingest         # wipe DB, re-ingest default chunks, eval
  python eval_retrieval.py --experiment       # compare default vs small vs large chunks
"""

import argparse
import importlib
import shutil
import sys

import config
from config import CHROMA_COLLECTION
from ingest import load_documents, chunk_document

EVAL_CHROMA_PATH = "./chroma_eval"
_last_retriever = None

EVAL_CASES = [
    {
        "query": "What happens when you roll a 7?",
        "expected_game": "Catan",
        "notes": "Specific Catan mechanic",
    },
    {
        "query": "How do you get out of Jail in Monopoly?",
        "expected_game": "Monopoly",
        "notes": "Monopoly jail rules",
    },
    {
        "query": "How many points is the Q tile worth in Scrabble?",
        "expected_game": "Scrabble",
        "notes": "New game — tile values section",
    },
    {
        "query": "What is the bingo bonus in Scrabble?",
        "expected_game": "Scrabble",
        "notes": "New game — 7-tile bonus",
    },
    {
        "query": "What happens when a city gets a 4th disease cube?",
        "expected_game": "Pandemic",
        "notes": "Pandemic outbreak",
    },
    {
        "query": "How does the Spymaster give clues in Codenames?",
        "expected_game": "Codenames",
        "notes": "Codenames spymaster role",
    },
    {
        "query": "Can two players claim the same route?",
        "expected_game": "Ticket To Ride",
        "notes": "Ticket to Ride route claiming",
    },
    {
        "query": "How does attacking work in Risk?",
        "expected_game": "Risk",
        "notes": "Risk combat",
    },
    {
        "query": "How does making a Suggestion work in Clue?",
        "expected_game": "Clue",
        "notes": "Clue suggestion mechanic",
    },
    {
        "query": "When can you play a Wild Draw Four in Uno?",
        "expected_game": "Uno",
        "notes": "Uno special card",
    },
]

CHUNK_CONFIGS = {
    "default": {"chunk_size": 300, "overlap": 50, "min_length": 50},
    "small": {"chunk_size": 75, "overlap": 10, "min_length": 30},
    "large": {"chunk_size": 1200, "overlap": 100, "min_length": 50},
}

EXPERIMENT_QUERIES = [
    "What happens when you roll a 7?",
    "How many points is the Q tile worth in Scrabble?",
    "How do you win?",
]


def reload_retriever():
    """Re-import retriever after wiping chroma so the client reconnects cleanly."""
    config.CHROMA_PATH = EVAL_CHROMA_PATH
    for mod in ("retriever", "chromadb"):
        if mod in sys.modules:
            del sys.modules[mod]
    import retriever
    return retriever


def wipe_chroma():
    global _last_retriever
    if _last_retriever is not None:
        try:
            _last_retriever._client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass
    shutil.rmtree(EVAL_CHROMA_PATH, ignore_errors=True)
    _last_retriever = None


def ingest_with_config(chunk_size=300, overlap=50, min_length=50):
    wipe_chroma()
    retriever = reload_retriever()
    global _last_retriever
    _last_retriever = retriever

    documents = load_documents()
    all_chunks = []
    for doc in documents:
        chunks = chunk_document(
            doc["text"],
            doc["game"],
            chunk_size=chunk_size,
            overlap=overlap,
            min_length=min_length,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        raise RuntimeError("No chunks produced during ingestion.")

    retriever.embed_and_store(all_chunks)
    stored = retriever.get_collection().count()
    print(
        f"Ingested {len(all_chunks)} chunks, {stored} in DB "
        f"(size={chunk_size}, overlap={overlap}, min={min_length})"
    )
    if stored != len(all_chunks):
        raise RuntimeError(f"DB count mismatch: expected {len(all_chunks)}, got {stored}")
    return retriever, len(all_chunks)


def evaluate_retrieval(retriever, cases=EVAL_CASES, top_k=3, distance_threshold=0.5):
    """Return accuracy score and per-case results."""
    results = []
    hits = 0

    for case in cases:
        chunks = retriever.retrieve(case["query"])
        top_games = [c["game"] for c in chunks[:top_k]]
        top_distances = [c["distance"] for c in chunks[:top_k]]
        hit = case["expected_game"] in top_games
        if hit:
            hits += 1

        rank = None
        if hit:
            rank = top_games.index(case["expected_game"]) + 1

        entry = {
            **case,
            "hit": hit,
            "rank": rank,
            "returned": len(chunks),
            "top_games": top_games,
            "top_distances": top_distances,
        }
        results.append(entry)

        status = "PASS" if hit else "FAIL"
        games_str = ", ".join(
            f"{g} ({d:.3f})" for g, d in zip(top_games, top_distances)
        ) or "(no results)"
        print(f"  [{status}] {case['query']!r}")
        print(f"         expected: {case['expected_game']} | got: {games_str}")
        if not hit:
            print(f"         notes: {case['notes']}")

    accuracy = hits / len(cases) if cases else 0.0
    return accuracy, results


def run_experiment():
    print("\n" + "=" * 60)
    print("CHUNKING EXPERIMENT")
    print("=" * 60)

    summary = []
    for name, cfg in CHUNK_CONFIGS.items():
        print(f"\n--- Config: {name} ({cfg}) ---")
        retriever, chunk_count = ingest_with_config(**cfg)

        for query in EXPERIMENT_QUERIES:
            chunks = retriever.retrieve(query)
            print(f"\n  Query: {query!r} ({len(chunks)} results)")
            for i, c in enumerate(chunks, 1):
                print(
                    f"    {i}. [{c['game']}] dist={c['distance']:.3f} "
                    f"{c['text'][:70].replace(chr(10), ' ')}..."
                )

        accuracy, _ = evaluate_retrieval(retriever)
        summary.append((name, chunk_count, accuracy))
        print(f"\n  Retrieval accuracy @ top-3: {accuracy:.0%}")

    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    for name, count, acc in summary:
        print(f"  {name:8s}  chunks={count:4d}  accuracy={acc:.0%}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RulesBot retrieval quality")
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Delete chroma_db and re-ingest with default chunk settings before eval",
    )
    parser.add_argument(
        "--experiment",
        action="store_true",
        help="Run chunking comparison (default vs small vs large), then exit",
    )
    args = parser.parse_args()

    if args.experiment:
        run_experiment()
        return

    if args.reingest:
        print("Re-ingesting with default chunk settings (eval DB)...")
        retriever, _ = ingest_with_config(**CHUNK_CONFIGS["default"])
    else:
        config.CHROMA_PATH = EVAL_CHROMA_PATH
        retriever = reload_retriever()
        if retriever.get_collection().count() == 0:
            print("Eval DB empty — run with --reingest first.")
            return

    print("\n" + "=" * 60)
    print("RETRIEVAL EVAL")
    print("=" * 60)
    accuracy, results = evaluate_retrieval(retriever)
    print("\n" + "=" * 60)
    print(f"Retrieval accuracy (top-3): {hits_display(accuracy, results)}")
    print("=" * 60)

    failures = [r for r in results if not r["hit"]]
    if failures:
        print(f"\n{len(failures)} failure(s) for human review:")
        for f in failures:
            print(f"  - {f['query']!r} (expected {f['expected_game']})")


def hits_display(accuracy, results):
    hits = sum(1 for r in results if r["hit"])
    return f"{hits}/{len(results)} = {accuracy:.0%}"


if __name__ == "__main__":
    main()
