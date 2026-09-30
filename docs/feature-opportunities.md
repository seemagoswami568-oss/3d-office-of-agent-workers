# Product Feature Opportunities

Research notes for additions to Agent Office, based on the repository as inspected on 2026-09-30 and official product documentation checked the same day. This is a product/engineering roadmap, not a claim that every feature should be built. Competitor references are used for established patterns and user value, not as a request to copy a product wholesale.

## Current Product Shape

Agent Office is already more than a 3D shell around terminals. It has multiple agent providers; persistent shared PTYs and scrollback; worktree-isolated worker branches; per-project floors; an ordered task queue; provider/model selection; GitHub issues and pull requests; services discovery; meetings with several bounded collaboration patterns; MCP and CLI control; real-time chat, presence, voice and screen sharing; custom JSON maps; and machine, usage and waiting-worker indicators.

That changes what is worth adding. A second basic queue, another chat panel, a generic agent picker, or an unbounded multi-agent chat would duplicate working product. The strongest opportunities close gaps between those capabilities: make human intervention clearer, compose tasks over time, safely expose results, make execution more reproducible and isolated, and let teams adapt the space without editing JSON by hand.

Relevant implementation boundaries include [the shared protocol](../src/shared/protocol.ts), [the server queue](../src/server/queue.ts), [worker/provider lifecycle](../src/server/workers.ts), [worktree creation](../src/server/worktrees.ts), [meetings](../src/server/meetings.ts), [service discovery UI](../src/client/ui/services.ts), [map schema](../src/shared/maps/types.ts), [map validation and planning](../src/shared/maps/index.ts), and [settings](../src/client/ui/settings.ts).

## Priority Summary

| Rank | Addition | User outcome | Impact | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| 1 | Isolated worker execution profiles | Reduce cross-worker and cross-account exposure | Very high | Large | P0 |
| 2 | Actionable approvals and questions inbox | Unblock workers without hunting through desks and terminals | High | Medium-large | P0 |
| 3 | Dependency-aware task workflows | Turn ordered tasks and meetings into durable end-to-end work | High | Large | P1 |
| 4 | Secure in-office service previews | Review a worker's running UI without leaving the office | High | Medium-large | P1 |
| 5 | Repository environment profiles and warm starts | Reduce setup time and make tasks reproducible | High | Medium-large | P1 |
| 6 | Inbound event and schedule automations | Start bounded office work from GitHub events or a schedule | High | Large | P1 |
| 7 | Visual custom-map editor | Let teams arrange their workspace without editing JSON | Medium | Medium | P2 |
| 8 | Focus-aware presence and notification policy | Make interruptions intentional in a shared office | Medium | Small-medium | P2 |
| 9 | Durable worker-run timeline | Explain what happened across restarts, workers and PRs | Medium | Medium | P2 |

Effort is relative to this repository and assumes tests, docs and operational constraints are included. The priorities are recommendations, not a committed release plan.

## 1. Isolated Worker Execution Profiles

**Why it matters.** The current security notes explicitly warn that all workers run as the same operating-system user and that one person's worker can read another person's folder. Per-account provider sign-ins improve attribution and plan separation, but they are not a filesystem security boundary. This is the most important platform risk to address before adding more unattended automations or broader multi-user access.

**Comparable pattern.** OpenHands' official Agent Canvas describes local, remote and cloud agent backends, including Docker and VM execution. Its README explicitly warns that running without a sandbox gives the agent full access to the installation machine. The useful lesson is not “require Docker”; it is “make the execution boundary explicit and selectable.”

**Repo fit.** Provider launch and PTY ownership are concentrated in [workers.ts](../src/server/workers.ts), while each worker already has a known project/worktree path in [the protocol](../src/shared/protocol.ts) and worktree manager. That gives a concrete unit to isolate: one worker process, its PTY, and only its assigned workspace.

**Suggested first slice.** Add an execution-backend interface with the existing host process as the compatibility backend and an opt-in container backend. Mount only the worker's worktree/workspace, keep office state and other workers' directories out of the container, pass only that worker's required provider credentials, and make network access a documented policy. Show the selected isolation mode on the worker card and in the hire dialog. Do not imply that a container protects secrets that are deliberately mounted into it.

