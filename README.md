# Veynuq


![Veynuq logo](assets/brand/logo-dark.svg)

Veynuq (pronounced “VAY-nook”) is an independent Windows desktop AI agent. It works with local models or a Chat Completions compatible API, and uses backend tools to act on files, projects, GitHub, the web and accessible Windows applications.

## Quick installation

Requires **Windows 10/11 and Python 3.11+**.

1. Download **`veyq-update.zip`** from [the latest release](https://github.com/gabriele-gaudissard/Veynuq-Agent-App/releases/latest), under **Assets**.
2. Extract the complete ZIP to a writable application folder outside your working projects.
3. Open **`Installer.bat`** once. It configures dependencies, updates and the Desktop shortcut.
4. Launch **Veynuq** from the Desktop and choose an installed model or download one in Settings.

Use the release ZIP for installation. GitHub's **Source code** archives and **Code → Download ZIP** contain the repository checkout, including publishing files. Node/npm and test files are not needed by users. Keep the extracted application files together: they support the app and its future updates.

## See Veynuq

Three screenshots of the running Windows application in English with an isolated demo profile, including the local dictation button. The illustrative conversation contains no personal chat or credentials and is not a benchmark. New profiles start in English.

**Workspace and conversation** — both user and agent messages are aligned left; the composer stays visible while history scrolls.

![Workspace and conversation](docs/screenshots/workspace.png)

**Task center** — resumable progress, reusable procedures, change review and read-only schedules.

![Task center](docs/screenshots/explorer.png)

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

The **Tools** menu describes the 39 integrated tools by category. Requests to execute work trigger tools rather than a tutorial. If a model produces an instruction-only draft, Veynuq retries twice with an execution reminder and then reports that it could not complete and verify the request. Compatible APIs request required tool calls where appropriate. This improves execution behavior but does not make every local model equally capable or reproduce proprietary agent services.

Browser control reuses installed Microsoft Edge through Playwright. Its separate local profile is inside the private data folder and can contain site cookies; it does not take over your everyday browser profile. Only an explicitly opened loopback development server on a port of 1024 or higher is allowed locally; other private/reserved destinations are blocked. Browser traffic is checked through request routing rather than the DNS-pinned transport used by structured URL/download tools, so these controls are not a network sandbox. No external plugin or account setup runs on launch. AI image generation still requires a suitable local image engine or a separately authenticated service; it is not included in the local language model.

## Install and launch

Windows 10/11 and Python 3.11+ are required. A tool-capable local model is sufficient; a paid API is optional.

Follow **Quick installation** above. A new profile starts in **English**. Choose a 7B, 8B or 14B starter model, another catalog model, an installed model, or a remote API.

Model downloads require your explicit choice. If the default local engine is missing, the confirmed download starts the official installer, verifies its Windows publisher signature and starts the engine. An already running engine is reused. Installer failures preserve the application and are reported. Engine installation requires network access and a valid publisher signature; this path is not needed on an already configured PC.

The installer creates Desktop and Start menu shortcuts with the dark seven-size Windows icon and verifies that the icon exists. The shortcut launches without a terminal window. `Veynuq.bat` also launches the app; opening a batch file directly may briefly show its shell. Missing Python packages are repaired automatically on launch, with diagnostics in `startup.log`. To repair only the shortcuts, open PowerShell in the application folder and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ShortcutOnly`; this preserves the installed runtime and your data.

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

These are application permission gates. In **Windows host** mode, shell commands run as the current Windows user and can access other files and network services. The separate offline command sandbox described below uses Docker isolation; file tools and desktop actions continue to use their own host permission gates. Structured file tools protect recognized credential locations and the app data folder, but arbitrary approved shell commands cannot provide the same isolation. Full access does not elevate Windows privileges. GUI controls in password-manager/system-security apps and Veynuq’s own permission UI are protected; inaccessible or elevated applications may require a different approach.

Approval is tied to one action and exact parameters. File changes while approval is pending invalidate it. Denials are returned to the model and recorded. Configuration/project mutations are blocked during work; follow-ups and question answers remain available. Stop interrupts the model connection and terminates command process trees. A window-close handler performs the same cleanup even with command timeouts disabled. Completed side effects remain applied.

## Speak instead of typing

Press **🎙 Speak** beside the message field. On first use, confirm **Download speech model** to obtain the pinned multilingual base model (about 150 MB) from Hugging Face. This is separate from the chat model; no account is needed. Press **Speak** again to begin recording, then **Stop recording** to transcribe. Recording is visibly indicated and automatically stops after two minutes. **Cancel dictation** discards the recording/transcript and terminates the dedicated worker. Closing the app also stops it.

Transcription runs locally on CPU using faster-whisper/CTranslate2 and automatically detects the spoken language. Once prepared, it works without a network connection; audio stays in memory and is not uploaded or saved. The text is appended to the message box for editing and **is never sent automatically**. During an agent response it can be sent as a normal immediate follow-up. Switching conversations cancels dictation to keep transcripts out of another chat. Windows microphone permissions and an available recording device are required; accuracy depends on speech clarity and background noise. The two-minute recording cap is separate from the optional agent step/command limits.

## Long tasks, review and controlled execution

**Task center** shows saved progress and lets you resume an interrupted, cancelled, failed or step-limited activity. Full history stays on disk; older exchanges are condensed into bounded observations for the model. The agent can save decisions, verification and next steps with `checkpoint_task`. After a crash, dispatched tools without recorded results are marked **outcome unknown** and are never automatically replayed. Resume asks the model to inspect the real state first. This is application context management, not a guarantee of the model's reasoning quality.

**Review changes** displays additions and removals with separate colors, including unstaged, staged and new Git files. Outside Git, it compares available file backups. Sandbox changes are shown separately through the agent's review tool and are also included in Task center. Binary and large output is bounded. Review does not publish or merge anything.

Five reusable procedures cover coding, desktop work, repository setup, code review and documents. Up to three model workers can investigate independent questions concurrently. Workers can only read/search/list files inside the selected project; they cannot execute commands, write files, browse, control the PC or delegate again. The main agent performs the changes. `git_worktree` creates a separate generated branch and sibling checkout from a clean repository, with checkout hooks disabled. Select that folder as the project for isolated coding and review before merging.

In **Settings → Command environment**, select **Offline sandbox** to execute Linux `/bin/sh` commands on a filtered disposable project copy. This requires an installed, running local Docker Linux engine and the cached `python:3.13-slim` image. To prepare the image, run `docker pull python:3.13-slim` after installing Docker. Veynuq refuses remote Docker endpoints and never falls back to Windows host execution when isolation is unavailable. Containers have no network, a read-only root, dropped capabilities, no new privileges, an unprivileged user, and process/CPU/memory limits. Only the disposable copy is mounted. Credentials, profile data, Git metadata and dependency folders are excluded. Copies are limited to 20 MB, 2000 files and 2 MB per file; output size is monitored, not a filesystem disk quota. Sandbox mode is suitable for small code tasks; it is not a Windows GUI virtual machine.

Sandbox edits are held in the local profile and survive restarting the app. Use `sandbox_changes` to review/apply them. Application checks the original host hashes, refuses overwriting externally changed files, creates backups and rolls back partial application failures. Auto/always approval shows the actual diff before applying. Full access follows the user's selected approval policy. File/desktop tools remain host actions: selecting the command sandbox does not isolate all PC interaction.

**Read-only schedules** run project checks with the selected model while Veynuq is open, at intervals from 1 to 168 hours. Missed checks run once on the next launch; failed or interrupted runs pause for review. Scheduled checks cannot execute commands, change files, browse, use GitHub or control the desktop, even when the app normally has full access. They use at most 12 model turns and remain read-only when resumed. A remote selected provider still receives the permitted context. Schedules can be paused, enabled or removed; deleting a chat removes its schedules. Running with the app closed requires explicitly enabling the visible Windows scheduled task described below; it is disabled by default.

## GitHub and updates

The GitHub tool accepts `repository: "owner/name"` for each action. Settings can hold an optional default. A token is only necessary for private data and authenticated writes; use a fine-grained token with the permissions you need. It stays in the backend vault and is injected into requests. Git credential-manager authentication for command-line Git is separate.

Pushing changes to **main** runs Windows backend tests, UI tests, syntax checks and a real isolated Linux Docker test before publishing a release. An unpushed local edit or another branch does not update users. Installed packages check at startup and hourly, stage the new version and restart when idle. This independent update check contacts GitHub even if the agent’s online tools are off; disable automatic updates too when avoiding outbound traffic. Explicit model downloads and engine setup also contact their publishers after confirmation.

Every update manifest is **Ed25519 signed** against a pinned publisher key, checked before staging and again before applying. The updater verifies SHA-256 hashes, rejects unsigned/tampered manifests, archive traversal/links and older release sequences, preserves user data, backs up app files and rolls back a failed installation. Changed dependencies install into a separate runtime before switching. Offline/download/rate-limit failures leave the current app installed.

The update publisher is `gabriele-gaudissard/Veynuq-Agent-App`; this fixed trust source is independent of the repositories the agent works on. The signing private key is an Actions secret, with a publisher backup in the Windows vault, and is never distributed. The package signature is not a Windows Authenticode certificate.

Developer checkouts with `.git` use Git updates and are never overwritten by the package updater. Modified managed app files also pause updates to preserve changes. Users of the original application install this version once because the original has no updater. Earlier Veyq packages also require a one-time installation of this renamed release: their updater trusts the old repository URL and file list. Subsequent Veynuq releases update automatically.

## Privacy and recovery

Data defaults to `%LOCALAPPDATA%\Veynuq`, with `VEYNUQ_DATA_DIR` and the legacy `VEYQ_DATA_DIR` overrides supported. Existing Veyq profiles are reused. Installation records the physical profile path in local `profile.json` so Windows filesystem redirection does not create separate profiles for different launchers. This machine-specific file is preserved during updates and is never distributed. Legacy `codex_data.json` is imported once, retaining chats/projects/preferences and migrating the provider token into the vault. The legacy token field is scrubbed after vault storage succeeds.

Chats, settings, memory and backups are local plaintext files protected by the Windows account. Tokens are separately encrypted with current-user DPAPI. The metadata-only audit log records tool names/outcomes/digests, not chat contents. There are no analytics, external fonts or runtime CDN scripts; Markdown/highlight/sanitizer libraries ship locally with licenses. A remote provider receives the context and, when enabled/requested, screenshots needed for the task.

Corrupt JSON is preserved under a separate filename. The app restores the previous valid snapshot, or creates a clean profile if no valid snapshot exists, and displays a recovery notice. Recognized token patterns/configured credentials are redacted from output and logs; this is not a universal secret detector. Structured web tools block private/reserved network addresses and validate DNS/redirects. Missing Beautiful Soup disables web extraction/search rather than crashing the whole app.

## Autonomy and creative tools in 4.2

The agent now checks the local engine’s installed tool capabilities rather than relying only on catalog estimates. Local context/response budgets are configurable; the requested context is capped by the model metadata when available. Successful repeated reads are not counted as repeated failures. Temporary model connection/backend interruptions retry the current response up to twice without replaying accepted tool actions. Automatic chat titles end at a word boundary with an ellipsis when limited to 100 characters; manually named chats are preserved. After mutations the agent requests an inspection before completing; when verification is missing it records **unverified**, with a resumable task, rather than recording a completed activity. A read result is evidence for the model to assess, not a guarantee that every user requirement has been met.

`computer_wait` waits for observed UI text/value with cancellation and a bounded timeout. Windows Sandbox scope limits desktop targeting to the supported native sandbox client and rejects other host windows. Canvas typing is only available within that scope after a fresh screenshot and a vision capability check; host applications retain editable-field restrictions.

`windows_sandbox` creates a filtered project copy and starts an already available Windows Sandbox. Network, clipboard, microphone, camera, printer and GPU sharing are disabled, Protected Client is enabled, and the only mapped folder is read-only. The guest may copy inputs internally for editing; guest changes disappear on closing and are not automatically exported to the host. Preparing the configuration does not enable Windows features or install a hypervisor. Windows edition, feature and virtualization requirements remain external prerequisites. This scope restricts desktop tools; project file tools and command execution retain their separate permissions. [Windows Sandbox configuration reference](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file).

An opt-in setting registers a visible per-user Windows scheduled task for read-only project reviews while Veynuq is closed. It checks every five minutes while that user is signed in, uses no administrator privileges or saved Windows password, verifies the installed files, and takes the same exclusive profile lock as the app before loading state. Opening the app asks the worker to stop. Background runs have a four-minute limit, cannot install dependencies, execute commands, change project files, control the desktop or wait for absent approvals. Failed/interrupted schedules pause for review. A selected remote model still receives its required context. There is no activity while the user is signed out or the PC is off.

Image generation uses a separately configured, already running local Stable Diffusion API or an HTTPS compatible `/images/generations` API. It is disabled by default. A local engine requires no account; a remote service may require an API key stored separately in the vault and may charge for generation. The app does not download a multi-GB image model or create a subscription automatically. Prompts are sent only to the configured engine. Generation runs in a cancellable process, bounds responses, validates/re-encodes actual pixels to PNG, checks the destination again, and backs up replacements. Stopping prevents the local output write; the remote provider may still finish its request. Actual generated files can be previewed from the task center without allowing arbitrary Markdown HTML or remote image embeds. [Local image API reference](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API), [compatible images API reference](https://developers.openai.com/api/reference/resources/images/methods/generate).

The native window now loads a self-contained, nonce-protected local interface rather than relying on a localhost asset server. This avoids blank or partly initialized windows when local asset requests fail. Project-group expansion is saved in the local profile, and copying has a native-compatible fallback when the browser clipboard API is unavailable. The four UI languages include the new settings. These changes do not turn a small model into a frontier model or guarantee successful control of every third-party application.

## Development and validation

The verification suite is retained in repository history at the immutable commit `0ae7d9959d8673f19e26b66ace664d82d3f28694`, reachable from `main` without a separate branch. CI restores this baseline to ignored working files before checking the current application. Local maintenance files are preserved but are not tracked in the main tree or included in the installer. To restore the same checks in a fresh source checkout:

```powershell
git fetch --depth=1 origin 0ae7d9959d8673f19e26b66ace664d82d3f28694
git restore --source=0ae7d9959d8673f19e26b66ace664d82d3f28694 --worktree -- tests package.json package-lock.json ui-translations.json
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py veyq
npm ci
npm test
node --check app.js
python app.py --self-check
```

The 146 backend checks include controlled profile-lock handoff, background installation integrity, isolated desktop filtering, actual image-worker HTTP/pixel validation, artifact ownership, cancellation, model capabilities/context limits, safe transport retries and mutation verification. Windows validated the scheduled-task XML using validate-only mode; no task was registered. The image test uses a local mock API, not a live diffusion model or a paid service. Windows Sandbox is absent on the development PC, so its guest interaction is not claimed as live-tested. The backend checks and UI suite also cover approval denial, process cancellation/timeouts, persistent cwd, memory/project scoping, immediate follow-ups, actual chat removal, action-intent repair, questions, partial HTTP cancellation, recovery, credential paths, literal keyboard input, mouse targeting/drag cleanup, deep Windows accessibility trees, stale control identity, read-only fields, download integrity, backup restoration, Markdown sanitation, four-language switching, signed updates and rollback. An isolated real Edge test filled an input, clicked a button and rejected reuse of the previous observation. A live `qwen3:14b` desktop run typed into an isolated test window, selected its checkbox, resumed after a local model backend interruption, clicked its verification button and inspected the resulting PASS. All eight native tool calls succeeded; unrelated Windows applications and tools were blocked by the test harness. Another live `qwen3:14b` run received a follow-up during generation, changed and reread an actual file, then inspected the Windows keyboard without changing it. Earlier live runs cloned `octocat/Hello-World`, wrote a validation script and ran it successfully with Python. Windows mouse/key dispatch and keyboard-setting writes have controlled regression checks; a separate live-model desktop test uses a disposable test window with all unrelated tools/windows blocked. Visual QA covers the real Veynuq app. The Docker test runs in an isolated Linux CI job because Docker is not installed on the development PC. This does not verify every third-party Windows application's accessibility behavior. The missing-engine installer path is checked structurally and with mocks because the development PC already has the engine; no unnecessary reinstall or multi-GB model download was performed.

The agent’s ability to finish a particular task still depends on the model, available tools, hardware, permissions and service responses. It does not guarantee frontier-model quality or successful control of every Windows application. There is no generic MCP/plugin manager or voice/video generation; dictation is speech input. Read-only schedules can run with the app closed after explicit opt-in, while the Windows user remains signed in.

Publisher builds use `.github/build_release.py`, the Actions signing secret and the workflow run number. The publisher explicitly selects distribution files, independently of `.gitignore`; build-time validation rejects accidental development files or private data in the package. Keep the private key out of source, arguments and ordinary JSON. Startup diagnostics are in the profile’s `startup.log`.

## Name and licenses

The user-selected name is **Veynuq**. Public searches on 8 October 2026 found no exact software brand, GitHub repository, npm/PyPI package or Apple app under this name. Its .com and .app RDAP lookups returned no registration record at that time. Interactive trademark databases were not fully searchable, so this is a preliminary name screen, not legal clearance or a guarantee of exclusivity. Mandatory third-party licenses/attribution remain in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE). Internal compatibility paths retain older identifiers to preserve installed profiles and update trust.
