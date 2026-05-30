# **ÆLLI Architecture Vision v1**

## **Core Philosophy**

ÆLLI is not designed as a chatbot.

ÆLLI is designed as a continuously learning research, reasoning, and execution system that separates:

1. Operational Memory  
2. Knowledge Memory  
3. Experience Memory  
4. Reasoning  
5. Agent Execution

Each layer has a clearly defined responsibility.

---

# **Design Principles**

## **Principle 1: Truth stays at the source**

ÆLLI never becomes the source of truth.

The source systems remain:

* GitHub  
* Jira  
* Confluence  
* CRM  
* ERP  
* E-Mail  
* Legal Databases  
* Medical Databases

ÆLLI only builds context and understanding around them.

---

## **Principle 2: Different memories solve different problems**

Not all memory is the same.

### **Operational Memory**

"I know exactly what should be stored."

### **Knowledge Memory**

"I want to find information."

### **Experience Memory**

"I want to understand why something happened."

---

## **Layer 1: Operational Memory**

### **Technology**

* LiteLLM Memory API  
* PostgreSQL

### **Purpose**

Stores structured and deterministic information.

### **Examples**

```
user:janis:preferences

agent:aelli:system_state

team:gfe:playbook

project:integrahub:config

agent:aelli:a2a_registry_notes

agent:aelli:available_skills

project:integrahub:roadmap_status
```

### **Characteristics**

* deterministic  
* auditable  
* versionable  
* low latency  
* operational state

---

## **Layer 2: Knowledge Memory**

### **Technology**

* Qdrant  
* BGE-M3 Embeddings

### **Purpose**

Stores searchable knowledge.

### **Collections**

```
github

pubmed

eurlex

openjur

confluence

jira

contracts

patents

integrahub_docs

pdfs
```

### **Example Sources**

* GitHub Repositories  
* PubMed  
* EUR-Lex  
* OpenJur  
* Confluence  
* Jira  
* Patents  
* Internal Documentation  
* Contracts  
* PDFs

### **Characteristics**

* semantic retrieval  
* RAG  
* source citations  
* knowledge discovery

---

## **Layer 3: Experience Memory**

### **Technology**

* MemPalace

### **Purpose**

Stores experiences instead of facts.

### **Examples**

* E-Mail Threads  
* Customer Conversations  
* User Conversations  
* Agent Diaries  
* Decision Histories  
* Meeting Notes  
* Lessons Learned  
* Sprint Retrospectives

### **Questions MemPalace Answers**

```
Why was decision X made?

When did scope creep begin?

What did customer Y originally request?

What alternatives were considered?

Why was technology A chosen over B?
```

### **Characteristics**

* episodic memory  
* historical context  
* organizational learning  
* decision reconstruction

---

# **Agent Diaries**

Agent Diaries are one of the most important long-term features.

## **Working Memory**

Stores:

* active tasks  
* current session context  
* temporary reasoning  
* short-lived plans

TTL:

Hours to Days

---

## **Long-Term Memory**

Stores:

* successful strategies  
* failed approaches  
* lessons learned  
* important discoveries  
* recurring patterns

This memory is preserved.

---

# **Reflection Layer**

MemPalace is not the final destination.

It is the archive.

A dedicated Reflection Agent continuously analyzes historical experiences.

Workflow:

```
Experience
↓
MemPalace
↓
Reflection Agent
↓
Pattern Extraction
↓
Playbooks
↓
Operational Knowledge
```

Example:

After 20 projects ÆLLI discovers:

"Requirement ambiguity caused most project failures."

Result:

```
Requirement Discovery Playbook
```

This becomes part of organizational knowledge.

---

# **Reasoning Layer**

### **Technology**

* DeepSeek

Current preferred architecture:

```
DeepSeek-R1-0528-Qwen3-8B
```

Role:

Agent Controller

Responsibilities:

* routing  
* orchestration  
* planning  
* tool use  
* A2A coordination

---

### **Deep Thinking Engine**

```
DeepSeek-R1-Distill-Qwen-32B
```

Role:

Research and reasoning engine

Responsibilities:

* legal analysis  
* medical reasoning  
* architecture decisions  
* patent research  
* root cause analysis  
* deep investigations

---

# **Agent Network**

### **Technology**

* A2A  
* LiteLLM

Responsibilities:

* Agent Discovery  
* Agent Communication  
* Agent Routing  
* Capability Registry

Examples

```
Medical Agent

Legal Agent

Patent Agent

Research Agent

IntegraHub Agent

Lead Generation Agent
```

---

# **Runtime Layer**

### **Apple Silicon**

* M4 Max  
* MLX  
* mlx-lm

Reasons:

* native Apple optimization  
* low overhead  
* excellent memory efficiency

---

# **Interface Layer**

Primary Interface:

```
CLI
```

Examples:

```shell
aelli ask "Can IntegraLeads use Reverse DNS for B2B prospecting?"

aelli ask "Latest evidence for IL-17 inhibitors in axial spondyloarthritis"

aelli ask "Find similar patents to this architecture"
```

Secondary Interfaces:

* Codex CLI  
* Claude Code  
* Internal APIs

No heavy web-based interface required.

---

# **Knowledge Domains**

## **Medical**

Sources:

* PubMed  
* ClinicalTrials  
* Guidelines

Agent:

Medical Research Agent

---

## **Legal**

Sources:

* EUR-Lex  
* OpenJur  
* Contracts  
* Regulatory Documents

Agent:

Legal Research Agent

---

## **Patents**

Sources:

* Espacenet  
* Google Patents  
* IPC

Agent:

Patent Research Agent

---

## **Engineering**

Sources:

* GitHub  
* Jira  
* Confluence

Agent:

Engineering Knowledge Agent

---

# **Final Architecture**

```
                    CLI
                     │
                     ▼

                  LiteLLM

                     │

      ┌──────────────┼──────────────┐

      ▼              ▼              ▼

 Memory API      A2A Network   Model Routing

      │

      ▼

   PostgreSQL

      │

      ▼

Operational Memory

      │

      ▼

────────────────────────────────────

Knowledge Memory

      │

      ▼

    Qdrant

      │

      ▼

GitHub
PubMed
EUR-Lex
OpenJur
Confluence
Jira
Patents
PDFs

────────────────────────────────────

Experience Memory

      │

      ▼

   MemPalace

      │

      ▼

E-Mails
Meetings
Customer History
Agent Diaries
Decision History

────────────────────────────────────

Reasoning Layer

      │

      ▼

DeepSeek 8B
(Agent Controller)

      │

      ▼

DeepSeek 32B
(Deep Thinking Engine)
```

## **Summary**

ÆLLI is designed around a simple principle:

```
Configuration?
→ LiteLLM Memory

Knowledge?
→ Qdrant

Experience?
→ MemPalace

Reasoning?
→ DeepSeek

Execution?
→ A2A Agents

Truth?
→ Source Systems
```

The objective is not to build a better chatbot.

The objective is to build an AI-native organizational intelligence system that accumulates knowledge, preserves experience, learns from history, and continuously improves over time.

