# **Octowiz Engineering Runtime Plan v1**

## **1\. Zweck dieses Plans**

Dieser Plan beschreibt die Umsetzung von **Octowiz** als Engineering- und Coding-Tentacle innerhalb der bestehenden **ÆLLI Architecture Vision v1**.

Die übergeordnete ÆLLI-Architektur definiert bereits:

* Operational Memory  
* Knowledge Memory  
* Experience Memory  
* Reasoning  
* Agent Execution  
* Agent Diaries  
* Reflection Layer  
* A2A Agent Network  
* CLI als Primary Interface  
* Truth-at-source-Prinzip

Dieser Plan beschreibt nicht erneut die gesamte ÆLLI-Architektur.

Er konkretisiert, wie der Bereich **Softwareentwicklung / Coding / Engineering Execution** durch Octowiz umgesetzt wird.

---

## **2\. Produktdefinition**

**Octowiz ist ÆLLIs Coding-Alter-Ego.**

Octowiz ist kein einzelnes Claude-Code-Plugin und kein isolierter Coding-Agent.

Octowiz ist ein memory-backed, A2A-verbundenes Engineering-System, das Coding-Arbeit plant, beobachtet, bewertet, ausführt, reviewt, dokumentiert und bei strategischen Entscheidungen an ÆLLI eskaliert.

Kurzform:

```
Octowiz connects coding agents, memory, skills and execution environments into one supervised engineering workflow.
```

Deutsch:

```
Octowiz verbindet Coding-Agenten, Memory, Skills und Ausführungsumgebungen zu einem überwachten Engineering-Workflow.
```

---

## **3\. Position in der ÆLLI-Architektur**

Octowiz ist der **Engineering / Coding Agent** im A2A-Agent-Network von ÆLLI.

```
A2A Agent Network

├── Medical Research Agent
├── Legal Research Agent
├── Patent Research Agent
├── Research Agent
├── IntegraHub Agent
├── Lead Generation Agent
└── Octowiz Engineering Agent
```

ÆLLI bleibt die zentrale Orchestratorin.

Octowiz übernimmt die Coding-Domäne.

```
ÆLLI owns intent.
Octowiz owns coding orchestration.
Execution providers own runtime.
LiteLLM owns platform services.
IntegraHub Marketplace owns distribution.
Source systems remain truth.
```

---

## **4\. Zielbild**

```
AELLI
  ├── user-facing orchestration
  ├── cross-domain decisions
  └── invokes Octowiz via A2A

Octowiz
  ├── AELLI's coding alter ego
  ├── A2A Agent
  ├── Claude Code Bridge
  ├── Dev Advisor
  ├── Agent View Adapter
  ├── Sandcastle Runner
  ├── Memory Client
  ├── Knowledge Retrieval Client
  ├── Experience Diary Writer
  ├── Marketplace Skill Runtime
  ├── Policy Engine
  ├── Observability Layer
  └── Execution Provider Router

LiteLLM Platform
  ├── Model Gateway
  ├── A2A Gateway
  ├── Memory API
  └── IntegraHub Marketplace
        ├── Models
        ├── MCP Servers
        ├── Skills / Plugins
        ├── Agents
        └── Octowiz Packages

Claude Code
  ├── claude agents
  ├── background sessions
  ├── subagents
  └── local supervisor

Sandcastle
  ├── sandboxed runs
  ├── branch strategies
  ├── Docker / Podman / Vercel providers
  └── programmatic agent orchestration
```

---

## **5\. Architekturprinzipien**

## **5.1 ÆLLI bleibt oberhalb der Coding-Ausführung**

ÆLLI soll keine lokalen Claude-Code-Sessions, Worktrees, Shell-Kommandos oder Sandbox-Runs direkt verwalten.

ÆLLI entscheidet:

* Was ist die Absicht?  
* Ist es eine Coding-Aufgabe?  
* Muss Octowiz aktiviert werden?  
* Ist eine strategische Entscheidung nötig?  
* Müssen andere Tentacles eingebunden werden?  
* Muss das Ergebnis user-facing synthetisiert werden?

ÆLLI wird aktiv bei:

* Architekturentscheidungen  
* Produktentscheidungen  
* Cross-domain-Fragen  
* widersprüchlichem Memory  
* strategischen Trade-offs  
* explizitem User-Wunsch  
* hoher Unsicherheit  
* Eskalation durch Octowiz

---

## **5.2 Octowiz besitzt die Coding-Domäne**

Octowiz übernimmt:

