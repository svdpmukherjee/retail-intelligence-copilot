"""Run the acceptance case catalogue against the live pipeline and print evidence.

Usage (from the backend/ directory, so backend/.env is picked up):
    python ../docs/testing/acceptance/run_acceptance.py

Needs: pgvector up + index built; Ollama (llama3.2:3b) for the LLM paths. $0.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))

from agents.pipeline import answer, new_thread  # noqa: E402
from agents.router import route  # noqa: E402
from app.cost import CostLedger  # noqa: E402


def line(c="-"):
    print(c * 90)


def ev(r):
    a = r.audit
    print("ANSWER:", " ".join(r.answer.split())[:600])
    print("CITES :", [(c.n, c.label) for c in r.citations])
    print(f"AUDIT : intent={a.get('intent')} tools={a.get('tool_path')} "
          f"grounding={a.get('grounding')} sources={len(a.get('sources') or [])} "
          f"tokens={a.get('tokens')} cost=${a.get('cost_usd')} lat={a.get('latency_ms')}ms "
          f"mem={a.get('memory')}")


async def shot(cid, q, role):
    line("=")
    try:
        d = await route(q, role, CostLedger())
        print(f"{cid}  Q: {q!r} | role={role} -> routed intent={d.intent}")
    except Exception as e:  # noqa: BLE001
        print(f"{cid}  Q: {q!r} | role={role} -> ROUTE {type(e).__name__}: {e}")
    try:
        ev(await answer(q, role))
    except Exception as e:  # noqa: BLE001
        print(f"PIPELINE {type(e).__name__}: {str(e)[:200]}")


async def main():
    print("ROUTING & ANSWER QUALITY")
    await shot("AC-1 ", "What is the average rating for Electronics?", "executive")
    await shot("AC-2 ", "How many reviews are there per category?", "analyst")
    await shot("AC-3 ", "What do customers say about build quality?", "support")
    await shot("AC-4 ", "What is the return and refund policy?", "executive")
    await shot("AC-5 ", "How do I set up the laptop?", "admin")
    await shot("AC-6 ", "Why did ratings drop for Electronics?", "analyst")

    print("\nGOVERNANCE & SAFETY")
    await shot("AC-7 ", "What do customers say about battery life?", "marketing")
    await shot("AC-8 ", "What do customers say about battery life?", "hacker")
    await shot("AC-9 ", "What is the return and refund policy?", "support")
    await shot("AC-10", "What do customers say about build quality?", "support")

    print("\nRETRIEVAL MECHANICS")
    from retrieval.embeddings import get_embedder
    from retrieval.hybrid import rrf_fuse
    from retrieval.rerank import LocalReranker, NoReranker
    from retrieval.vector_store import get_vector_store
    from app.config import get_settings

    s, store, emb = get_settings(), get_vector_store(), get_embedder()
    q = "stopped working"  # co-occurring terms so BM25 returns hits too
    filt = {"source_type": "review"}
    vec = store.query(emb.embed([q])[0], 6, filters=filt)
    kw = store.keyword_query(q, 6, filters=filt)
    fused = rrf_fuse([vec, kw], s.rrf_k)
    line("=")
    print(f"AC-11  hybrid probe q={q!r}")
    print("  vector-only top3 :", [h.chunk.id[:8] for h in vec[:3]])
    print("  keyword-only top3:", [h.chunk.id[:8] for h in kw[:3]])
    print("  fused (RRF) top3 :", [h.chunk.id[:8] for h in fused[:3]])
    line("=")
    print("AC-12  rerank probe (none vs local cross-encoder)")
    none_order = [h.chunk.id[:8] for h in NoReranker().rerank(q, fused[:6])]
    local = LocalReranker(s).rerank(q, fused[:6])
    print("  none  order:", none_order)
    print("  local order:", [h.chunk.id[:8] for h in local])
    print("  local scores:", [round(h.score, 3) for h in local])

    print("\nCONVERSATION & MEMORY")
    line("=")
    uid, tid = "acc-user", new_thread("acc-user", "support")
    print(f"AC-13  thread={tid}")
    for i, qq in enumerate(["What do customers say about build quality?",
                            "What else do reviews mention about quality?",
                            "What do customers say about the products overall?"], 1):
        try:
            r = await answer(qq, "support", thread_id=tid, user_id=uid)
            print(f"  turn{i}: history_turns_used={r.audit['memory']['history_turns_used']} "
                  f"persisted={r.audit['memory']['persisted']}")
        except Exception as e:  # noqa: BLE001  one bad turn must not abort the suite
            print(f"  turn{i}: ERROR {type(e).__name__}: {str(e)[:120]}")
    line("=")
    uid2 = "acc-pref"
    tA = new_thread(uid2, "support")
    await answer("From now on, please always keep answers short.", "support",
                 thread_id=tA, user_id=uid2)
    tB = new_thread(uid2, "support")
    await answer("What do customers say about build quality?", "support",
                 thread_id=tB, user_id=uid2)
    from memory.manager import MemoryManager
    ctx = await asyncio.to_thread(MemoryManager().load, tB, uid2, "support", limit=6)
    print(f"AC-14  thread B loaded preferences={ctx.preferences} "
          f"prior_findings={len(ctx.prior_findings)}")


if __name__ == "__main__":
    asyncio.run(main())
