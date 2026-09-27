# Fresh Worker

Fresh Worker is a small isolation tool for LLM workflows.

It gives a model one bounded task in a **brand-new conversation/session with no parent chat history**, then returns the worker's answer to the calling agent. The goal is simple: when a task benefits from an independent second look, the worker should not inherit the assumptions, mistakes, momentum, or clutter of the main conversation.

This repository contains two harness-specific implementations:

- **Pi** — a native Pi extension that starts a completely new Pi agent session using the current model and thinking level, with tools disabled.
- **Open WebUI** — a Workspace Tool that creates a separate saved Open WebUI chat, sends one prompt to a configured worker model, waits for completion, and returns the result.

They implement the same pattern, but they are intentionally not forced into one universal abstraction. Each version uses the native mechanisms of its host.

## Why use a Fresh Worker?

Long-running agent sessions accumulate context. That is often useful, but it can also create problems:

- an early assumption can keep influencing later reasoning;
- a model may anchor on its own previous answer;
- irrelevant history consumes context;
- a reviewer may simply agree with the work it has already seen;
- a small local model can become less reliable as the conversation grows;
- independent verification is difficult if the "reviewer" shares the same conversation.

Fresh Worker creates a clean boundary.

The parent decides exactly what the worker receives. The worker sees **only the bounded prompt supplied to it**.

## Typical use cases

Fresh Worker is useful for:

- **Independent review** — ask a clean worker to critique a design, patch, plan, calculation, or explanation.
- **Second-opinion reasoning** — compare the parent agent's answer with a worker that has not seen the parent's chain of conversation.
- **Small/local models** — keep delegated tasks short and focused so limited context is spent on the current problem rather than conversation history.
- **Agentic development** — hand off one well-defined coding, diagnostic, or research subtask.
- **Verification gates** — ask a worker to check whether an artifact satisfies a short list of acceptance criteria.
- **Prompt testing** — run the same self-contained prompt from a clean state.
- **Context decontamination** — test whether a conclusion survives without prior framing.
- **Parallel workflow design** — use fresh contexts as independent bounded workers in larger orchestration systems.

## What it is not

Fresh Worker is not:

- a replacement for a full multi-agent framework;
- a shared-memory agent;
- a recursive autonomous swarm;
- a way to give the worker hidden access to the parent conversation;
- proof that an answer is correct simply because an independent worker produced it.

It is deliberately small: **one fresh context, one bounded prompt, one returned result**.

## The isolation contract

The important property is not merely "start another model call". It is **context isolation**.

### Pi

The Pi implementation:

1. creates a new saved Pi session;
2. reuses the parent session's active model;
3. reuses the parent session's thinking level;
4. copies no parent messages;
5. disables all tools in the worker;
6. sends exactly one supplied prompt;
7. returns the final assistant text and worker-session metadata;
8. disposes the live worker session when finished.

See [pi/README.md](pi/README.md).

### Open WebUI

The Open WebUI implementation:

1. creates a new saved Open WebUI chat;
2. uses the worker model configured in its Valves;
3. sends exactly one supplied prompt;
4. explicitly disables optional WebUI features for the worker request;
5. polls the server-side task until completion;
6. retrieves and validates the saved chat;
7. returns the assistant response and chat ID;
8. can optionally save the retrieved chat JSON as evidence.

See [open-webui/README.md](open-webui/README.md).

## Which version should I use?

| Host | Use |
| --- | --- |
| Pi coding agent | [`pi/fresh-worker.ts`](pi/fresh-worker.ts) |
| Open WebUI | [`open-webui/fresh_worker.py`](open-webui/fresh_worker.py) |

If you use another agent harness, the pattern is easy to port: create a genuinely new session, do not copy parent history, pass only the bounded prompt, and return the result.

## A good Fresh Worker prompt

A Fresh Worker cannot infer omitted context from the parent chat. That is a feature.

Write the prompt as a self-contained job:

```text
Review the following function for correctness.

Check:
1. off-by-one errors;
2. empty-input behaviour;
3. integer overflow;
4. whether the stated invariant is actually maintained.

Return:
- PASS or FAIL for each check;
- a short explanation;
- a corrected function only if required.

<function>
...
</function>
```

Avoid prompts such as:

```text
Check what we just discussed and tell me if it is right.
```

The worker has not seen "what we just discussed".

## Design principles

Fresh Worker follows a few intentionally conservative rules:

- **Bounded input** — the parent must provide the complete job.
- **No inherited conversation** — isolation is the point.
- **No hidden recursive delegation** — the published worker does not receive tools.
- **Explicit completion** — the caller waits for the worker result.
- **Inspectable evidence** — both implementations expose identifiers for the fresh session/chat.
- **Host-native implementation** — each harness uses its own session primitives instead of pretending all hosts behave identically.

## Security and privacy

Read the implementation before installing it.

For Pi, the worker uses the same configured model/provider as the parent, so prompts are sent wherever that model normally runs.

For Open WebUI, the Workspace Tool executes Python on the Open WebUI server and uses an API key to call the same instance. Open WebUI itself warns that Workspace Tools execute arbitrary Python code on the server, so only trusted code should be installed.

Never put secrets into a worker prompt unless you are comfortable sending them to the configured model/provider.

See [SECURITY.md](SECURITY.md).

## Compatibility

The implementations were extracted from working project code and cleaned for public reuse.

Agent and WebUI APIs evolve. If a host changes its session or chat API, Fresh Worker may need a small compatibility update. Version-specific compatibility notes belong in the implementation README files.

## Repository layout

```text
Fresh-Worker/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
├── examples/
│   └── prompt-patterns.md
├── pi/
│   ├── README.md
│   └── fresh-worker.ts
└── open-webui/
    ├── README.md
    └── fresh_worker.py
```

## Status

**0.1.0 — initial public release**

The core Fresh Worker behaviour has been used in real local-model development workflows. This repository packages the reusable parts and removes project-specific verification helpers and paths.

## Licence

MIT. See [LICENSE](LICENSE).

## Contributions

Bug reports, compatibility fixes, documentation improvements, and ports to other agent harnesses are welcome. Please keep the core isolation contract intact: a "Fresh Worker" should actually be fresh.