* Coding-Aufgabenplanung  
* lokale Coding-Session-Erkennung  
* Claude Code Bridge  
* Claude Agent View Integration  
* Dev Advisor Checks  
* Skill Routing  
* Marketplace Skill Runtime  
* Execution Provider Routing  
* Memory-backed Coding Doctrine  
* Agent Diaries  
* Engineering Reflection Input  
* Risk Detection  
* Review und Handoff  
* Eskalation an ÆLLI

---

## **5.3 Truth stays at the source**

Octowiz wird nicht zur Quelle der Wahrheit.

```
Code truth
→ GitHub / Git

Ticket truth
→ Jira

Documentation truth
→ Confluence / Docs

Plugin truth
→ IntegraHub Marketplace

Operational state
→ LiteLLM Memory

Engineering knowledge
→ Qdrant

Engineering experience
→ MemPalace
```

Octowiz baut Kontext, Workflows, Empfehlungen und Entscheidungen um diese Systeme herum.

---

## **6\. Memory Mapping für Octowiz**

Octowiz folgt der bestehenden Drei-Memory-Architektur von ÆLLI.

---

## **6.1 Operational Memory**

Technologie:

```
LiteLLM Memory API
PostgreSQL
```

Octowiz nutzt Operational Memory für:

* Coding-Rollen  
* Playbooks  
* Projektregeln  
* Provider Policies  
* Skill Registry Notes  
* A2A Registry Notes  
* ADR Pointers  
* User Preferences  
* Team Preferences  
* Agent Capabilities

Beispiel-Namespaces:

```
team:{team_id}:octowiz:playbook:default
team:{team_id}:octowiz:roles:planner
team:{team_id}:octowiz:roles:implementer
team:{team_id}:octowiz:roles:reviewer
team:{team_id}:octowiz:roles:qa

project:{project_id}:octowiz:config
project:{project_id}:octowiz:rules
project:{project_id}:octowiz:adr:{date}-{slug}

agent:octowiz:available_skills
agent:octowiz:a2a_registry_notes
agent:octowiz:memory:{topic}

user:{user_id}:octowiz:preferences
```

---

## **6.2 Knowledge Memory**

Technologie:

```
Qdrant
BGE-M3 Embeddings
```

Octowiz nutzt Knowledge Memory für semantische Engineering-Recherche über:

* GitHub Repositories  
* Pull Requests  
* Issues  
* Jira Tickets  
* Confluence  
* Architektur-Dokumentation  
* Codebase Summaries  
* technische Dokumentation  
* ADRs  
* interne Engineering Notes

Fragen, die Knowledge Memory beantworten soll:

```
Wo ist dieses Feature implementiert?

Welche PR hat dieses Verhalten eingeführt?

Welches Ticket beschreibt die ursprüngliche Anforderung?

Welche Architekturentscheidung gilt hier?

Welche Dateien hängen semantisch zusammen?

Gab es diesen Fehler schon einmal?

Welche Dokumentation belegt diese Änderung?
```

---

## **6.3 Experience Memory**

Technologie:

```
MemPalace
```

Octowiz nutzt Experience Memory für Engineering-Erfahrungen:

* Coding Sessions  
* Agent Diaries  
* fehlgeschlagene Ansätze  
* erfolgreiche Strategien  
* Debugging-Verläufe  
* Review-Historien  
* Architekturdebatten  
* Entscheidungshistorien  
* Lessons Learned  
* Scope-Creep-Momente

Fragen, die Experience Memory beantworten soll:

```
Warum wurde diese Architektur gewählt?

Wann begann der Implementierungs-Drift?

Welcher Ansatz ist beim letzten Mal gescheitert?

Was haben wir aus dem Refactor gelernt?

Warum musste ein Agent gestoppt werden?

Welche wiederkehrenden Probleme bremsen Entwicklung?
```

---

## **7\. Octowiz Agent Diaries**

Jede relevante Octowiz-Session erzeugt ein **Agent Diary**.

Ein Diary ist kein vollständiges Transcript.

Es ist ein strukturierter Erfahrungsdatensatz.

---

## **7.1 Working Diary**

TTL:

```
Hours to Days
```

Speichert:

* aktive Aufgabe  
* Repo  
* Branch  
* Session ID  
* Prompt Summary  
* aktueller Plan  
* geänderte Dateien  
* genutzte Tools  
* offene Risiken  
* temporäre Entscheidungen  
* offene Fragen

---

## **7.2 Long-Term Diary**

