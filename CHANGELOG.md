# Changelog

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