**Acceptance checks.** A worker can read/write its own worktree and use its configured provider; it cannot read another worker's worktree, account sign-ins, or the office's `.agent-office/` state; terminal reconnect and resume work after office restart; container cleanup preserves the configured worktree lifecycle; host mode remains backward compatible. Add tests for path mounts, secret environment filtering, and failure cleanup.

**Risks and design decisions.** Containers can complicate nested tools, GPU use, SSH/GitHub credentials, service-port discovery and persistent PTYs. Start with an explicit opt-in and a supported runtime matrix. Keep network allow/deny policy separate from filesystem isolation, and document that a shared OS account remains a weaker boundary in host mode.

## 2. Actionable Approvals and Questions Inbox

**Why it matters.** The office already reports `needs_input`, records waiting time, shows waiting workers, and supports provider-specific approval/question events. The remaining gap is that the human often has to find the worker, open its terminal and interpret a provider-specific screen before acting. A single inbox could make the existing status substantially more useful on desktop and mobile.

**Comparable pattern.** Gather's product page emphasizes seeing whether teammates are free, focused or in meetings and joining nearby conversations quickly. GitHub's cloud-agent flow emphasizes steering a session, reviewing a branch diff and iterating before creating a PR. Both reinforce that a shared space should expose the next useful human action, not only activity.

**Repo fit.** `WorkerInfo.status` and `waitingSince` already identify pending work in [protocol.ts](../src/shared/protocol.ts). Provider adapters in [workers.ts](../src/server/workers.ts), [opencode.ts](../src/server/opencode.ts), [codex.ts](../src/server/codex.ts), [muse.ts](../src/server/muse.ts) and [dsh.ts](../src/server/dsh.ts) detect waiting events, but the shared worker record does not define one normalized, user-facing request object. The existing workers panel and notifications provide natural entry points.

**Suggested first slice.** Add a normalized pending-request summary with kind (`permission`, `question`, `login/setup`, `unknown`), safe display text, timestamp and supported response choices. Put a waiting inbox in the Workers panel/top bar, ordered by oldest request, with one-tap navigation to the terminal. Add inline approve/reject/answer buttons only for providers whose public adapter protocol can safely submit that exact response. For all other providers, open the terminal at the waiting worker and leave the request untouched.

**Acceptance checks.** A request appears once, disappears when resolved or the worker resumes, survives reconnect by being reconstructed from current provider state where possible, and does not expose raw secrets or full command output. Provider-specific response tests prove the answer reaches only the intended session. Unknown requests remain terminal-only. No automatic approval is introduced.

**Risks and design decisions.** Providers report different schemas and lifecycle events; terminal text parsing is fragile. Start with structured events and explicit capability flags instead of pretending every provider can be answered the same way. Keep full command arguments redacted by default and preserve the current safe behavior when request data is incomplete.

## 3. Dependency-Aware Task Workflows

**Why it matters.** The task queue is persistent and correctly seats independent tasks in order, while the meeting room supports bounded debate, lead/team, map-reduce and review patterns. What is missing is a durable way to express “A must finish before B,” fan out a list of work, and then run a final integration/review task. A workflow would join two mature features instead of replacing either.

**Comparable pattern.** OpenHands Agent Canvas describes automations that can decompose GitHub issues into tasks and connect to services such as Slack, GitHub and Linear. GitHub cloud agent centers work around a branch that can be reviewed and iterated into a pull request. These patterns suggest preserving traceable task units and reviewable outcomes while making the orchestration durable.

**Repo fit.** `QueueTask` currently has `queued | running | done` and no dependency or workflow identifiers in [protocol.ts](../src/shared/protocol.ts); [queue.ts](../src/server/queue.ts) pumps tasks independently and persists `queue.json`. Existing meetings already handle bounded fan-out/fan-in, so a workflow should compose queue tasks and meetings rather than invent a free-form agent swarm.

**Suggested first slice.** Add a `Workflow` record containing named stages, task ids, `dependsOn`, status, creator and creation time. A stage becomes runnable only when all prerequisites succeed. Begin with sequential pipelines and fan-out/fan-in over explicit task lists; let a workflow stage optionally invoke an existing meeting pattern. Display a compact workflow row with blocked/running/failed/done states and links to each worker, terminal and PR.

**Acceptance checks.** Reject cycles, missing task ids and cross-floor dependencies unless explicitly supported. A prerequisite failure blocks descendants with a clear reason; retry only resumes eligible descendants; restart preserves the dependency graph; deleting a queued task handles dependent stages predictably. Tests should cover concurrent workers, retry, cancellation and restart.

