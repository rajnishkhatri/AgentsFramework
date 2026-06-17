link: https://www.linkedin.com/pulse/memory-systems-fundamentals-rajnish-khatri-qt0wc/?trackingId=vgXE55GCQmm9j7osoeHVBA%3D%3D
article: Memory Systems Fundamentals

 rajnish khatri
rajnish khatri 

Principal Consultant at Infosys | LLM Evaluation & Multi-Agent Systems Expert


November 17, 2025
Why Memory Matters 

Large language models (LLMs) are inherently stateless—each call forgets every prior interaction unless context is replayed—so they cannot remember a user’s name, past failures, or open tasks without explicit memory scaffolding. Hosted assistants feel persistent only because they bolt on memory modules and tool outputs that track prior actions, which is exactly what we must reproduce inside our custom agents. An “LLM” answers in isolation; an “agent” couples the base model with memory (plus tools, planning, safety) so it can reason about prior choices, avoid loops, and build long-lived context quickly

Article content


Memory taxonomy at a glance

Article content


Why agents need all five types

Customer support co-pilot: must remember who asked what (working), which troubleshooting branches already failed (episodic), link to accurate runbooks (semantic), execute escalation policy (procedural), and still leverage parametric facts for general chit-chat.
Field service maintenance agent: caches on-site sensor readings (working), logs previous interventions per device (episodic), queries CAD manuals (semantic), adheres to safety checklist (procedural), and falls back on common-engineering knowledge (parametric) between syncs.
Research analyst workflow (Search-o1): spins up temporary working memory during reasoning traces, writes durable notes per insight (episodic), retrieves corporate filings (semantic), enforces due-diligence steps (procedural), and leans on parametric numeracy for quick estimates.

Short-Term Memory Systems

2.1 Working Memory Definition

Working memory is the finite buffer of recent turns that we keep feeding back into the LLM so it can reason about the latest state; it is literally the conversation history the agent copies across calls. Because every model has a combined input/output ceiling (8K, 128K, 1M tokens, etc.) When the window overflows, the model truncates, leading to forgotten constraints or half-finished responses, so the management techniques below are non-negotiable for production agents.

2.2 Trimming Strategies

Article content
Config knobs:

MAX_CONTEXT_TOKENS: absolute cap; default tied to EXECUTION_MODE (e.g., 1500 demo, 6000 full).
PINNED_FACTS: list of episodic facts (user profile) that re-insert even after trimming.
DECAY_AFTER_TURNS: automatically move old turns into summary queue once they age past N interactions.

2.3 Summarization Strategies

Trimming alone eventually drops facts we still care about, so we introduce layered summaries:

Rolling append: After every turn, ask a summarizer (can be the same base model in low-cost mode) to append 1–2 sentences capturing new facts. Preserves chronology at the expense of steadily growing summaries.
Windowed compression: Every M turns, collapse that block into a short paragraph and replace the raw turns with the paragraph, keeping overall size bounded. Useful for call-center style logs with repetitive structure.
Update-in-place: Maintain a single mutable summary (“User preferences”) and instruct the model to update specific fields, which keeps the token count stable at the cost of losing historical nuance.
Hybrid: Keep rolling summary for semantic facts and an update-in-place ledger for hard constraints (budget, deadlines). This mirrors MemoryBank’s reinforcement/decay behavior.

Latency impact: summarization adds an extra LLM call (100–400 ms) but typically saves multiple dollars in downstream context costs. We will benchmark both approaches inside the notebook’s working-memory exercises.

2.4 Conversation History Example

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List

Message = Dict[str, str]

@dataclass
class ConversationMemory:
    max_tokens: int = 1500
    summary_trigger: int = 900
    messages: Deque[Message] = field(default_factory=deque)
    rolling_summary: List[str] = field(default_factory=list)

    def add_turn(self, user: str, assistant: str) -> None:
        self.messages.append({"role": "user", "content": user})
        self.messages.append({"role": "assistant", "content": assistant})
        self._trim()
        if self._token_count() > self.summary_trigger:
            self._summarize_recent()

    def _trim(self) -> None:
        while self._token_count() > self.max_tokens and self.messages:
            self.messages.popleft()

    def _summarize_recent(self, window: int = 4) -> None:
        recent = list(self.messages)[-window:]
        summary = summarize_block(recent)
        self.rolling_summary.append(summary)
        for _ in range(min(window, len(self.messages))):
            self.messages.pop()
        self.messages.appendleft({"role": "system", "content": "[Summary]" + summary})

    def _token_count(self) -> int:
        # Lightweight heuristic; swap in tiktoken later
        return sum(len(m["content"].split()) for m in self.messages)

