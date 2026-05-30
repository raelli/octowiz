**Premium Frontier Models für High-Stakes Output.**  
 **Lokale Modelle für Privacy, Speed, Offline, Pre-Reasoning, Zweitmeinung und Kostenkontrolle.**

## **Rollenmodell**

| Rolle | Primärmodell | Fallback / lokal | Zweck |
| ----- | ----- | ----- | ----- |
| **ÆLLI Core / Executive Reasoning** | Opus / GPT | Qwen3.6 27B | Strategie, Architektur, Entscheidungen |
| **Octowiz Coding** | Codex / Opus / GPT | Qwen3.6 27B | Code, Refactoring, Repo-Analyse |
| **Local Operator** | DeepSeek-R1-0528-Qwen3-8B | — | schnelles Routing, Tool Calls, einfache Tasks |
| **Deep Local Reasoner** | DeepSeek-R1-Distill-Qwen-32B | Qwen3.6 27B | Zweitmeinung, Medizin, Legal, Root Cause |
| **Agentic Local Reasoner** | Qwen3.6 27B | DeepSeek 32B | Coding, Tool Use, Long Context, RAG |
| **Retrieval Embeddings** | BAAI/bge-m3 | — | Qdrant Search über Repos, PubMed, EUR-Lex etc. |

## **Routing-Regeln**

```
1. Simple task / local command / classification
→ DeepSeek 8B

2. Coding, repo reasoning, tool-heavy workflow
→ Codex first
→ Qwen3.6 27B local fallback / privacy mode

3. Strategic architecture, product, business, complex synthesis
→ Opus or GPT
→ Qwen3.6 27B as local draft/second pass

4. Medical / legal / patent / high-risk reasoning
→ Opus/GPT + RAG
→ DeepSeek 32B as local skeptical second opinion

5. Private/internal documents
→ local-first:
  Qwen3.6 27B or DeepSeek 32B
  + Qdrant
  + bge-m3

6. Low-cost batch work
→ DeepSeek 8B / Qwen3.6 27B

7. Final external-facing answer
→ Opus/GPT if quality matters
→ local only if privacy/offline/cost dominates
```

## **Praktisches Agent-Routing**

```
User Request
   ↓
LiteLLM Router
   ↓
Policy Check:
- sensitivity
- difficulty
- domain
- cost
- latency
- privacy
   ↓
Model Selection
```

## **Konkrete Agent-Rollen**

```
ÆLLI
- Default: Opus/GPT
- Local Shadow: Qwen3.6 27B
- Skeptic: DeepSeek 32B
- Operator: DeepSeek 8B
```

```
Octowiz
- Default: Codex
- Architecture Review: Opus/GPT
- Local Repo Mode: Qwen3.6 27B
- Debug Skeptic: DeepSeek 32B
```

```
Legal Research Agent
- Default: Opus/GPT + EUR-Lex/OpenJur RAG
- Local Second Opinion: DeepSeek 32B
- Fast Retrieval Summaries: Qwen3.6 27B
```

```
Medical Research Agent
- Default: Opus/GPT + PubMed RAG
- Differential Diagnosis Skeptic: DeepSeek 32B
- Fast Abstract Triage: DeepSeek 8B
```

```
Repo Agent
- Default: Codex
- Local fallback: Qwen3.6 27B
- Embeddings: BAAI/bge-m3
- Vector Store: Qdrant
```

## **Finaler Stack als Routing-System**

```
Frontend:
- CLI
- Codex CLI
- Claude Code
- ÆLLI CLI

Gateway:
- LiteLLM

Memory:
- LiteLLM Memory API + Postgres

Knowledge:
- Qdrant + BAAI/bge-m3

Experience:
- MemPalace

Local Runtime:
- mlx-lm

Local Models:
- DeepSeek-R1-0528-Qwen3-8B-MLX-4bit
- DeepSeek-R1-Distill-Qwen-32B-4bit
- Qwen3.6-27B-OptiQ-4bit

Cloud / Frontier:
- Opus
- GPT / ChatGPT
- Codex

Routing Logic:
- privacy
- cost
- latency
- task difficulty
- domain risk
- required output quality
```

Kurz gesagt:

**Opus/GPT/Codex sind die Elite-Operatoren.**  
 **Qwen ist dein lokaler Engineer.**  
 **DeepSeek 32B ist dein lokaler Skeptiker.**  
 **DeepSeek 8B ist dein Dispatcher.**  
 **bge-m3 \+ Qdrant sind das Gedächtnis für Wissen.**  
 **MemPalace ist das Gedächtnis für Geschichte.**