Wird gespeichert, wenn die Session langfristig relevant ist.

Speichert:

* Entscheidungen  
* fehlgeschlagene Ansätze  
* erfolgreiche Strategien  
* wiederkehrende Muster  
* wichtige Entdeckungen  
* unerwartete Blocker  
* Review-Ergebnisse  
* finales Ergebnis  
* Lessons Learned

Beispiel:

```
Task:
Merge Dev Advisor into Octowiz.

Observed:
Endpoint compatibility was more important than internal package structure.

Failed approach:
Moving all code at once caused unclear ownership.

Successful strategy:
Keep /a2a/dev-advisor as compatibility alias while making /a2a/octowiz canonical.

Lesson:
Deprecation aliases should be planned before repo consolidation.
```

---

## **8\. Engineering Reflection Loop**

Octowiz erzeugt Experiences.

MemPalace archiviert sie.

Der Reflection Agent analysiert sie.

Wiederkehrende Muster werden zu Engineering Playbooks.

```
Coding Session
↓
Octowiz Agent Diary
↓
MemPalace
↓
Reflection Agent
↓
Pattern Extraction
↓
Engineering Playbook
↓
LiteLLM Operational Memory
```

Beispiele für resultierende Playbooks:

```
Requirement Discovery Playbook
Refactor Safety Playbook
Claude Code Worktree Playbook
Spec Deviation Prevention Playbook
PR Review Checklist
Agent Dispatch Strategy
Sandbox Run Policy
Memory Write Policy
A2A Escalation Policy
```

---

## **9\. A2A-Kommunikation**

## **9.1 ÆLLI → Octowiz**

ÆLLI ruft Octowiz per A2A auf, wenn eine Aufgabe zur Coding- oder Engineering-Domäne gehört.

Beispiel:

```json
{
  "agent": "octowiz",
  "capability": "octowiz.plan",
  "task": "Plan the migration of Dev Advisor into Octowiz.",
  "context": {
    "repo": "raelli/octowiz",
    "priority": "high",
    "requiresDecision": true
  }
}
```

---

## **9.2 Octowiz → ÆLLI**

Octowiz eskaliert an ÆLLI, wenn eine Aufgabe über reine Coding-Ausführung hinausgeht.

Beispiel:

```json
{
  "agent": "aelli",
  "capability": "aelli.decide",
  "reason": "architecture_decision_required",
  "question": "Should Dev Advisor be merged into Octowiz or remain separate?",
  "recommendation": "Merge into Octowiz and keep /a2a/dev-advisor as compatibility alias."
}
```

---

## **9.3 Octowiz A2A Capabilities**

Canonical endpoint:

```
/a2a/octowiz
```

Compatibility endpoint:

```
/a2a/dev-advisor
```

Capabilities:

```
octowiz.observe
octowiz.advise
octowiz.plan
octowiz.review
octowiz.dispatch
octowiz.manage_agents
octowiz.run_sandboxed
octowiz.load_memory
octowiz.write_diary
octowiz.escalate_to_aelli
```

---

## **10\. Invocation Policy**

Octowiz entscheidet in vier Stufen:

```
observe
→ Event speichern, keine Reaktion

advise
→ Hinweis an Coding-Session zurückgeben

intervene
→ Warnung, Vorschlag oder Checkpoint erzwingen

escalate
→ ÆLLI per A2A aufrufen
```

ÆLLI wird invoked, wenn:

* der User explizit ÆLLI anspricht  
* Octowiz strategische Unsicherheit erkennt  
* Architekturentscheidungen nötig sind  
* Produktentscheidungen nötig sind  
* mehrere Agents oder Domänen koordiniert werden müssen  
* Projekt-Memory der aktuellen Arbeit widerspricht  
* ein hohes Risiko erkannt wird  
* Octowiz nicht ausreichend sicher entscheiden kann

ÆLLI wird nicht invoked für:

* jeden File Edit  
* jeden Prompt  
* jeden Testlauf  
* jeden Git-Status  
* Routine-Warnungen  
* Low-risk Observations

---

## **11\. Event-Modell**

Alle Bridges und Provider nutzen ein gemeinsames Event-Modell.

```ts
type OctowizEvent =
  | SessionStarted
  | SessionStopped
  | PromptSubmitted
  | ToolUsed
  | FileChanged
  | GitStateChanged
  | TestFinished
  | ReviewReady
  | InputRequired
  | AgentRunStarted
  | AgentRunFinished
  | RiskDetected;
```

