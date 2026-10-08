# Requirement matrix

The uploaded 58-point list is implemented through the following features. “Equivalent” choices replace legacy implementation details; later user requests take precedence. Hardware figures are estimates, and external/GUI behavior depends on the selected model and Windows application.

| # | Requirement | Implementation |
| --- | --- | --- |
| 1 | Automatic Python dependencies | Startup repair and Installer.bat; pip errors go to startup.log |
| 2 | Detect existing local engine | Probe local API and locate installed executable |
| 3 | Download official engine if missing | Confirmed model choice triggers signed silent installer; unnecessary reinstalls avoided |
| 4 | 14B/7B/8B first-run choice | Native first-run UI replaces terminal menu |
| 5 | Preconfigured empty configuration | Veyq state.json; legacy codex_data.json migration retains old data |
| 6 | Silent Pythonw launcher | Desktop shortcut uses hidden bootstrap + visible pythonw GUI; direct .bat may briefly show shell |
| 7 | Create Desktop shortcut | Windows COM replaces temporary VBScript while delivering the same shortcut |
| 8 | Desktop icon | Custom dark Veyq icon supersedes generic shell32 icon, per later request |
| 9 | Shortcut-only recovery installer | Installer_only_shortcut.bat |
| 10 | Real action loop | Backend model/tool/result cycle, structured validated actions |
| 11 | Self-correct failed commands | Actual error/output returned, up-to-three correction guidance and identical-call guard |
| 12 | Language/cwd/memory context | System instructions + updated current shell directory + persistent memory |
| 13 | Installed-model dropdown | API-backed selection in Settings |
| 14 | Catalog and custom downloads | Ten-family UI and custom model name |
| 15 | Download streaming progress | Status/percentage and cancellation |
| 16 | RAM/VRAM details button | Minimum/recommended estimates; optional GPU, size and uses |
| 17 | Unknown-model inference | Parameter-count Q4 estimate, explicitly approximate |
| 18 | Delete models | Confirmed engine delete endpoint |
| 19 | Remote API URL/token | Local protocol and compatible APIs; remote HTTPS + backend token |
| 20 | PowerShell execution | Real subprocess, exit code/output, no console |
| 21 | Persistent cd hook | Backend side channel captures final cwd; persists per chat |
| 22 | Read textual files | Paginated UTF-8 read tool, protected secret paths |
| 23 | Create/edit files and parents | write_file/edit_file with automatic parent creation and backups |
| 24 | Directory listing | Structured list_dir + explorer |
| 25 | DuckDuckGo search | DDG snippets and source links with Bing fallback |
| 26 | HTML URL extraction | Removes non-content tags, bounded to 15000 characters |
| 27 | Long-term memory | save_memory tool + manual view/edit/clear |
| 28 | Other same-project chats | Project-only context; paginate chat list/full history |
| 29 | Projects with UUIDs | create_project generates UUID and folder |
| 30 | Project accordion groups | Grouped collapsible chat navigation |
| 31 | Assign existing chat | Project selector updates chat workspace |
| 32 | Automatic full history | Atomic save after every user/model/tool message |
| 33 | 25-character auto-title | First user message supplies first 25 characters |
| 34 | Live full-text search | Title and message search, debounced 150ms |
| 35 | Rename chat | Prompt and contextual menu |
| 36 | Confirm chat deletion | Confirmation before delete |
| 37 | Hover three-dot menu | Contextual rename/delete controls; keyboard-focus support |
| 38 | Scrolling long titles | Hover scroll only when text overflows |
| 39 | Header model badge | Selected model shown in project header |
| 40 | Animated working state | Pulsing status with current tool, yellow working text |
| 41 | Toggle activity panel | Expandable activity/tool results; compact-width overlay |
| 42 | Colored logs | Green successes, red errors, blue tool starts, yellow memory |
| 43 | Chat/log auto-scroll | Streaming and activity updates scroll to latest content |
| 44 | Live model text | Native JSON stream and compatible SSE stream |
| 45 | Full Markdown | Local marked.js, sanitized before DOM rendering |
| 46 | Code syntax highlighting | Local highlight.js + Atom One Dark |
| 47 | Copy exact Markdown | Exact raw response, 2-second copied feedback |
| 48 | Regenerate response | Truncate later messages; completed actions stay applied |
| 49 | File chooser attachment | Copy into project; bounded inline text excerpt and full path, PDF/DOCX tools |
| 50 | Autoresize/Enter/Shift+Enter | Composer grows; Enter sends, Shift+Enter inserts newline |
| 51 | Send/Stop/Follow-up state | Normal send, empty-during-run stop, typed-during-run follow-up |
| 52 | Cancel and save partial text | Interrupt HTTP socket; preserve partial assistant message |
| 53 | Immediate EN/IT/ES/FR | Labels/placeholders/contextual menus; stored across restart |
| 54 | Model response language | Selected language in system instructions; explicit user language wins |
| 55 | Provider account in browser | Known local engine account or validated remote HTTPS origin |
| 56 | Missing Beautiful Soup fallback | Optional import; web tools fail cleanly, app stays available |
| 57 | Window-close cleanup | Closing handler interrupts request and kills command tree, including unlimited mode |
| 58 | Corrupt database recovery | Preserve damaged JSON; recover prior valid state, else clean profile |

## Additional chat requirements

- User-selected Veyq branding, original dark/light logos, dark Desktop icon and renamed repository.
- Native application launch fix and real-window visual QA; 3 illustrative README screenshots from a separate profile.
- Windows observation/input tools, shell/file/web/GitHub tools and actual autonomous repository clone/configuration verification.
- GitHub actions accept any repository; optional default only. Application update trust remains pinned to the publisher.
- Maximum steps and command timeout accept 0 to disable the limit; new profiles default to 0.
- English first run and persisted English/Italian/Spanish/French translations, including token sections.
- Internal memory, project context, linked folders, file/document attachments, queued follow-ups, essential questions and Stop.
- Both user and assistant messages aligned left; sanitized Markdown and source-code highlighting.
- Publisher-signed automatic updates, rollback, user-data preservation, credential vault and metadata-only audit.

## Verification boundaries

Automated backend/UI tests and a real local-model repository task have been performed. Native visual QA checks Veyq itself. The Windows input controller is tested against controlled doubles for observation/approval failures; it has not been exhaustively exercised against third-party applications. The missing-engine installer has not been run on the already configured development PC. These distinctions prevent illustrative screenshots and unit tests from being presented as stronger evidence than they provide.

The Veyq name has an unrelated existing software use at https://veyq.app/; exclusivity was not established. Mandatory upstream copyright and licenses are retained. Python is a prerequisite; dependencies are installed automatically, but Python itself is not silently installed.
