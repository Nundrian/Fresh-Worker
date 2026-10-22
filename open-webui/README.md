# Fresh Worker for Open WebUI

This is the Open WebUI Workspace Tool implementation of Fresh Worker.

It creates a separate saved Open WebUI chat, runs one bounded prompt in that chat, waits for the server-side generation to finish, validates the saved result, and returns the answer to the calling conversation.

## Why a separate saved chat?

Calling the same model is not enough to guarantee a fresh context.

This implementation deliberately creates a new Open WebUI chat and sends only the supplied worker prompt. That gives you an inspectable chat ID and avoids passing the parent conversation into the worker request.

## Requirements

- Open WebUI with Workspace Tools enabled
- an Open WebUI API key
- a model already available to Open WebUI
- Python dependency: `httpx`

The tool metadata declares `httpx` as a requirement.

## Install

1. Open **Workspace → Tools** in Open WebUI.
2. Create a new Tool.
3. Paste the contents of [`fresh_worker.py`](fresh_worker.py).
4. Save it.
5. Open the Tool's **Valves**.
6. Configure:
   - `base_url`
   - `api_key`
   - `worker_model` (optional fallback; normally leave blank)
7. Enable the Fresh Worker tool for the parent model/chat.

Open WebUI's documentation notes that Workspace Tools execute Python on the server. Install only code you trust.

## Valves

### `base_url`

The Open WebUI base URL **as reachable from the server process that executes this tool**.

Examples depend on your deployment:

```text
http://localhost:3000
```

or, in some container deployments, an internal service address/port rather than the host-browser URL.

Do not assume the address you use in your browser is automatically the correct address from inside a container.

### `api_key`

An Open WebUI API key used by the tool to create and retrieve chats.

Treat it as a secret.

### Model selection (automatic by default)

Fresh Worker v0.1.3 automatically uses the **model selected in the calling Open WebUI chat**, obtained from Open WebUI's tool metadata. You do **not** have to look up or enter a model ID when switching between models.

`worker_model` is an **optional fallback** model ID, used only when Open WebUI does not supply a model in the calling chat metadata. Leave it blank for normal use. No particular model is hard-coded.

To use a different worker model for a particular call, pass the optional `model` parameter with its exact Open WebUI model ID. An explicit override takes precedence over the current chat model and the fallback.

The tool also accepts an optional separate `system_prompt`, which is empty by default. Parent chat history is not copied into the worker.

### `wait_timeout`

Maximum number of seconds to wait for the worker generation.

Default:

```text
600
```

### `poll_interval`

Seconds between task-status polls.

Default:

```text
2
```

### `evidence_dir`

Optional server-side directory in which the complete retrieved worker-chat JSON is saved.

Leave blank to disable evidence-file output.

## Worker request restrictions

The completion request explicitly sets:

```text
tools: []
web_search: false
code_interpreter: false
image_generation: false
memory: false
```

It also disables title, tag, and follow-up background generation for the worker request.

This keeps the worker bounded and reduces hidden context/features.

## Use

Ask the parent model to delegate a self-contained task.

For example:

```text
Use fresh_worker to independently inspect the following migration plan.

Give the worker:
- the full plan;
- the schema constraints;
- the acceptance criteria.

After it returns, compare its findings with your own.
```

The tool itself accepts:

```json
{
  "prompt": "Complete self-contained worker instruction"
}
```

An explicit model override is optional:

```json
{
  "prompt": "Complete self-contained worker instruction",
  "model": "exact-model-id"
}
```

With no `model` argument, the worker uses the calling chat's selected model. In the parent chat, make sure the Fresh Worker tool is enabled for that model before asking it to run.

## Returned result

The tool returns a structure containing:

- `chat_id`
- `response`
- `model`
- `done`
- `evidence_path` when configured

The saved chat ID lets you inspect the independent worker run in Open WebUI.

## Compatibility warning

The v0.1.3 code has passed a live end-to-end test with `bonsai-2:27b` on the maintainer's Open WebUI setup. That does **not** establish compatibility with every model or Open WebUI version. Earlier v0.1.2 logic was exercised on Open WebUI 0.11.3; v0.1.3 should be checked on other host versions as APIs evolve.

This implementation uses Open WebUI chat/task endpoints including:

```text
POST /api/v1/chats/new
POST /api/chat/completions
GET  /api/tasks/chat/{chat_id}
GET  /api/v1/chats/{chat_id}
```

Those are host implementation details and may change between Open WebUI releases.

If a future release changes these endpoints or payloads, the tool may require an update. Please report the Open WebUI version and the failing response when opening an issue.

## Security

Open WebUI Workspace Tools run arbitrary Python code on the server. Review this file before installation and restrict Tool editing/import permissions appropriately.

The API key is sent only to the configured `base_url` in the `Authorization: Bearer ...` header. The returned result deliberately excludes credentials.

## Upstream documentation

Open WebUI Tools:
https://docs.openwebui.com/features/extensibility/plugin/tools/

Open WebUI Tool development:
https://docs.openwebui.com/features/extensibility/plugin/tools/development/

Open WebUI Valves:
https://docs.openwebui.com/features/extensibility/plugin/development/valves/