**Risks and design decisions.** A workflow can become a second queue UI or a hidden programming language. Keep the first model small, use existing queue capacity/worker limits, make failure policy visible, and avoid implicit “merge automatically” behavior. A workflow can end in a PR-ready state without merging it.

## 4. Secure In-Office Service Previews

**Why it matters.** The services board already detects worker-started web servers and provides an SSH tunnel or Tailscale URL. That is useful but breaks the review loop: the teammate must copy a command, leave the office, and possibly configure a tunnel before inspecting a branch preview.

**Comparable pattern.** GitHub cloud-agent sessions are reviewed through their branch and pull-request workflow; Gather promotes joining collaboration in a click. The opportunity here is to make review similarly immediate without weakening Agent Office's existing service access boundary.

**Repo fit.** Discovery and ownership are already in [server/services.ts](../src/server/services.ts) and [the services UI](../src/client/ui/services.ts). The server has an authenticated relay for service tunnels, including WebSockets, documented in [how-it-works.md](how-it-works.md). A preview can build on that ownership mapping, but the current localhost relay should not be treated as safe to embed under the office's authenticated origin.

**Suggested first slice.** Add an explicit **Preview** action for HTTP services. Serve previews from a separate origin or a carefully sandboxed, session-scoped route with a restrictive CSP, no office cookies forwarded to the worker server, and an explicit per-service opt-in for frames/scripts. Keep **Open** and tunnel-copy behavior as fallbacks. Add branch, worker, port and “preview may be untrusted” context around the frame.

**Acceptance checks.** HMR and WebSocket previews work; a preview cannot read the office DOM, cookies, or API session; stopping a service invalidates the preview; untrusted response headers cannot escape the sandbox; only services owned by a worker and visible to the signed-in user are available. Add an end-to-end browser test for a small local preview server.

**Risks and design decisions.** A reverse proxy can introduce same-origin script risks, cookie confusion, SSRF and Host-header problems. A sandboxed iframe on a distinct origin is preferable to simply embedding the current relay. The implementation needs a deliberate origin and CSP design before UI work.

## 5. Repository Environment Profiles and Warm Starts

**Why it matters.** Worktrees already give tasks clean, isolated branches, but a fresh task may still need dependency installation, code generation, service setup or repository-specific test preparation. Repeating those steps increases time-to-first-result and can make two workers see different environments.

**Comparable pattern.** GitHub Codespaces documents prebuild configurations for preparing a repository environment before a user starts a codespace. OpenHands describes persisted workspaces and multiple execution backends. Together these show the value of repeatable setup plus persisted caches, while keeping the task checkout itself isolated.

**Repo fit.** New worktrees start in [worktrees.ts](../src/server/worktrees.ts); provider process setup lives in [workers.ts](../src/server/workers.ts); worker/provider selection is already configurable. There is no first-class repo setup profile in the worker lifecycle today.

**Suggested first slice.** Support an opt-in, project-local environment manifest with a versioned setup command, readiness check and optional cleanup command. Run it once per cache key derived from manifest, lockfiles and runtime versions, outside the worker's source branch when safe; then mount or reuse only dependency caches while retaining a fresh worktree. Show setup progress and failure separately from agent status. Start with documented npm/pnpm/yarn, Python and .NET examples rather than a generic installer marketplace.

**Acceptance checks.** A new worktree still starts from the latest fetched base; setup runs once for an unchanged cache key and reruns when a dependency manifest changes; setup failure is visible and does not mark the agent task successful; cache cleanup never removes project files; concurrent tasks do not corrupt a shared cache.

**Risks and design decisions.** Setup commands execute project code and should be treated as untrusted. Make the feature opt-in per project, run under the worker's isolation policy, cap output/time/disk, and do not silently inherit office credentials. Measure median time from task seating to first agent tool call before and after enabling it.

## 6. Inbound Event and Schedule Automations

**Why it matters.** The current Slack/Discord webhook is outbound: it tells a channel that a worker needs input or has finished. The queue can accept tasks from board agents and the authenticated office API, but it does not provide a first-class recurring rule or an authenticated inbound event workflow. This could make the office useful for routine maintenance without requiring someone to remember to start each task.

