# Changelog

## 0.1.3 — 2026-10-22

Open WebUI update (Pi extension unchanged).

- Automatically select the calling Open WebUI chat model via tool `__metadata__`, instead of requiring a manually configured `worker_model`.
- Keep an optional exact `model` override and use `worker_model` only as a fallback when chat metadata is unavailable.
- Preserve the caller's prompt verbatim and allow an optional independent `system_prompt`.
- Improve saved-result validation, task polling, retry and timeout/cancellation handling, status notification resilience, and redacted HTTP error reporting (building on v0.1.2).
- Verify model selection and response retrieval with a live `bonsai-2:27b` worker run. This is not a claim that every model and host version has been tested.

## 0.1.1 — 2026-10-12

Open WebUI security maintenance release (Pi extension unchanged).

- Validate server-provided chat IDs before use in URL paths or optional evidence filenames.
- Add regression coverage for unsafe chat ID characters and GitHub Actions Python checks.


## 0.1.0 — 2026-09-27

Initial public release.

### Added

- Pi Fresh Worker extension.
- Open WebUI Fresh Worker Workspace Tool.
- Shared concept and isolation-contract documentation.
- Installation and configuration guides.
- Prompt examples.
- Security and contribution notes.

### Public-release cleanup

- Removed Magazine-specific Pi `pipe_proof` verification code and paths.
- Removed the project-specific default Open WebUI model.
- Changed the saved Open WebUI chat title to `Fresh Worker`.
- Added explicit validation for the configured worker model and polling values.