def summarize_block(block: List[Message]) -> str:
    """Placeholder: replace with low-cost LLM or embedding-based summary."""
    joined = " ".join(m["content"] for m in block)
    return joined[:200] + ("..." if len(joined) > 200 else "")


memory = ConversationMemory(max_tokens=200, summary_trigger=120)
memory.add_turn("I love Kashmiri food, especially rogan josh.", "Noted! I'll remember that.")
memory.add_turn("Also remind me if a recipe uses nuts.", "I'll flag nut-heavy recipes from now on.") 
This toy class mirrors the notebook helpers we will formalize later: trim aggressively once the token budget is breached, then fall back to rolling summaries so key preferences stay available even after many turns. 

Long-Term Memory Patterns

3.1 Episodic vs Semantic vs Procedural

Long-term memory is not monolithic; we partition it so agents can reason about specific experiences (episodic), persistent knowledge (semantic), and how-to rules (procedural). 

Episodic memories include task traces, user-specific facts, and prior tool calls, often stored in append-only logs or vector DB collections keyed by interaction IDs.

 Semantic memory typically lives in curated corpora (internal docs, research papers) that we embed for RAG workflows.

 Procedural memory covers policies we externalize (YAML configs, guardrail prompts) when a simple system prompt is insufficient. Many production teams collapse these into a single collection for expediency, but splitting lets us tune retention and retrieval independently (e.g., episodic facts expire faster than governance policies).

3.2 Classic RAG Recap

Classic Retrieval-Augmented Generation works in two stages:

 ingestion (chunk → embed → store)

 and 

inference (embed query → retrieve top k → stuff into prompt → generate).

3.3 MemoryBank Pattern

MemoryBank stores multi-turn conversations, summaries, and a “user portrait” that captures traits/emotions, then applies spaced-repetition math so frequently touched memories decay more slowly while stale memories evaporate.  Each interaction is embedded and tagged; as the agent retrieves a memory, its strength is reinforced, preventing deletion.

 This pattern shines for consumer assistants or customer-support copilots that need to recall long-lived user preferences without manual profile engineering. For ops: plan capacity for three embedded stores (raw turns, summaries, portraits) and run a nightly cron that prunes low-strength memories to contain cost.

3.4 A-MEM Pattern

A-MEM reimagines memory as a Zettelkasten notebook: each interaction becomes a single “note” with keywords, tags, timestamp, description, and embedding. Newly created notes immediately run similarity searches to link to existing ones, and both sides update metadata so the graph evolves over time. 

This suits research and investigation agents (e.g., Bhagavad Gita commentary explorer) because it encourages atomic knowledge chunks and rich cross-linking. Implementation tips you will revisit in the notebook: keep embeddings for the concatenated note payload, maintain adjacency lists for linked notes, and periodically relabel tags when new connections emerge.

3.5 Search-o1 Pattern

Search-o1 injects retrieval directly into the reasoning trace: the agent emits <|begin_search_query|> ,<|end_search_query|> tags , mid-thought, fetches results, and then passes both the documents and ongoing reasoning to a Reason-in-Documents module that condenses information before writing the next reasoning token. 

Token accounting: you pay for search queries, retrieved document tokens, and condensed reasoning tokens. 
Context freshness: because retrieval happens inside the reasoning loop, the agent can branch into secondary searches (e.g., first learn flamingos are pink due to diet, then re-query for “carotenoid pigments”) without restarting the outer conversation.

Use Search-o1 when your agent needs to reason deeply about emerging facts (thick research memos, regulatory analysis) and you can afford the ~15–30% overhead shown in the forthcoming notebook metrics. 

For routine FAQ-style queries, classic RAG or MemoryBank is simpler and cheaper.

search-o1 diagram

Article content
search-o1
Vector DB Decision Matrix 

4.1 Pinecone / Weaviate / Chroma

Article content


4.2 Qdrant / Milvus / pgvector

Article content


4.3 Compass Metrics Extraction