**Comparable pattern.** OpenHands Agent Canvas advertises scheduled automations and webhook-triggered runs, including integrations with GitHub, Slack and Linear. This is a strong reference for event-driven work, but Agent Office should keep its existing explicit queue and visible worker limits as the safety rail.

**Repo fit.** Outbound behavior lives in [webhook.ts](../src/server/webhook.ts); queue state and admission limits live in [queue.ts](../src/server/queue.ts); GitHub issue/PR events and task insertion are handled through the existing server and floor APIs. This suggests a narrow trigger-to-queue layer rather than a new worker runner.

**Suggested first slice.** Add named automation rules with a trigger (cron or a supported GitHub event), filters, a fixed prompt template, provider/model choice, enabled state and last-run/next-run metadata. An event only enqueues a task; it never directly runs shell commands or merges PRs. Include a dry-run preview and a per-rule daily cap. Start with scheduled repo health checks and GitHub issue-label-to-queue rules.

**Acceptance checks.** Authenticate webhook signatures, reject stale/replayed deliveries, deduplicate by provider delivery id, cap payload size, and persist rule state across restart. Test time zones and daylight-saving transitions for schedules. Disabled rules enqueue nothing; repeated delivery enqueues once; the queue's worker and budget caps still apply.

**Risks and design decisions.** Inbound endpoints expand the attack surface and can create runaway cost. Avoid arbitrary user-provided URLs, arbitrary shell steps and automatic merges in v1. Require HTTPS and secret rotation, provide a delivery log, and keep every resulting task visible in the ordinary queue with the rule that created it.

## 7. Visual Custom-Map Editor

**Why it matters.** Custom maps are already a real extension point, but teams must edit JSON and understand table/seat geometry, board locations, props, rotations and validity constraints. A visual editor would turn an existing power-user feature into an approachable customization path.

**Comparable pattern.** WorkAdventure's official documentation foregrounds building a virtual world, managing users and permissions, and extending worlds with custom scripts. Agent Office already supports custom data-driven maps, so the highest-fit step is a safe visual editor rather than a general scripting system.

**Repo fit.** The schema lives in [maps/types.ts](../src/shared/maps/types.ts), validation and seat planning in [maps/index.ts](../src/shared/maps/index.ts), the user workflow in [docs/maps.md](maps.md), and selection in [settings.ts](../src/client/ui/settings.ts). Important constraint: `MAP_STYLES` currently contains only `castle`; a config can rearrange that supported style but cannot create an arbitrary new renderer or alter the office's built-in style.

**Suggested first slice.** Add a local editor for a copy of the castle map: draggable tables, stations, boards and props; seat-count overlays; zoom/pan; a preview using the existing builder; validation errors from `planMap`; and import/export to JSON. Keep the editor local to the person editing until they deliberately save/select the map for the building. Do not add arbitrary scripts in this feature.

**Acceptance checks.** Every editor save round-trips through `planMap`; invalid placement gives a clear field-level error; seat identities and counts stay valid; edits do not alter the active building until confirmed; export produces JSON accepted by the existing loader and tests.

**Risks and design decisions.** A 2D top-down editor is much cheaper and more usable than live 3D object manipulation for the current schema. Begin with data the schema already represents; do not imply support for custom geometry, arbitrary collision shapes or a new style builder.

## 8. Focus-Aware Presence and Notification Policy

**Why it matters.** The office already shows where teammates are and what they have open, supports proximity-based voice volume, push-to-talk, notifications, and “needs input” indicators. A clearer “available / focused / in a meeting” state would help people coordinate before interrupting, especially when several floors and many agents create constant status changes.

**Comparable pattern.** Gather explicitly surfaces whether a person is free, focused or in a meeting, supports waving someone over, and emphasizes nearby conversations. Its meetings and chat are also offered alongside the spatial office. These are useful presence patterns because they communicate interruptibility, not just location.

**Repo fit.** Peer presence is broadcast through `PeerInfo` and the WebSocket protocol in [protocol.ts](../src/shared/protocol.ts); user settings are stored in [state.ts](../src/client/state.ts) and the settings UI; the office already sends worker notifications via browser notifications and Slack/Discord webhooks. A user-level status can therefore be added without changing agent worker statuses.