Beispiel: Prompt Event

```json
{
  "type": "prompt.submitted",
  "sessionId": "cc-123",
  "repo": "raelli/octowiz",
  "branch": "feat/octowiz-advisor",
  "prompt": "Merge the Dev Advisor into Octowiz.",
  "git": {
    "modifiedFiles": [
      "packages/advisor/index.ts",
      "apps/a2a-agent/server.ts"
    ]
  }
}
```

Beispiel: Risk Event

```json
{
  "type": "risk.detected",
  "sessionId": "cc-123",
  "risk": "spec_deviation",
  "severity": "medium",
  "message": "The session modified payment files while the prompt described auth changes.",
  "recommendedAction": "advise"
}
```

---

## **12\. Execution Provider Router**

Octowiz nutzt verschiedene Execution Provider, ohne dass ÆLLI deren Details kennen muss.

Provider:

```
claude-agent-view
sandcastle
shell
cline
vscode
```

Routing-Logik:

```
Human-guided local task
→ Claude Agent View

Parallel local tasks
→ Claude Agent View

Risky refactor
→ Sandcastle

CI-like batch review
→ Sandcastle

Simple test command
→ Shell Provider

IDE-attached workflow
→ VS Code / Cline Adapter

Strategic decision
→ ÆLLI
```

Provider Interface:

```ts
interface CodingExecutionProvider {
  listSessions?(): Promise<CodingSession[]>;
  dispatch(task: CodingTask): Promise<CodingRun>;
  getStatus(runId: string): Promise<CodingRunStatus>;
  getLogs(runId: string): Promise<string>;
  reply?(runId: string, message: string): Promise<void>;
  stop(runId: string): Promise<void>;
}
```

---

## **13\. Kernkomponenten**

## **13.1 Octowiz Bridge**

Die Bridge verbindet IDEs, CLIs und lokale Coding-Tools mit Octowiz.

Erste Ausprägung:

```
aelli-cc-plugin
→ Octowiz Bridge
```

Aufgaben:

* Claude-Code-Hooks beobachten  
* Session-Kontext lesen  
* Git-Kontext lesen  
* File Changes normalisieren  
* Events an Octowiz senden  
* Advice zurück in Claude Code injizieren

---

## **13.2 Octowiz Advisor**

Der bisherige Dev Advisor wird als Capability in Octowiz integriert.

Aufgaben:

* File Conflict Detection  
* Branch Drift Detection  
* Spec Deviation Detection  
* Risk Scoring  
* Advice Generation  
* Escalation Decision

---

## **13.3 Claude Agent View Provider**

Der Agent View Provider verbindet Octowiz mit Claude Code Agent View.

Funktionen:

* Sessions auflisten  
* Status auslesen  
* Logs abrufen  
* Background-Sessions starten  
* Sessions stoppen  
* Sessions respawnen  
* Sessions entfernen  
* Ready-for-review erkennen  
* Needs-input eskalieren  
* Status an ÆLLI verdichten

CLI-Basis:

```
claude agents --json
claude --bg
claude attach <id>
claude logs <id>
claude stop <id>
claude respawn <id>
claude rm <id>
```

---

## **13.4 Sandcastle Provider**

Sandcastle wird als zusätzlicher Execution Provider in Octowiz eingebunden.

Einsatzfälle:

* isolierte Agent-Runs  
* riskante Refactorings  
* parallele Implementierungsversuche  
* Vergleich mehrerer Lösungsansätze  
* CI-nahe Agentenläufe  
* branch-basierte Experimente

Sandcastle gehört nicht in ÆLLI Core.

---

## **13.5 Marketplace Skill Runtime**

Octowiz nutzt Skills und Plugins aus dem IntegraHub Marketplace.

Skill-Kategorien:

* Planning  
* PRD  
* TDD  
* Implementation  
* Review  
* QA  
* Handoff  
* Worktree  
* Migration  
* Setup  
* Verification

Marketplace-Artefakte:

```
octowiz-agent
octowiz-bridge
octowiz-advisor
octowiz-skills
octowiz-mcps
octowiz-provider-claude-agent-view
octowiz-provider-sandcastle
```

---

## **14\. Security, Permissions & Human-in-the-loop**

Octowiz darf nicht jede Aktion automatisch ausführen.

Eine Policy Engine entscheidet:

```
Can observe?
Can advise?
Can intervene?
Can dispatch?
Can modify files?
Can run shell?
Can use sandbox?
Can write memory?
Must escalate to ÆLLI?
Must ask user?
```