Short-term lookup vs. vector retrieval: Redis-based caches deliver <5 ms access for hot episodic facts compared with 50–200 ms vector round trips, so blending both tiers keeps agents responsive. 
End-to-end RAG latency budget averages 630 ms–2.4 s (embeddings 20–50 ms, vector search 50–200 ms, retrieval 10–30 ms, optional rerank 50–100 ms, LLM generation 500–2000 ms). Build dashboards that isolate each stage for bottleneck hunting. lines 89-90.
Context compression vs. selective retrieval ROI: 100 turns without management cost $24; add 50% compression → $12; add selective retrieval (20% context) → $4.80. Use these deltas when justifying Chroma → Pinecone upgrades. 

4.4 Decision Framework

80/20 guidance. 

For ~80% of agent teams, start with Pinecone (if you need managed uptime) or Weaviate (if you need hybrid search + optional self-hosting). They balance feature depth, latency, and cost 

The remaining 20% fall into edge categories:

Shoestring prototypes → Chroma running locally, optionally persisting to SQLite/S3.
Filtering-heavy knowledge graphs → Qdrant, thanks to payload indexing.
Throughput monsters (>100M vectors) → Milvus/Zilliz-managed clusters for sharding.
Existing Postgres-first infra → pgvector (makes DevOps happy, albeit with higher latency).

Decision prompts (use this checklist as a mini decision tree):

Do you need production grade SLAs this week? → Pinecone.
Do you have compliance/data-residency constraints? → Weaviate self-hosted or Qdrant OSS.
Is metadata filtering mandatory for retrieval quality? → Qdrant or Weaviate (hybrid search).
Are you still experimenting with embeddings/context budgets? → Chroma or pgvector until requirements stabilize.
Is latency the primary KPI because you orchestrate multiple agents in parallel? → Milvus or Pinecone with dedicated pods; pair with Redis cache to bypass vector lookup for hot data.

Recommended pairings by use case

Prototyping & education: Chroma + local Redis cache. Minimal infra, matches notebook exercises so students can reproduce results offline.
Pilot deployments / enterprise PoCs: Weaviate (managed) + Qdrant fallback. Use hybrid search to mix keyword filters with semantics.
Full production (multi-team): Pinecone + LangGraph or AgentOps tracing, optionally replicate to Milvus for on-prem failover.
Hybrid multi-agent orchestration: Milvus (semantic) + pgvector (transactional) + Redis (working memory) to cover semantic, structured, and ephemeral tiers without overloading a single system.

 Token Cost Math

Scenario. You run a Bhagavad Gita tutoring agent. Each turn averages 180 tokens (user + assistant combined) because answers cite scripture. Students ask 30 follow-up questions in a single sitting.

Calculate the total input tokens if you naively resend the entire transcript each turn.
Apply FIFO trimming with a 6-turn window—what’s the new token count?
Instead of trimming, you roll a summarizer every 5 turns that compresses those turns by 60%. How many tokens now?
Combine both strategies: keep the last 4 raw turns plus a rolling summary of older turns (60% compression). What is the blended token cost and approximate USD spend if your model charges $0.03 per 1K input tokens (roughly GPT-4 8K pricing from the Compass ROI example)?

Solution.

Naive: tokens per request grow linearly (180, 360, …, 5400). Using the sum of the first 30 integers: 180 * Σ₁³⁰ i = 83,700 tokens, or $2.51 at $0.03 / 1K tokens.
FIFO window (size 6): once the buffer fills, each request ships 6 × 180 = 1080 tokens. Total = 180 * Σ₁⁶ i + 24 × 1080 = 29,700 tokens, or $0.89 (≈65% savings).
Rolling summaries (60% reduction): every 5 turns become a 360-token summary. Total context per request oscillates between 540 and 1,260 tokens; summing all 30 turns yields 43,200 tokens → $1.30. Savings are smaller because summaries persist alongside raw turns.
Hybrid (4 live turns + 60% compressed archive): after the fourth turn, every older turn is compressed to 40% of its size. Total tokens processed ≈ 45,792 → $1.37. Despite not beating FIFO here, the hybrid approach preserves decades of context with predictable cost; if you tighten the live window or compress harder (20% retention), the savings approach the Compass $4.80 benchmark.

Pattern Selection

Match each scenario to MemoryBank, A-MEM, or Search-o1. Explain your rationale and any trade-offs.

Article content


Trade-off discussion.

MemoryBank optimizes for personalization but adds storage/maintenance overhead → best for user-facing assistants.
A-MEM excels when knowledge must remain explorable via backlinks; however, embeddings and linking logic add latency, so pair with asynchronous indexing.
Search-o1 burns extra tokens (search + condensation) but dramatically improves reasoning quality on fresh data—reserve it for high-value analytical work and monitor costs in the notebook metrics dashboard.

