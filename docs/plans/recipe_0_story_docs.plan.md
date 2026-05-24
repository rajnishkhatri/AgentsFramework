---
name: Recipe 0 Story Docs
overview: Create a story-narrated Recipe 0 documentation at `docs/recipes/gcp/00_adapters.md` using a mentor/teaching style that walks the reader through why each GCP adapter exists, what problem it solves, and how the composition root switches between local-dev and cloud at runtime.
todos:
  - id: create-recipe-dir
    content: Create docs/recipes/gcp/ directory
    status: done
  - id: write-00-adapters
    content: Write docs/recipes/gcp/00_adapters.md as mentor-style story narrative covering all 5 adapters + composition switch
    status: done
  - id: verify-links
    content: Verify all code file references in the doc point to actual files that exist
    status: done
isProject: false
---

# Recipe 0 Story Documentation

## Approach

Write [`docs/recipes/gcp/00_adapters.md`](../recipes/gcp/00_adapters.md) as a **mentor-style narrative** — a senior engineer explaining the "why" behind each adapter to a mentee preparing for their first GCP deployment. The narrative uses Socratic questions to motivate each adapter, then shows the concrete code.

## Structure

The document follows the standard recipe convention (Goal, Prerequisites, Agent Steps, Verify, etc.) but wraps each section in a teaching story:

1. **Opening story hook** — "Your agent works on your laptop. Now imagine it needs to survive a container restart..."
2. **The five adapters as five lessons**, each following the pattern:
   - A Socratic question that reveals the problem
   - A brief GCP concept introduction (1-2 sentences)
   - The adapter code walkthrough with a real-world analogy
   - A "why not X?" sidebar addressing common alternatives
3. **The composition switch** — explained as a "feature flag for your infrastructure"
4. **Verification section** — told as "prove it to yourself" exercises
5. **Rollback / cost** — quick, factual

## Five Adapter Lessons (narrative arc)

| Lesson | Adapter File | Socratic Hook | GCP Concept |
|--------|-------------|---------------|-------------|
| 1 | `postgres_saver.py` | "What happens when your container scales to zero and restarts with a fresh filesystem?" | Cloud SQL = managed Postgres (like RDS) |
| 2 | `gcs_sink.py` | "Where do your trust traces go if `/tmp` vanishes?" | GCS = object storage (like S3 buckets) |
| 3 | `pubsub_sink.py` | "What if trace volume grows to 10 GB/mo and direct writes become a bottleneck?" | Pub/Sub = message queue (like SQS/SNS) |
| 4 | `agent_facts_gcs_registry.py` | "How does your agent know who it is when it wakes up in the cloud?" | Signed identity cards stored in GCS |
| 5 | `gcp_identity.py` | "But who tells the agent which identity card to load?" | Workload Identity = automatic SA-to-app binding |

## Key Files Referenced

- [`services/trace_sinks/gcs_sink.py`](../../services/trace_sinks/gcs_sink.py)
- [`services/trace_sinks/pubsub_sink.py`](../../services/trace_sinks/pubsub_sink.py)
- [`services/governance/agent_facts_gcs_registry.py`](../../services/governance/agent_facts_gcs_registry.py)
- [`services/cloud_providers/gcp_identity.py`](../../services/cloud_providers/gcp_identity.py)
- [`agent_ui_adapter/adapters/runtime/postgres_saver.py`](../../agent_ui_adapter/adapters/runtime/postgres_saver.py)
- [`middleware/__main__.py`](../../middleware/__main__.py) (composition root switch)
- [`pyproject.toml`](../../pyproject.toml) (`[gcp]` optional extra)

## Deliverable

`docs/recipes/gcp/00_adapters.md` — completed 2026-05-22
