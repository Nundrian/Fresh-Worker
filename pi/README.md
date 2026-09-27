# Fresh Worker for Pi

This is the Pi coding-agent implementation of Fresh Worker.

It registers one tool:

```text
fresh_worker
```

The tool runs a single, self-contained prompt in a brand-new Pi session.

## Behaviour

When Pi calls `fresh_worker`, the extension:

1. validates that the parent has an active model;
2. creates a new persistent Pi session;
3. reuses the parent's active model;
4. reuses the parent's current thinking level;
5. copies **no parent conversation messages**;
6. disables **all tools** in the child;
7. sends the supplied prompt;
8. returns the final assistant text;
9. includes the worker session ID/file in tool details;
10. disposes the live session object.

The worker cannot call Fresh Worker again because no tools are exposed in the child session.

## Install

Pi discovers extensions from its extension directories. For a user-wide installation, copy:

```text
fresh-worker.ts
```

to:

```text
~/.pi/agent/extensions/fresh-worker.ts
```

For a project-local installation, place it in the project's Pi extension directory:

```text
.pi/extensions/fresh-worker.ts
```

Restart/reload Pi if necessary.

Pi's current SDK documentation describes extension discovery from `~/.pi/agent/extensions/` and `.pi/extensions/`.

## Use

Enable the tool in the parent Pi session and give the parent a task where an independent clean-context worker is helpful.

A parent-agent instruction might be:

```text
Use fresh_worker to independently review this proposed fix.
Give the worker all code and acceptance criteria it needs.
Then compare its findings with your own.
```

The actual tool input has one field:

```json
{
  "prompt": "A complete self-contained task for the worker"
}
```

## Important: the worker knows nothing about the parent chat

This is intentional.

Bad worker prompt:

```text
Check the solution we discussed above.
```

Good worker prompt:

```text
Review this TypeScript function for race conditions.

Requirements:
- only one writer may enter the critical section;
- cancellation must release the lock;
- return PASS/FAIL with reasons.

Code:
...
```

## Model and thinking level

The Pi version inherits the active parent model and thinking level. That makes it useful when you want an independent context without silently changing the underlying model configuration.

If you want a deliberately different reviewer model, that is a different orchestration policy and is not part of this minimal extension.

## Persistence

The implementation uses `SessionManager.create(cwd)`, so each worker is saved as its own Pi session. This makes the isolation inspectable.

If you prefer ephemeral workers, changing the implementation to `SessionManager.inMemory(...)` is straightforward, but that is not the default because saved worker sessions are useful evidence during development and debugging.

## Tools

The child uses:

```ts
noTools: "all"
```

This is deliberate. A Fresh Worker is a bounded reasoning/review worker, not an autonomous nested agent.

## Cancellation

The parent cancellation signal is wired to `session.abort()`. Cancelling the tool cancels the worker.

## Compatibility

This file was extracted from a working Pi extension and cleaned of project-specific test code.

Pi evolves quickly. If the SDK changes the `createAgentSession`, `SessionManager`, extension, or tool-selection APIs, an adaptation may be required. Please open an issue with your Pi version and error message.

## Upstream documentation

Pi SDK:
https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sdk.md