**Suggested first slice.** Add a manually chosen presence state (`available`, `focused`, `in a meeting`, `away`) with an optional expiry, visible in the people list and above the character. Add per-state notification policy for non-urgent events; keep worker-needs-input alerts prominent unless the user explicitly configures otherwise. A simple “wave/request attention” action can enqueue a small in-office prompt without automatically opening voice.

**Acceptance checks.** Presence expires or returns to available on schedule, persists only as long as intended, works across reconnects/devices if user identity is present, and does not leak private calendar data. Notification preferences apply consistently across browser and configured webhooks. Add accessible text labels; do not rely on color alone.

**Risks and design decisions.** Presence can become surveillance if inferred too aggressively. Make status explicit, transparent and reversible; do not infer focus from keystrokes or monitor activity. Keep urgent agent requests distinct from teammate availability.

## 9. Durable Worker-Run Timeline

**Why it matters.** The office persists terminal scrollback and chat, and the queue stores current and finished tasks, but reconstructing a task's lifecycle across worker restart, provider events, worktree recovery, commits, PR creation and human approvals still requires searching separate surfaces. A concise run timeline would make failures and handoffs explainable.

**Comparable pattern.** GitHub cloud agent emphasizes reviewing and iterating on branch diffs; OpenHands Agent Canvas presents conversations and automations as persistent units of work with workspace/history state. Both reinforce that agent work should be inspectable after execution, not only while its terminal is open.

**Repo fit.** Queue task lifecycle is in [queue.ts](../src/server/queue.ts), scrollback and chat persistence in [history.ts](../src/server/history.ts), worker statuses/actions in [workers.ts](../src/server/workers.ts), and PR/worktree metadata in the shared protocol. The office already has the raw signals; the missing piece is a common append-only event record and view.

**Suggested first slice.** Record a bounded, append-only event stream keyed by task/worker: queued, seated, provider started, waiting, resumed, terminal exit, worktree/branch changes, PR opened, task finished/failed, and human action. Store timestamps, actor, event type and links/IDs, not raw terminal output or prompts by default. Add a timeline tab to the queue task detail and worker panel, with search by task, branch and PR.

**Acceptance checks.** Events survive restart and are ordered under clock skew; duplicate provider events are idempotent; pruning follows a documented retention policy; search can locate a PR/task relationship; secrets and terminal content do not enter the event log accidentally. Test migration from existing queue files with no event history.

**Risks and design decisions.** This overlaps with chat/scrollback/search if it stores content rather than facts. Keep it an event index, not a second transcript. Define retention and multi-user visibility before adding audit claims; do not describe it as compliance-grade auditing unless it has tamper resistance and the necessary controls.

## Suggested Sequence

1. **Security foundation:** define the execution-backend contract and ship opt-in per-worker isolation. Keep the current host backend available and clearly labeled.
2. **Human control:** normalize waiting requests and deliver a reliable inbox. This reduces stuck work without granting agents more authority.
3. **Visible results:** ship safe service previews so reviewers can inspect generated interfaces in context.
4. **Composition:** add dependency-aware workflows, using the queue for durable tasks and meetings for bounded collaboration.
5. **Operational leverage:** add environment profiles and inbound automations only after isolation, deduplication and resource caps are in place.
6. **Customization and team habits:** add the map editor, explicit presence, and a durable run timeline as focused improvements.

## Research Sources

Primary pages were checked on 2026-09-30. Product pages change; confirm current plans, API limits and capabilities before committing to an implementation.

- [Gather product features](https://www.gather.town/features): virtual-office presence (free/focused/in meetings), nearby conversations, meetings, chat and collaboration features.
- [WorkAdventure documentation](https://docs.workadventu.re/): map building, world/user management, permissions and custom scripts.
- [GitHub Copilot cloud agent documentation](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent): repository research, implementation plans, branch-based work, review, iteration and pull requests.
- [GitHub Codespaces prebuilds](https://docs.github.com/en/codespaces/prebuilding-your-codespaces): repository-defined prepared development environments.
- [OpenHands Agent Canvas repository](https://github.com/All-Hands-AI/OpenHands): self-hosted coding-agent control center, multiple agent backends, scheduled/webhook automations and integrations; its README distinguishes Docker execution from running unsandboxed on the host.

---

These recommendations are intentionally shaped around the current system. The most valuable next steps are not “more agents”; they are stronger isolation, faster human response, durable task composition and a secure review loop.