Automatisch erlaubt:

* Events beobachten  
* Status lesen  
* Git-Kontext lesen  
* Memory lesen  
* Low-risk Advice geben  
* strukturierte Summaries erzeugen

Nur mit expliziter Freigabe:

* neue Agent-Sessions starten  
* Shell-Kommandos ausführen  
* Dateien ändern lassen  
* Worktrees löschen  
* Sandcastle Runs mit Merge-Potenzial starten  
* Memory dauerhaft überschreiben  
* Marketplace Plugins installieren  
* MCPs aktivieren  
* riskante Permission Modes nutzen

Nie automatisch:

* Secrets anzeigen oder speichern  
* produktive Deployments auslösen  
* irreversible Löschaktionen durchführen  
* externe Systeme ohne Scope prüfen oder verändern  
* unreviewed Sandbox-Ergebnisse mergen

---

## **15\. Observability & Audit**

Octowiz benötigt eine eigene Observability-Schicht.

Zu protokollieren:

* gestartete Sessions  
* Provider-Auswahl  
* A2A Calls  
* Memory Reads  
* Memory Writes  
* Skill-Versionen  
* Marketplace Dependencies  
* MCP-Nutzung  
* Eskalationsgründe  
* Advisor-Warnungen  
* Risk Scores  
* Kosten / Tokens  
* Laufzeiten  
* Fehlerzustände  
* User-Freigaben  
* finale Entscheidungen

Zielstruktur:

```
packages/observability/
  run-log
  audit-log
  cost-log
  decision-trace
  provider-health
```

---

## **16\. Marketplace Lifecycle**

Der IntegraHub Marketplace ist Teil der LiteLLM-Plattformschicht.

Er verteilt:

* Models  
* MCP Servers  
* Skills  
* Plugins  
* Agents  
* Octowiz Packages  
* Execution Provider Integrationen

Lifecycle:

```
publish
install
update
pin version
verify signature
compatibility check
disable
rollback
trust level
dependency graph
```

Octowiz konsumiert Marketplace-Artefakte.

Octowiz besitzt den Marketplace nicht.

---

## **17\. Repository-Konsolidierung**

Aktuelle Komponenten:

```
aelli
octowiz
aelli-cc-plugin
LiteLLM config
A2A agent config
IntegraHub Marketplace
Memory API
plugins / skills
```

Zielbenennung:

```
aelli
→ ÆLLI core and orchestration

octowiz
→ engineering / coding agent

aelli-cc-plugin
→ Octowiz Bridge

dev-advisor
→ Octowiz Advisor Capability
```

Zielstruktur:

```
octowiz/

  apps/
    a2a-agent/
    claude-code-bridge/
    vscode-extension/

  packages/
    advisor/
    agent-control/
    execution/
    events/
    git-context/
    memory-client/
    knowledge-client/
    experience-client/
    marketplace-client/
    observability/
    policy/
    types/

  providers/
    claude-agent-view/
    sandcastle/
    shell/
    cline/

  skills/
    octowiz-plan/
    octowiz-prd/
    octowiz-tdd/
    octowiz-review/
    octowiz-handoff/
    octowiz-setup/
    octowiz-run-sandboxed/

  docs/
    architecture.md
    product-narrative.md
    a2a-contract.md
    memory-contract.md
    event-schema.md
    migration.md
```

Migration Principle:

```
Hybrid first.
Monorepo later if useful.
Compatibility aliases before breaking changes.
```

---

## **18\. Phasenplan**

## **Phase 0: SSOT und Architektur-Freeze**

Ziel:

Das Gesamtbild wird in der SSOT-Dokumentation festgeschrieben.

Deliverables:

* Octowiz als Engineering Agent im A2A Network  
* Zielarchitektur  
* Rollenmodell  
* A2A-Kommunikationsmodell  
* Memory-Mapping  
* Marketplace-Abgrenzung  
* Repo-Konsolidierungsstrategie

Akzeptanzkriterien:

* ÆLLI, Octowiz, LiteLLM, Marketplace und Execution Provider sind eindeutig abgegrenzt.  
* `aelli-cc-plugin` ist offiziell als Octowiz Bridge eingeordnet.  
* Dev Advisor ist offiziell als Octowiz Advisor Capability eingeordnet.

---

## **Phase 1: Naming und Produktnarrativ**

Ziel:

Ein konsistentes Produktnarrativ wird eingeführt.

Festlegungen:

```
Produktname:
Octowiz

Positionierung:
AELLI's coding alter ego

Claude Code Adapter:
Octowiz Bridge

A2A Agent:
Octowiz Agent

Risk Capability:
Octowiz Advisor

Execution Layer:
Octowiz Execution Providers
```

Deliverables:

* README-Update  
* Produktbeschreibung  
* Architekturdiagramm  
* Komponenten-Glossar  
* Migration Note für alte Namen

Akzeptanzkriterien:

* Keine neue Dokumentation verwendet `aelli-cc-plugin` als Produktnamen.  
* Dev Advisor wird nicht mehr als eigenständiges Produkt beschrieben.  
* Octowiz ist als Coding-Tentacle von ÆLLI beschrieben.

---

## **Phase 2: A2A Contract und Agent Card**

Ziel:

Octowiz wird als eigenständiger A2A-Agent verfügbar.

Deliverables:

* Octowiz Agent Card  
* `/a2a/octowiz` Endpoint  
* Compatibility Alias für `/a2a/dev-advisor`  
* Capability-Liste  
* Request-/Response-Schemas  
* Auth-Konzept

Akzeptanzkriterien:

* ÆLLI kann Octowiz per A2A aufrufen.  
* Octowiz kann bei Bedarf an ÆLLI eskalieren.  
* Der alte Dev-Advisor-Endpoint funktioniert weiterhin als Alias.

---

## **Phase 3: Memory Integration**

Ziel:

Octowiz nutzt LiteLLM Memory als Operational Memory.

Deliverables:

* Memory Client Package  
* Namespace-Konventionen  
* Role Bundle Loader  
* Project Rules Loader  
* Playbook Loader  
* ADR Writer  
* Agent Memory Writer

Akzeptanzkriterien:

* Octowiz kann Playbooks per Namespace laden.  
* Octowiz kann Entscheidungen als ADR speichern.  
* User-, Team- und Project-Scopes sind getrennt.  
* Memory-Zugriffe werden auditierbar dokumentiert.

---

## **Phase 4: Knowledge und Experience Integration**

Ziel:

Octowiz wird an Knowledge Memory und Experience Memory angebunden.

Deliverables:

* Knowledge Client für Engineering Retrieval  
* Experience Client für MemPalace  
* Octowiz Agent Diary Schema  
* Working Diary Writer  
* Long-Term Diary Writer  
* Reflection-ready export format

Akzeptanzkriterien:

* Octowiz kann Engineering-Kontext aus Knowledge Memory abrufen.  
* Octowiz kann Coding-Erfahrungen als Diary speichern.  
* Diaries können vom Reflection Agent verarbeitet werden.

---

## **Phase 5: Octowiz Bridge Konsolidierung**

Ziel:

Das bisherige `aelli-cc-plugin` wird als Octowiz Bridge integriert.

Deliverables:

* Bridge-Code in `octowiz/apps/claude-code-bridge`  
* Event Normalizer  
* Git Context Reader  
* Session ID Handling  
* Hook Adapter  
* Advice Injection  
* Backward-compatible package wrapper

Akzeptanzkriterien:

* Claude Code Events werden an Octowiz gesendet.  
* Octowiz kann synchron Advice zurückgeben.  
* Existing Setup bricht nicht.  
* Alte Paketnamen werden mit Deprecation-Hinweis unterstützt.

---

## **Phase 6: Dev Advisor Merge**

Ziel:

Der Dev Advisor wird als Octowiz Advisor Capability integriert.

Deliverables:

* `packages/advisor`  
* Rule Engine  
* File Conflict Detection  
* Branch Drift Detection  
* Spec Deviation Detection  
* Risk Scoring  
* Escalation Policy

Akzeptanzkriterien:

* Advisor läuft innerhalb von Octowiz.  
* Risiken werden als strukturierte Events ausgegeben.  
* Advisor kann zwischen observe, advise, intervene und escalate unterscheiden.  
* ÆLLI wird nur bei strategischen oder unsicheren Fällen aufgerufen.

---

## **Phase 7: Claude Agent View Provider**

Ziel:

Octowiz kann Claude Code Agent View als lokalen Execution Provider nutzen.

Deliverables:

* `providers/claude-agent-view`  
* Session Listing via JSON  
* Dispatch  
* Logs  
* Stop  
* Respawn  
* Remove  
* Status Mapping  
* Ready-for-review Detection  
* Needs-input Escalation

Akzeptanzkriterien:

