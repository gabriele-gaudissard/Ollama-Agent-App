# Veynuq

![Veynuq logo](assets/brand/logo-dark.svg)

Veynuq (pronounced “VAY-nook”) is an independent Windows desktop AI agent. It works with local models or a Chat Completions compatible API, and uses backend tools to act on files, projects, GitHub, the web and accessible Windows applications.

## See Veynuq

Three screenshots of the running Windows application with an isolated demo profile. The illustrative conversation contains no personal chat or credentials and is not a benchmark.

**Workspace and conversation** — both user and agent messages are aligned left; the composer stays visible while history scrolls.

![Workspace and conversation](docs/screenshots/workspace.png)

**Project explorer** — browse folders, read real files and refer to them in chat.

![Project explorer](docs/screenshots/explorer.png)

**Models and settings** — installed models, the ten-model download selector, custom names and information beside each model. Permissions and provider credentials are further down the same panel.

![Models and settings](docs/screenshots/permissions.png)

The [brand assets](assets/brand) include original [dark](assets/brand/logo-dark.svg) and [light](assets/brand/logo-light.svg) SVG/PNG logos and a Windows icon. The Desktop shortcut uses the dark icon.

## What it does

The backend owns the model → tool → result loop. Markdown code fences never execute commands. Actions use validated structured tool calls, and failures return the actual error/output to the model for correction.

- **Code and projects:** read/search/write/edit files, run PowerShell commands and tests, inspect Git, clone public repositories and configure their dependencies. Commands report exit codes; shell directory changes persist across commands and restarts.
- **Files and documents:** create folders, move/delete individual files with recoverable backups, restore backups, preview files and images, extract PDF/DOCX text, attach files with bounded text excerpts, and link folders. Documents, spreadsheets and charts can be created through project Python code and the required libraries.
- **Mouse and keyboard:** list visible Windows applications, inspect accessible controls, click, double-click, right-click, drag, scroll, type literal text and send shortcuts. Input is bound to a verified live control and mouse points are checked against the actual target window. Failed argument validation preserves the observation; successful input requires a new inspection. Slow model responses can refresh an older observation only after the same live control identity is verified. Read-only and password fields are protected. Vision-capable models can receive requested window screenshots; other models use the accessibility tree.
- **Windows keyboard settings:** inspect and set the current user's default US, UK, Italian, French, German or Spanish input layout directly, preserving existing languages and the Windows display language. The tool reads back the result. Existing applications may retain their input method until reopened; it does not claim to modify the BIOS or every open window.
- **Browser and downloads:** operate a separate Edge browser through observed page elements, fill ordinary fields, click, choose options, scroll and use shortcuts. Its worker can be stopped independently. Public file downloads support optional SHA-256 verification and preserve existing content before replacement. No plugin or account is required for public pages. Private services may require the user's own sign-in; password fields are not filled by the agent.
- **Online and GitHub:** DuckDuckGo search with Bing fallback, public URL reading, and GitHub REST reads/writes for any requested repository. The configured repository is an optional default, not a restriction. GitHub itself enforces the token’s permissions.
- **Conversation:** projects with accordion groups, full-text chat search, rename/delete/export, persistent editable memory, paginated access to other chats in the same project, Markdown tables/lists/highlighting, copy and regeneration. Titles wrap instead of being cut in half. Deleting removes the session itself and leaves the welcome screen when no chats remain.
- **During a run:** live text and colored tool logs, task plans, targeted questions, immediate follow-ups, and Stop when the composer is empty. Stopping preserves partial text and completed actions.
- **Models:** installed-model dropdown, a ten-family catalog, custom-name download, progress/cancellation, deletion, source links and approximate RAM/VRAM/size/use-case details.
- **Distribution:** tested main-branch pushes create signed GitHub Releases; managed installations download and apply updates automatically when idle.

The main repository contains the application, user documentation, brand assets, third-party licenses and the GitHub publishing workflow. Tests, Node test dependencies, brand-generation scripts and temporary/private files are excluded by `.gitignore`. The installer package includes only the application and user-facing assets; Python is the only runtime prerequisite, and Node/npm are not needed by users.

The **Tools** menu describes the 30 integrated tools by category. Requests to execute work trigger tools rather than a tutorial. If a model produces an instruction-only draft, Veynuq retries twice with an execution reminder and then reports that it could not complete and verify the request. Compatible APIs request required tool calls where appropriate. This improves execution behavior but does not make every local model equally capable or reproduce proprietary agent services.

Browser control reuses installed Microsoft Edge through Playwright. Its separate local profile is inside the private data folder and can contain site cookies; it does not take over your everyday browser profile. Only an explicitly opened loopback development server on a port of 1024 or higher is allowed locally; other private/reserved destinations are blocked. Browser traffic is checked through request routing rather than the DNS-pinned transport used by structured URL/download tools, so these controls are not a network sandbox. No external plugin or account setup runs on launch. AI image generation still requires a suitable local image engine or a separately authenticated service; it is not included in the local language model.

## Install and launch

Windows 10/11 and Python 3.11+ are required. A tool-capable local model is sufficient; a paid API is optional.

