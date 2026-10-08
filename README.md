# Veyq

Veyq (pronounced "vayk") is an independent Windows desktop AI agent. It connects to an existing local model server or a Chat Completions compatible API, and uses structured tools to work on a selected project.

## What it actually does

The Python backend owns the complete model → tool → result loop. The interface displays messages and approves specific actions; code fences and generated HTML are never interpreted as commands.

- Coding: inspect and search files, create/edit code, run shell commands and tests, inspect Git status/diffs/logs.
- File management: create directories, move individual files, delete individual files with confirmation, and restore backups from the interface.
- Online work: web search with source URLs, read public documentation, and GitHub REST reads/writes scoped to the repository you configure.
- Tasks: visible plans, streaming output, action history, bounded loops, cancellation, and persistent chats.
- Privacy: local chat storage, OS credential vault, metadata-only audit log, no analytics or CDN scripts, explicit online setting.
- Distribution: every tested push to main publishes a GitHub Release; managed installations check for and apply updates automatically.

Agent quality depends on the model, hardware and task. Veyq does not guarantee successful completion of every task or parity with hosted frontier agents. It currently has no general GUI/computer-control tool, voice/video generation, scheduled autonomous missions, or generic MCP connector manager.

## Install and launch

Windows 10/11, Python 3.11+ and a model with structured tool calling are required. A working local engine is already sufficient; no paid API is required for local use.

1. Download `veyq-update.zip` from [the latest release](https://github.com/gabriele-gaudissard/Veyq-Agent-App/releases/latest).
2. Extract it to a writable application folder, outside your project folders.
3. Run `Installer.bat`. It creates a virtual environment, installs Python packages, registers the installation and creates the **Veyq** Desktop shortcut. It does not overwrite chat data or download models without your action.
4. Launch **Veyq**, choose your project folder and configure your provider/model in Settings.

For an existing source checkout, launch `Veyq.bat`; its fallback uses the existing Python installation. `Installer_only_shortcut.bat` creates only the new shortcut. The old local model service continues to work; its executable has not been renamed or removed.

The local protocol uses `/api/chat` and `/api/tags`. A compatible API uses `/chat/completions` and `/models`; include `/v1` in the configured base URL if your provider requires it. Remote endpoints require HTTPS and the online setting. Provider tokens are optional for unauthenticated local endpoints.

## Permission modes

| Mode | Behavior |
| --- | --- |
| Chiedi sempre | Each model tool call pauses for one explicit approval. |
| Approva per me (default) | Reads and file changes inside the selected project proceed automatically. Commands, outside-project access, application-source changes, deletions, memory writes, network requests and GitHub publication require approval. |
| Accesso completo | Tools proceed without approvals, subject to hard validation, protected credential paths and the online switch. Enabling it requires an explicit checkbox. |

These are application permission gates, **not an operating-system sandbox**. Approved shell commands run with the Windows user's privileges and may reach other files and the network. For this reason the terminal is disabled when online tools are disabled. Use a separate OS account or isolated VM when executing untrusted code. Full access cannot guarantee credential isolation from arbitrary shell commands.

Approval is bound to one tool, its exact arguments and a digest. File content changes while approval is pending invalidate the action. Denial is recorded; an approval expires after ten minutes. Settings/project changes are blocked during a run. Cancellation stops pending approvals and kills running command process trees; a stalled model HTTP stream may take up to its 90-second read timeout to return. Completed mutations are preserved.

## GitHub

Set `owner/repository` and a fine-grained token in Settings. Choose only the permissions needed for that repository. Tokens stay in the backend vault and are injected into authenticated requests, never added to model context. The GitHub tool supports issues, pull requests, contents, commits, branches and releases through GET/POST/PATCH. Use approved Git commands for local branches, commits and pushes. Windows Git credential-manager authentication remains separate.

## Automatic updates

The release workflow runs Windows tests and syntax checks before publishing `veyq-update.zip` and its SHA-256 manifest. Pushing a file change to **main** triggers this pipeline; editing an unpushed local file or another branch does not publish an update.

Managed installations check GitHub on startup and hourly, verify the archive and every file, reject archive traversal/links, stage the update and restart when the agent is idle. The updater preserves the data folder, backs up replaced app files and rolls back file changes on installation failure. Changed requirements are installed in a separate virtual environment before switching runtimes. Failed downloads, offline machines and rate limits leave the current app installed. The automatic-update option independently contacts GitHub even when model tools are offline; disable both settings to avoid outbound traffic.

The publisher is the fixed repository `gabriele-gaudissard/Veyq-Agent-App`. SHA-256 verifies integrity against the manifest delivered from that repository over HTTPS; this is not an independent code-signing system. Anyone authorized to publish there can distribute application code. Protect the repository account and branch accordingly.

Developer checkouts containing `.git` are deliberately never overwritten by automatic updates. Update those with Git. Managed installations with locally edited application files also stop before overwriting them. The update status and previous builds are stored under the local data directory.

Users of the old application must install this version once: their existing version has no updater and cannot acquire one automatically.

## Local data and recovery

By default data lives in `%LOCALAPPDATA%\Veyq`; `VEYQ_DATA_DIR` can set another location. The legacy `codex_data.json` is imported once, preserving chats/projects/preferences and moving any provider token into the vault. The old token field is scrubbed after successful migration.

`state.json` contains chats, workspace paths, settings and memory **in plaintext**. Windows credentials use DPAPI bound to the current user; other platforms require a functioning system keyring. `audit.jsonl` contains timestamps, tool names, outcomes and argument hashes, not commands or file contents. File backups can contain private code. Protect the Windows account and disk. The interface supports chat export/deletion, memory clearing, token removal and individual-file restore.

Known credential paths such as `.env`, SSH keys, certificate keys and the agent data directory are blocked by structured file tools. Recognized tokens and configured credentials are redacted from model output and logs; this is a best-effort safeguard, not a universal secret detector. Web tools block private/reserved addresses and use DNS-pinned connections with redirect validation.

## Development and validation

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py veyq
node --check app.js
python app.py --self-check
python scripts/build_release.py release
```

The test suite covers permission denial, command cancellation/timeouts, backup/recovery, exact-edit failures, credential migration/storage, public-network checks, tool protocol pairing, safe Markdown behavior, update integrity, traversal rejection and rollback. Live-model behavior should also be tested with your selected model.

## Naming and license

The selected name is Veyq. A preliminary web search on 8 October 2026 found no matching commercial software brand; this does not certify trademark or domain availability. The application is independent of upstream model providers. Mandatory third-party attribution remains in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the author copyright remains in [LICENSE](LICENSE).