* Octowiz kann lokale Claude-Code-Background-Sessions auslesen.  
* Octowiz kann neue Sessions starten.  
* Octowiz erkennt Sessions mit Input-Bedarf.  
* Octowiz kann Status an ÆLLI verdichten.

---

## **Phase 8: Sandcastle Provider**

Ziel:

Octowiz kann isolierte Coding-Runs programmatisch starten.

Deliverables:

* `providers/sandcastle`  
* Sandbox Policy  
* Branch Strategy Adapter  
* Commit Result Parser  
* Run Comparison  
* Failure Handling  
* Security Notes

Akzeptanzkriterien:

* Octowiz kann Sandcastle als Provider wählen.  
* Runs sind isoliert.  
* Ergebnisse können zusammengeführt oder verworfen werden.  
* ÆLLI bekommt nur verdichtete Entscheidungen und Resultate.

---

## **Phase 9: Marketplace Integration**

Ziel:

Octowiz nutzt den IntegraHub Marketplace zur Distribution von Skills, Plugins, MCPs und Provider-Dependencies.

Deliverables:

* Marketplace Manifest für Octowiz  
* Skill Dependency Resolver  
* MCP Dependency Resolver  
* Plugin Install Flow  
* Version Compatibility Checks  
* Skill Discovery  
* Lifecycle Handling

Akzeptanzkriterien:

* Octowiz kann benötigte Skills aus dem Marketplace laden.  
* Dependencies sind versioniert.  
* Installation ist reproduzierbar.  
* Marketplace ist nicht im Octowiz-Core hardcoded.

---

## **Phase 10: VS Code / Cline Adapter**

Ziel:

Octowiz wird nicht nur über Claude Code, sondern auch über VS Code und Cline nutzbar.

Deliverables:

* VS Code Extension Konzept  
* Cline Adapter Konzept  
* MCP Tool Interface  
* Workspace Event Adapter  
* Git/File Watcher Fallback

Akzeptanzkriterien:

* Octowiz kann auch ohne Claude-Code-Hooks relevante Workspace-Events erhalten.  
* Cline kann Octowiz-Tools nutzen.  
* ÆLLI bleibt über Octowiz erreichbar.

---

## **Phase 11: End-to-End Workflows**

Ziel:

Die Architektur wird durch echte Coding-Workflows validiert.

Referenz-Workflows:

```
Workflow 1: Architekturentscheidung

User fragt ÆLLI
→ ÆLLI ruft Octowiz
→ Octowiz analysiert Repo + Memory
→ Octowiz eskaliert Entscheidung
→ ÆLLI entscheidet
→ Octowiz schreibt ADR
→ Octowiz schreibt Diary
```

```
Workflow 2: Parallel Review

User startet Review
→ Octowiz dispatcht Agent View Sessions
→ Sessions prüfen unterschiedliche Bereiche
→ Octowiz sammelt Resultate
→ ÆLLI erhält Summary
→ Octowiz speichert Lessons Learned
```

```
Workflow 3: Risky Refactor

User will Refactor
→ Octowiz wählt Sandcastle
→ Sandbox Run erstellt Branch
→ Tests laufen
→ Ergebnis wird geprüft
→ Merge oder Verwerfen
→ Diary wird gespeichert
```

```
Workflow 4: Live Coding Guardrails

Claude Code Session startet
→ Bridge meldet Session
→ User Prompt wird gesendet
→ File Changes entstehen
→ Advisor erkennt Drift
→ Octowiz warnt
→ bei Wiederholung entsteht Reflection-Signal
```

Akzeptanzkriterien:

* Alle Workflows laufen von Ende zu Ende.  
* ÆLLI wird nur bei passenden Fällen aktiv.  
* Octowiz kann lokale Coding-Risiken eigenständig behandeln.  
* Memory, Knowledge, Experience und Marketplace werden produktiv genutzt.

---

## **19\. Roadmap**

## **Milestone 1: Architecture SSOT**

Ziel:

Dokumentation und Naming finalisieren.

Umfang:

* Architekturabschnitt schreiben  
* Rollenmodell finalisieren  
* Zielstruktur festlegen  
* alte Namen mappen

---

## **Milestone 2: Octowiz A2A MVP**

Ziel:

Octowiz als A2A-Agent verfügbar machen.

Umfang:

* Agent Card  
* `/a2a/octowiz`  
* `/a2a/dev-advisor` Alias  
* erste Capabilities

---

## **Milestone 3: Memory-backed Octowiz**

Ziel:

Octowiz lädt Rollenwissen und Projektregeln aus LiteLLM Memory.