1. Download `veyq-update.zip` from [the latest release](https://github.com/gabriele-gaudissard/Veynuq-Agent-App/releases/latest).
2. Extract it to a writable application folder outside your working projects.
3. Run `Installer.bat`. It creates a virtual environment, installs dependencies, registers updates and creates the Veynuq Desktop shortcut.
4. Launch Veynuq. A new profile starts in **English**. Choose a 7B, 8B or 14B starter model, another catalog model, an installed model, or a remote API.

Model downloads require your explicit choice. If the default local engine is missing, the confirmed download starts the official installer, verifies its Windows publisher signature and starts the engine. An already running engine is reused. Installer failures preserve the application and are reported. Engine installation requires network access and a valid publisher signature; this path is not needed on an already configured PC.

`Installer_only_shortcut.bat` repairs the Desktop and Start menu shortcuts with the dark seven-size Windows icon. The installer verifies that the icon exists. The shortcut launches without a terminal window. `Veynuq.bat` also launches the app; opening a batch file directly may briefly show its shell. Missing Python packages are repaired automatically on launch, with diagnostics in `startup.log`.

Settings includes a visible selector for 10 popular free local model families, a custom model-name download field and an information button beside each model. Details distinguish catalog estimates from live installed metadata, including parameters, quantization, maximum context, license, native tools, images and estimated hardware fit. Popular families are curated rather than presented as an unverified global usage ranking. Models without native tool support serve chat and analysis; choose Qwen3 or another tool-capable model for autonomous work.

You can switch existing chats while an agent works and return to the partial response. One run executes at a time; the composer offers a return button when you view another chat. The chat menu includes **Add to project**, with a project picker.

The local protocol uses `/api/chat`, `/api/tags`, `/api/show`, `/api/pull` and `/api/delete`. Compatible APIs use `/chat/completions` and `/models`; include `/v1` where required. Remote endpoints require HTTPS and online access. Local unauthenticated endpoints need no token. Remote vision input is an explicit setting.

The catalog contains curated popular families, not a measured popularity or performance ranking. Hardware figures assume typical quantized weights and are estimates: context, quantization and GPU offloading change requirements. CPU-only inference works but can be slow. Models without native tools work as chat models; select a tool-capable model for autonomous actions.

## Language, follow-ups and optional limits

English, Italian, Spanish and French apply immediately and persist across restarts. The model receives the selected response language. Model-generated prose, filenames, source code and raw operating-system/tool output are preserved rather than translated by the UI.

Type while the agent works to send a **follow-up**. During a model response it interrupts the stream and replans within the same activity. An already executing command reaches its completion; remaining calls from the old batch are marked as skipped before the new instruction is processed, keeping tool/result pairing valid. Leave the composer empty to **Stop**. Regeneration removes later chat messages but does not undo previously executed actions; inspect the result before repeating work.

**Maximum steps: `0` means unlimited. Command timeout: `0` disables the command timeout.** New profiles default to both disabled. You can enable finite values in Settings. Stop, window-close cleanup, output-size validation and repeated-identical-action protection remain active. Network transports retain connection/read timeouts so unavailable services do not hang forever.

## Approval modes

| Mode | Behavior |
| --- | --- |
| Always ask | Each action tool requires one explicit approval; asking an essential question itself does not need a second approval. |
| Approve for me | Project file reads/changes and keyboard inspection proceed automatically. Keyboard changes, commands, desktop/browser control, downloads, backup restoration, outside-project access, deletions, memory writes, other-chat context, online requests and GitHub writes require approval. |
| Full access | Actions proceed without confirmations, subject to validation and the online switch. Enabling it requires an explicit checkbox. |

These are application permission gates, **not an OS sandbox**. Shell commands run as the current Windows user and can access other files and network services. Structured file tools protect recognized credential locations and the app data folder, but arbitrary approved shell commands cannot provide the same isolation. Full access does not elevate Windows privileges. GUI controls in password-manager/system-security apps and Veynuq’s own permission UI are protected; inaccessible or elevated applications may require a different approach.

Approval is tied to one action and exact parameters. File changes while approval is pending invalidate it. Denials are returned to the model and recorded. Configuration/project mutations are blocked during work; follow-ups and question answers remain available. Stop interrupts the model connection and terminates command process trees. A window-close handler performs the same cleanup even with command timeouts disabled. Completed side effects remain applied.

## GitHub and updates

The GitHub tool accepts `repository: "owner/name"` for each action. Settings can hold an optional default. A token is only necessary for private data and authenticated writes; use a fine-grained token with the permissions you need. It stays in the backend vault and is injected into requests. Git credential-manager authentication for command-line Git is separate.

Pushing changes to **main** runs Windows backend tests, UI tests and syntax checks before publishing a release. An unpushed local edit or another branch does not update users. Installed packages check at startup and hourly, stage the new version and restart when idle. This independent update check contacts GitHub even if the agent’s online tools are off; disable automatic updates too when avoiding outbound traffic. Explicit model downloads and engine setup also contact their publishers after confirmation.

Every update manifest is **Ed25519 signed** against a pinned publisher key, checked before staging and again before applying. The updater verifies SHA-256 hashes, rejects unsigned/tampered manifests, archive traversal/links and older release sequences, preserves user data, backs up app files and rolls back a failed installation. Changed dependencies install into a separate runtime before switching. Offline/download/rate-limit failures leave the current app installed.

The update publisher is `gabriele-gaudissard/Veynuq-Agent-App`; this fixed trust source is independent of the repositories the agent works on. The signing private key is an Actions secret, with a publisher backup in the Windows vault, and is never distributed. The package signature is not a Windows Authenticode certificate.

Developer checkouts with `.git` use Git updates and are never overwritten by the package updater. Modified managed app files also pause updates to preserve changes. Users of the original application install this version once because the original has no updater. Earlier Veyq packages also require a one-time installation of this renamed release: their updater trusts the old repository URL and file list. Subsequent Veynuq releases update automatically.

## Privacy and recovery

Data defaults to `%LOCALAPPDATA%\Veynuq`, with `VEYNUQ_DATA_DIR` and the legacy `VEYQ_DATA_DIR` overrides supported. Existing Veyq profiles are reused. Installation records the physical profile path in local `profile.json` so Windows filesystem redirection does not create separate profiles for different launchers. This machine-specific file is preserved during updates and is never distributed. Legacy `codex_data.json` is imported once, retaining chats/projects/preferences and migrating the provider token into the vault. The legacy token field is scrubbed after vault storage succeeds.

Chats, settings, memory and backups are local plaintext files protected by the Windows account. Tokens are separately encrypted with current-user DPAPI. The metadata-only audit log records tool names/outcomes/digests, not chat contents. There are no analytics, external fonts or runtime CDN scripts; Markdown/highlight/sanitizer libraries ship locally with licenses. A remote provider receives the context and, when enabled/requested, screenshots needed for the task.

Corrupt JSON is preserved under a separate filename. The app restores the previous valid snapshot, or creates a clean profile if no valid snapshot exists, and displays a recovery notice. Recognized token patterns/configured credentials are redacted from output and logs; this is not a universal secret detector. Structured web tools block private/reserved network addresses and validate DNS/redirects. Missing Beautiful Soup disables web extraction/search rather than crashing the whole app.

## Development and validation

The verification suite is retained on the separate `verification` branch at the immutable commit `eb52194d568b3d2330a65bb7704ec2ac763b4b82`. CI restores this baseline to ignored working files before checking the current application. Local maintenance files are preserved but are not tracked in the main tree or included in the installer. To restore the same checks in a fresh source checkout:

```powershell
git fetch --depth=1 origin eb52194d568b3d2330a65bb7704ec2ac763b4b82
git restore --source=eb52194d568b3d2330a65bb7704ec2ac763b4b82 --worktree -- tests package.json package-lock.json ui-translations.json
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py veyq
npm ci
npm test
node --check app.js
python app.py --self-check
```

The 90 backend tests and UI suite cover approval denial, process cancellation/timeouts, persistent cwd, memory/project scoping, immediate follow-ups, actual chat removal, action-intent repair, questions, partial HTTP cancellation, recovery, credential paths, literal keyboard input, mouse targeting/drag cleanup, deep Windows accessibility trees, stale control identity, read-only fields, download integrity, backup restoration, Markdown sanitation, four-language switching, signed updates and rollback. An isolated real Edge test filled an input, clicked a button and rejected reuse of the previous observation. A live `qwen3:14b` run received a follow-up during generation, changed and reread an actual file, then inspected the Windows keyboard without changing it. Earlier live runs cloned `octocat/Hello-World`, wrote a validation script and ran it successfully with Python. Windows mouse/key dispatch and keyboard-setting writes are checked with controlled doubles; visual QA covers the real Veynuq app. This does not verify every third-party Windows application's accessibility behavior. The missing-engine installer path is checked structurally and with mocks because the development PC already has the engine; no unnecessary reinstall or multi-GB model download was performed.

The agent’s ability to finish a particular task still depends on the model, available tools, hardware, permissions and service responses. It does not guarantee frontier-model quality or successful control of every Windows application. There is no generic MCP/plugin manager, voice/video generator or unattended scheduler in this release.

Publisher builds use `.github/build_release.py`, the Actions signing secret and the workflow run number. The publisher explicitly selects distribution files, independently of `.gitignore`; build-time validation rejects accidental development files or private data in the package. Keep the private key out of source, arguments and ordinary JSON. Startup diagnostics are in the profile’s `startup.log`.

## Name and licenses

The user-selected name is **Veynuq**. Public searches on 8 October 2026 found no exact software brand, GitHub repository, npm/PyPI package or Apple app under this name. Its .com and .app RDAP lookups returned no registration record at that time. Interactive trademark databases were not fully searchable, so this is a preliminary name screen, not legal clearance or a guarantee of exclusivity. Mandatory third-party licenses/attribution remain in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE). Internal compatibility paths retain older identifiers to preserve installed profiles and update trust.
