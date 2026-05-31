# ADR-0001: Regulated data must not flow through hosted managed-agent paths

**Status:** Accepted  
**Date:** 2026-05-31

## Context

The Rollenmodell (docs/Rollenmodell.md) routing rules include:

> **Rule 4 — Medical / legal / patent / high-risk reasoning:**  
> Opus/GPT + RAG → DeepSeek 32B as local skeptical second opinion

Claude Managed Agents (and other hosted frontier providers) store session transcripts and files server-side. As documented in the Claude Managed Agents overview, these services are **not eligible for Zero Data Retention (ZDR) or HIPAA BAA coverage**.

A codex adversarial review (2026-05-31) flagged that the routing rules, as written, permit an implementer to route medical, legal, patent, or similarly regulated data to hosted providers (Opus, GPT, Codex, Claude Managed Agents) while following the docs exactly — there is no hard exclusion in the routing doc itself.

## Decision

**Regulated domains must always route to local providers.** Specifically:

1. **Medical data** (patient records, clinical notes, lab results, diagnoses, treatment plans) → local-only path: DeepSeek 32B + local RAG (Qdrant + bge-m3).
2. **Legal data** (contracts, case files, privileged correspondence, patent filings, court submissions) → local-only path: DeepSeek 32B + local RAG.
3. **Any data subject to data residency regulation** (GDPR restricted transfers, HIPAA PHI, attorney-client privilege) → local-only path.

"Local-only path" means:
- No calls to Anthropic API, OpenAI API, or any other hosted model API.
- No sessions launched via Claude Managed Agents.
- Embeddings via local bge-m3 + Qdrant only — no hosted embedding APIs.

The Qwen3.6 27B local model may be used as a draft/synthesis model alongside DeepSeek 32B for regulated tasks.

## Updated routing rule 4

```
4. Medical / legal / patent / high-risk regulated reasoning
→ LOCAL ONLY — no hosted API calls permitted
   Primary:  DeepSeek-R1-Distill-Qwen-32B (local skeptic / deep reasoning)
   Synthesis: Qwen3.6 27B (local draft)
   RAG:       Qdrant + BAAI/bge-m3 (local)
   Hosted Opus/GPT: BLOCKED for this path
   Claude Managed Agents: BLOCKED for this path
```

## Consequences

- **LiteLLM router** must enforce this as a policy check (`domain_risk: regulated` → reject hosted providers) before model selection. The routing diagram in Rollenmodell.md (`Policy Check → sensitivity → domain`) must treat `regulated` as a hard block on hosted paths, not a soft preference.
- **Legal Research Agent** and **Medical Research Agent** concrete configs (Rollenmodell.md) must be updated to remove `Default: Opus/GPT + RAG` and replace with `Default: DeepSeek 32B + local RAG`.
- Architecture reviews touching the routing layer must reference this ADR and not re-suggest routing regulated data to hosted providers.
- If a future compliant hosted provider achieves ZDR + HIPAA BAA certification and is configured in the stack, a new ADR may supersede this one for that specific provider. Do not assume any hosted provider is compliant without an explicit ADR entry.

## Non-goals

This ADR does not restrict general coding or architecture work from using Opus/GPT. It applies only to data that is regulated by law or professional privilege — not merely "sensitive" or "internal."