Umfang:

* Memory Client  
* Namespace Loader  
* Role Bundles  
* Project Rules  
* ADR Writer

---

## **Milestone 4: Bridge Integration**

Ziel:

Claude Code Events laufen stabil in Octowiz ein.

Umfang:

* Bridge Migration  
* Event Normalizer  
* Advice Injection  
* Git Context

---

## **Milestone 5: Advisor Merge**

Ziel:

Dev Advisor ist Teil von Octowiz.

Umfang:

* Rules Engine  
* Risk Events  
* Escalation Policy  
* Tests

---

## **Milestone 6: Agent Execution**

Ziel:

Octowiz kann lokale und isolierte Agentenläufe steuern.

Umfang:

* Claude Agent View Provider  
* Sandcastle Provider  
* Execution Router  
* Status Summary

---

## **Milestone 7: Experience Loop**

Ziel:

Octowiz schreibt Diaries und erzeugt Reflection-ready Erfahrungen.

Umfang:

* Diary Schema  
* Working Diary  
* Long-Term Diary  
* MemPalace Export  
* Reflection Input

---

## **Milestone 8: Marketplace Distribution**

Ziel:

Octowiz ist über IntegraHub Marketplace installierbar.

Umfang:

* Manifest  
* Skills  
* Dependencies  
* MCPs  
* Provider Packages  
* Lifecycle

---

## **Milestone 9: IDE Expansion**

Ziel:

VS Code und Cline werden angebunden.

Umfang:

* VS Code Extension  
* Cline/MCP Adapter  
* File Watcher Fallback

---

## **20\. Definition of Done für Octowiz v1**

Octowiz v1 ist fertig, wenn:

* ÆLLI Octowiz per A2A aufrufen kann.  
* Octowiz eine Agent Card besitzt.  
* Claude Code Events über Octowiz Bridge eingehen.  
* Dev Advisor Checks in Octowiz laufen.  
* LiteLLM Memory für Rollenwissen und Projektregeln genutzt wird.  
* Engineering Knowledge Memory abgefragt werden kann.  
* Octowiz Agent Diaries geschrieben werden können.  
* Octowiz mindestens einen Marketplace Skill nutzen kann.  
* Claude Agent View Sessions gelesen und gestartet werden können.  
* Octowiz Risiken lokal behandeln kann.  
* Strategische Fälle an ÆLLI eskaliert werden.  
* Eine Entscheidung als ADR in Memory gespeichert werden kann.  
* Eine Coding-Erfahrung als Diary in Experience Memory landet.  
* Die Architektur in der SSOT-Dokumentation beschrieben ist.

---

## **21\. Kurzfassung für die SSOT**

Octowiz ist ÆLLIs Engineering Agent und Coding-Alter-Ego.

Es implementiert die Engineering Execution Layer der ÆLLI Architecture Vision.

Octowiz verbindet Claude Code, lokale Agent View Sessions, Sandcastle, LiteLLM A2A, LiteLLM Memory, Knowledge Memory, Experience Memory und IntegraHub Marketplace Skills zu einem überwachten agentischen Entwicklungsworkflow.

ÆLLI bleibt die übergeordnete Orchestratorin und trifft strategische Entscheidungen.

Octowiz übernimmt die Coding-Domäne:

* Session-Beobachtung  
* Agent-Steuerung  
* Skill-Routing  
* Memory-Nutzung  
* Knowledge Retrieval  
* Experience Diaries  
* Review  
* Advisor-Regeln  
* Execution Provider Routing

Die bisher getrennten Bestandteile `aelli-cc-plugin` und Dev Advisor werden fachlich in Octowiz konsolidiert.

`aelli-cc-plugin` wird zur Octowiz Bridge.

Der Dev Advisor wird zur Octowiz Advisor Capability.

Octowiz kommuniziert mit ÆLLI über A2A und nutzt LiteLLM als Plattformschicht für Model Gateway, A2A Gateway, Memory API und IntegraHub Marketplace.

Das Ziel ist ein modularer Coding-Tentacle, der lokal-interaktive Claude-Code-Workflows, Agent View Sessions, isolierte Sandbox-Runs und spätere VS-Code-/Cline-Workflows steuern kann, ohne ÆLLI mit technischen Ausführungsdetails zu überladen.

```
ÆLLI orchestrates.
Octowiz engineers.
LiteLLM operates.
Qdrant knows.
MemPalace remembers.
Reflection improves.
Source systems remain truth.
```

