"use strict";
const $ = (id) => document.getElementById(id);
const ui = (text) => window.VeyqI18N.text(text);
let projects = [],
  questionId = "",
  infoModel = "",
  modelBusy = false;
let api,
  sessionId = "",
  settings = {},
  sessions = [],
  busy = false,
  polling = false;
let lastSeq = 0,
  streamNode = null,
  streamText = "",
  approvalId = "",
  updateReady = false;
let explorerPath = ".",
  selectedFile = "",
  previewLine = 1,
  previewTotal = 0;
const modalFocus = new Map();
const modes = {
  always: "Chiedi sempre",
  auto: "Approva per me",
  full: "Accesso completo",
};
function toast(text) {
  $("toast").textContent = ui(text);
  $("toast").style.display = "block";
  setTimeout(() => ($("toast").style.display = "none"), 6500);
}
async function call(name, ...args) {
  if (!api) throw Error("Apri l’app con Veyq.bat per usare il motore locale.");
  return await api[name](...args);
}
function action(id, fn) {
  $(id).addEventListener("click", () =>
    Promise.resolve()
      .then(fn)
      .catch((e) => toast(e.message || e)),
  );
}
function open(id) {
  if (!$(id).classList.contains("open"))
    modalFocus.set(id, document.activeElement);
  $(id).classList.add("open");
  const focus =
    id === "approvalModal"
      ? $("deny")
      : $(id).querySelector("input, select, button");
  focus?.focus();
}
function close(id) {
  $(id).classList.remove("open");
  modalFocus.get(id)?.focus();
  modalFocus.delete(id);
}
function setBusy(value, state) {
  busy = value;
  updateSendButton();

  $("state").textContent = state || (value ? "In esecuzione" : "Pronto");
  $("status").classList.toggle("busy", value);
  for (const id of [
    "newChat",
    "chooseFolder",
    "exploreFiles",
    "settingsButton",
    "newProject",
    "projectAssignment",
  ])
    $(id).disabled = value;
}
function updateSendButton() {
  const follow = busy && $("prompt").value.trim();
  $("send").textContent = ui(
    busy ? (follow ? "Send follow-up ↑" : "Ferma") : "Invia ↑",
  );
  $("send").classList.toggle("danger", busy && !follow);
  $("send").classList.toggle("follow-up", !!follow);
}
function codeBlock(parent, text, language) {
  const wrap = document.createElement("div");
  wrap.className = "codebox";
  const btn = document.createElement("button");
  btn.className = "copy";
  btn.textContent = "Copia " + (language || "");
  btn.addEventListener("click", () =>
    navigator.clipboard
      .writeText(text)
      .then(() => toast("Copiato"))
      .catch(() => toast("Seleziona il testo e usa Ctrl+C")),
  );
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.textContent = text;
  pre.append(code);
  wrap.append(btn, pre);
  parent.append(wrap);
}
// Markdown is sanitized locally before it enters the DOM. No model HTML,
// embedded images, scripts, forms or bridge calls are allowed.
function renderText(parent, text) {
  const box = parent.closest(".message");
  if (box) box.dataset.raw = String(text);
  const dirty = marked.parse(String(text), { breaks: true, gfm: true });
  const clean = DOMPurify.sanitize(dirty, {
    RETURN_DOM_FRAGMENT: true,
    ALLOWED_TAGS: [
      "p",
      "br",
      "hr",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "ul",
      "ol",
      "li",
      "strong",
      "em",
      "del",
      "blockquote",
      "pre",
      "code",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "a",
    ],
    ALLOWED_ATTR: ["href", "title", "class"],
    ALLOW_DATA_ATTR: false,
  });
  parent.replaceChildren(clean);
  for (const a of parent.querySelectorAll("a")) {
    const href = a.getAttribute("href") || "";
    a.removeAttribute("href");
    a.setAttribute("role", "link");
    a.tabIndex = 0;
    const follow = () =>
      call("open_external", href).catch((e) => toast(e.message));
    a.addEventListener("click", follow);
    a.addEventListener("keydown", (e) => {
      if (e.key === "Enter") follow();
    });
  }
  for (const code of parent.querySelectorAll("pre code")) {
    const raw = code.textContent;
    try {
      hljs.highlightElement(code);
    } catch {}
    const button = document.createElement("button");
    button.className = "copy";
    button.textContent = ui("Copy");
    button.addEventListener("click", () =>
      navigator.clipboard
        .writeText(raw)
        .then(() => toast("Copied"))
        .catch((e) => toast(e.message)),
    );
    code.parentElement.prepend(button);
  }
}
function message(role, text, historyIndex = null) {
  $("welcome").hidden = true;
  const box = document.createElement("article");
  box.className = "message " + role;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "Tu" : "Veyq";
  const body = document.createElement("div");
  body.className = "message-body";
  box.dataset.raw = text;
  if (historyIndex !== null) box.dataset.historyIndex = historyIndex;
  renderText(body, text);
  box.append(label, body);
  const actions = document.createElement("div");
  actions.className = "message-actions";
  const copy = document.createElement("button");
  copy.textContent = ui("Copy Markdown");
  copy.addEventListener("click", () =>
    navigator.clipboard
      .writeText(box.dataset.raw)
      .then(() => {
        copy.textContent = ui("Copied!");
        setTimeout(() => (copy.textContent = ui("Copy Markdown")), 2000);
      })
      .catch((e) => toast(e.message)),
  );
  actions.append(copy);
  if (role === "assistant") {
    const regenerate = document.createElement("button");
    regenerate.textContent = ui("Regenerate");
    regenerate.addEventListener("click", async () => {
      if (busy || box.dataset.historyIndex === undefined) return;
      if (
        !confirm(
          ui(
            "Regenerate this response? Later chat messages will be removed. Executed actions will remain applied.",
          ),
        )
      )
        return;
      try {
        await call(
          "regenerate",
          sessionId,
          Number(box.dataset.historyIndex),
          true,
        );
        await loadSession(sessionId);
        setBusy(true);
      } catch (e) {
        toast(e.message);
      }
    });
    actions.append(regenerate);
  }
  box.append(actions);
  $("messages").append(box);
  scrollBottom();
  return body;
}
function scrollBottom() {
  const el = $("messages");
  el.scrollTop = el.scrollHeight;
}
function renderPlan(steps) {
  $("plan").replaceChildren();
  if (!steps?.length) {
    $("plan").hidden = true;
    return;
  }
  $("plan").hidden = false;
  const title = document.createElement("div");
  title.className = "eyebrow";
  title.textContent = "Piano";
  $("plan").append(title);
  steps.forEach((s) => {
    const item = document.createElement("div");
    item.className = "plan-item " + s.status;
    item.textContent =
      (s.status === "completed"
        ? "✓ "
        : s.status === "in_progress"
          ? "◉ "
          : "○ ") + s.step;
    $("plan").append(item);
  });
}
function activity(title, data, kind = "info") {
  $("activityEmpty")?.remove();
  const item = document.createElement("details");
  item.className = "log-" + kind;
  const summary = document.createElement("summary");
  summary.textContent = title;
  const pre = document.createElement("pre");
  pre.textContent =
    typeof data === "string" ? data : JSON.stringify(data, null, 2);
  item.append(summary, pre);
  $("activity").append(item);
  while ($("activity").children.length > 150) $("activity").firstChild.remove();
  $("activity").scrollTop = $("activity").scrollHeight;
}
async function refreshSessions() {
  sessions = await call("get_sessions", $("search").value);
  projects = await call("get_projects");
  renderSessions();
}
function renderSessions() {
  const host = $("sessions");
  host.replaceChildren();
  for (const group of [{ id: "", name: ui("No project") }, ...projects]) {
    const items = sessions.filter((s) => (s.project_id || "") === group.id);
    if (!items.length) continue;
    const details = document.createElement("details");
    details.className = "project-group";
    details.open =
      !!$("search").value ||
      localStorage.getItem("group-" + group.id) !== "closed";
    details.addEventListener("toggle", () =>
      localStorage.setItem(
        "group-" + group.id,
        details.open ? "open" : "closed",
      ),
    );
    const summary = document.createElement("summary");
    summary.textContent = group.name + " · " + items.length;
    details.append(summary);
    for (const s of items) {
      const row = document.createElement("div");
      row.className = "session-row";
      const btn = document.createElement("button");
      btn.className = "session" + (s.id === sessionId ? " active" : "");
      btn.disabled = busy;
      const title = document.createElement("span");
      title.textContent = s.title;
      btn.addEventListener("mouseenter", () => {
        const distance = title.scrollWidth - title.clientWidth;
        btn.classList.toggle("marquee", distance > 0);
        title.style.setProperty(
          "--title-overflow",
          `-${Math.max(0, distance)}px`,
        );
      });
      btn.append(title);
      btn.title = s.title;
      btn.addEventListener("click", () =>
        loadSession(s.id).catch((e) => toast(e.message)),
      );
      const more = document.createElement("button");
      more.className = "session-more";
      more.textContent = "⋯";
      more.title = ui("More chat actions");
      more.disabled = busy;
      const menu = document.createElement("div");
      menu.className = "session-menu";
      menu.hidden = true;
      for (const [label, fn] of [
        [
          "Rename",
          async () => {
            const name = prompt(ui("Chat name:"), s.title);
            if (name) {
              await call("rename_session", s.id, name);
              await refreshSessions();
            }
          },
        ],
        [
          "Delete chat",
          async () => {
            if (confirm(ui("Delete this local chat?"))) {
              await call("delete_session", s.id);
              if (s.id === sessionId) await newChat();
              else await refreshSessions();
            }
          },
        ],
      ]) {
        const action = document.createElement("button");
        action.textContent = ui(label);
        action.addEventListener("click", () =>
          fn().catch((e) => toast(e.message)),
        );
        menu.append(action);
      }
      more.addEventListener("click", () => {
        menu.hidden = !menu.hidden;
      });
      row.append(btn, more, menu);
      details.append(row);
    }
    host.append(details);
  }
}
async function loadSession(id) {
  if (busy) return;
  const s = await call("get_session", id);
  if (!s) return;
  sessionId = id;
  $("messages")
    .querySelectorAll(".message")
    .forEach((n) => n.remove());
  $("welcome").hidden = s.history.some((m) => m.role === "user");
  for (const [index, m] of s.history.entries()) {
    if (["user", "assistant"].includes(m.role) && m.content)
      message(m.role, m.content, index);
  }
  showWorkspace(s.workspace || settings.workspace);
  $("projectAssignment").replaceChildren();
  for (const project of [{ id: "", name: ui("No project") }, ...projects]) {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    $("projectAssignment").append(option);
  }
  $("projectAssignment").value = s.project_id || "";
  renderPlan(s.plan);
  streamNode = null;
  streamText = "";
  renderSessions();
}
async function newChat() {
  sessionId = await call("create_session");
  await refreshSessions();
  await loadSession(sessionId);
}
function header() {
  $("mode").textContent = modes[settings.permission];
  $("online").textContent = settings.network ? "Rete attiva" : "Solo locale";
  $("modelBadge").textContent = settings.model;
}
function showWorkspace(path) {
  $("workspace").textContent =
    String(path).split(/[\\/]/).filter(Boolean).at(-1) || path;
  $("workspace").title = path;
}
async function send() {
  const text = $("prompt").value.trim();
  if (busy && !text) {
    await call("stop_run");
    setBusy(true, "Interruzione…");
    return;
  }
  if (!text) return;
  if (busy) {
    await call("follow_up", sessionId, text);
    message("user", text);
    $("prompt").value = "";
    updateSendButton();
    toast("Follow-up queued. It will be applied after the current tool step.");
    return;
  }
  if (!sessionId) await newChat();
  await call("start_run", sessionId, text);
  $("prompt").value = "";
  message("user", text);
  streamText = "";
  streamNode = null;
  setBusy(true);
  renderSessions();
}
function showApproval(data) {
  if (approvalId === data.id) return;
  approvalId = data.id;
  $("approvalReason").textContent = data.reason;
  $("approvalTool").textContent = data.tool;
  $("approvalArgs").textContent = JSON.stringify(data.arguments, null, 2);
  $("approvalDiff").hidden = !data.diff;
  $("approvalDiff").textContent = data.diff || "";
  $("approvalWorkspace").textContent = data.workspace;
  open("approvalModal");
}
async function decide(allow) {
  const id = approvalId;
  if (!id) return;
  await call("resolve_approval", id, allow);
  approvalId = "";
  close("approvalModal");
}
async function poll() {
  if (polling || !api) return;
  polling = true;
  try {
    const result = await call("get_events", lastSeq);
    for (const e of result.events) {
      lastSeq = e.seq;
      const d = e.data;
      if (e.session_id && e.session_id !== sessionId) continue;
      switch (e.type) {
        case "text":
          if (!streamNode) {
            streamNode = message("assistant", "");
            streamText = "";
          }
          streamText += d.text;
          renderText(streamNode, streamText);
          scrollBottom();
          break;
        case "message":
          if (d.message.content) {
            if (streamNode) {
              renderText(streamNode, d.message.content);
            } else
              message("assistant", d.message.content, d.history_index ?? null);
          }
          if (streamNode && d.history_index !== undefined)
            streamNode.closest(".message").dataset.historyIndex =
              d.history_index;
          streamNode = null;
          streamText = "";
          break;
        case "tool_start":
          activity(
            "↗ " + d.tool,
            d.arguments,
            d.tool === "save_memory" ? "memory" : "running",
          );
          $("state").textContent = d.tool;
          break;
        case "tool_result":
          activity(
            (d.result?.ok === false ? "⚠ " : "✓ ") + d.tool,
            d.result,
            d.result?.ok === false
              ? "error"
              : d.tool === "save_memory"
                ? "memory"
                : "success",
          );
          break;
        case "plan":
          renderPlan(d.steps);
          break;
        case "turn":
          $("state").textContent =
            ui("Step") + ` ${d.step} / ${d.max_steps || "∞"}`;
          break;
        case "approval":
          showApproval(d);
          break;
        case "error":
          toast(d.text);
          activity("Errore", d.text);
          break;
        case "notice":
          toast(d.text);
          break;
        case "model":
          $("modelStatus").textContent =
            ui(d.status || "Download progress") +
            (d.total
              ? " " + Math.round((100 * (d.completed || 0)) / d.total) + "%"
              : "");
          $("catalogProgress").textContent = $("modelStatus").textContent;
          break;
        case "question":
          showQuestion(d);
          break;
        case "done":
          streamNode = null;
          streamText = "";
          close("approvalModal");
          approvalId = "";
          close("questionModal");
          questionId = "";
          await refreshSessions();
          break;
      }
    }
    setBusy(
      result.busy,
      result.busy
        ? result.state === "question"
          ? ui("Waiting for your answer")
          : result.state === "approval"
            ? "Autorizzazione richiesta"
            : result.state === "stopping"
              ? "Interruzione…"
              : $("state").textContent
        : {
            completed: "Completato",
            failed: "Errore",
            cancelled: "Interrotto",
            limit: "Limite raggiunto",
          }[result.state] || "Pronto",
    );
    if (result.approval) showApproval(result.approval);
    if (result.question) showQuestion(result.question);
    modelBusy = !!result.model_busy;
    if (!result.busy && updateReady) {
      updateReady = false;
      await call("apply_update");
    }
  } catch (e) {
    toast(e.message);
  } finally {
    polling = false;
  }
}
async function showSettings() {
  settings = await call("get_settings");
  $("language").value = settings.lang;
  loadInstalledModels().catch((e) => toast(e.message));
  for (const [id, key] of [
    ["provider", "provider"],
    ["endpoint", "url"],
    ["model", "model"],
    ["permission", "permission"],
    ["maxSteps", "max_steps"],
    ["timeout", "command_timeout"],
    ["githubRepo", "github_repo"],
  ])
    $(id).value = settings[key];
  $("network").checked = settings.network;
  $("vision").checked = !!settings.vision;
  $("autoUpdate").checked = !!settings.auto_update;
  $("providerToken").value = "";
  $("githubToken").value = "";
  $("providerToken").placeholder = settings.has_provider_token
    ? ui("Saved in vault; leave blank to keep it")
    : ui("Token (optional for the local engine)");
  $("githubToken").placeholder = settings.has_github_token
    ? ui("Saved in vault; leave blank to keep it")
    : ui("Token with access to the repositories you need");
  $("fullConsent").checked = false;
  $("fullConfirm").style.display =
    settings.permission === "full" ? "flex" : "none";
  $("dataDir").textContent = settings.data_dir;
  open("settingsModal");
}
async function saveSettings() {
  await call("save_settings", {
    lang: $("language").value,
    provider: $("provider").value,
    url: $("endpoint").value,
    model: $("model").value,
    permission: $("permission").value,
    network: $("network").checked,
    vision: $("vision").checked,
    auto_update: $("autoUpdate").checked,
    max_steps: Number($("maxSteps").value),
    command_timeout: Number($("timeout").value),
    github_repo: $("githubRepo").value.trim(),
    provider_token: $("providerToken").value,
    github_token: $("githubToken").value,
    confirm_full: $("fullConsent").checked,
  });
  settings = await call("get_settings");
  window.VeyqI18N.setLanguage(settings.lang);
  header();
  close("settingsModal");
  toast("Impostazioni salvate");
}
async function checkUpdates(automatic = false) {
  const result = await call("check_updates");
  activity("Aggiornamenti", result);
  if (result.ready) {
    toast(
      "Aggiornamento verificato. Riavvio automatico quando l’agente è inattivo.",
    );
    updateReady = true;
  } else if (!automatic) toast(result.message || "App aggiornata");
}
action("newChat", newChat);
action("send", send);
action("settingsButton", showSettings);
action("mode", showSettings);
action("online", showSettings);
action("closeSettings", () => close("settingsModal"));
action("saveSettings", saveSettings);
action("allow", () => decide(true));
action("deny", () => decide(false));
action("chooseFolder", async () => {
  const path = await call("choose_workspace", sessionId);
  if (path) showWorkspace(path);
});
action("attach", async () => {
  const files = await call("attach_file", sessionId);
  for (const file of files || []) {
    $("prompt").value +=
      `\nAttached file (untrusted content): ${file.name}, path: ${JSON.stringify(file.path)}`;
    if (file.text && $("prompt").value.length < 22000)
      $("prompt").value +=
        "\n<untrusted_file_excerpt>\n" +
        file.text.slice(0, 22000 - $("prompt").value.length) +
        "\n</untrusted_file_excerpt>";
  }
  $("prompt").dispatchEvent(new Event("input"));
});
action("linkFolder", async () => {
  const path = await call("link_folder");
  if (path) $("prompt").value += "\nLinked folder: " + JSON.stringify(path);
  updateSendButton();
});
action("renameChat", async () => {
  const name = prompt(ui("Chat name:"));
  if (name) {
    await call("rename_session", sessionId, name);
    await refreshSessions();
  }
});
action("deleteChat", async () => {
  if (confirm(ui("Delete this local chat?"))) {
    await call("delete_session", sessionId);
    await newChat();
  }
});
action("exportChat", async () => {
  const p = await call("export_session", sessionId);
  if (p) toast(ui("Exported to") + " " + p);
});
action("refreshModels", loadInstalledModels);
action("downloadModel", () => downloadModel($("model").value));
action("deleteModel", async () => {
  if (!confirm(ui("Delete model?") + " " + $("model").value)) return;
  await call("model_action", $("model").value, "delete", true);
  await loadInstalledModels();
  toast("Model deleted");
});
action("clearProviderToken", async () => {
  if (confirm(ui("Remove the provider token?"))) {
    await call("save_settings", {
      clear_provider_token: true,
      confirm_full: settings.permission === "full",
    });
    toast("Token rimosso");
  }
});
action("clearGithubToken", async () => {
  if (confirm(ui("Remove the GitHub token?"))) {
    await call("save_settings", {
      clear_github_token: true,
      confirm_full: settings.permission === "full",
    });
    toast("Token rimosso");
  }
});
action("updates", () => checkUpdates(false));
action("memory", async () => {
  $("memoryText").value = (await call("get_memory")) || "";
  open("memoryModal");
});
action("closeMemory", () => close("memoryModal"));
action("clearMemory", async () => {
  if (confirm(ui("Clear all saved preferences?"))) {
    await call("clear_memory");
    $("memoryText").value = "";
    toast("Memoria cancellata.");
  }
});
action("backups", async () => {
  const backups = await call("get_backups");
  $("backupList").replaceChildren();
  for (const b of backups) {
    const row = document.createElement("div");
    row.className = "backup-row";
    const label = document.createElement("span");
    label.textContent =
      b.path + " · " + new Date(b.time * 1000).toLocaleString();
    const btn = document.createElement("button");
    btn.textContent = "Ripristina";
    btn.addEventListener("click", async () => {
      if (
        confirm(
          ui("Restore") +
            " " +
            b.path +
            "? " +
            ui("The current version will be saved in a new backup."),
        )
      ) {
        try {
          await call("restore_backup", b.id, true);
          toast("File ripristinato");
        } catch (e) {
          toast(e.message);
        }
      }
    });
    row.append(btn, label);
    $("backupList").append(row);
  }
  if (!backups.length)
    $("backupList").textContent =
      "I backup appariranno dopo le prime modifiche ai file.";
  open("backupsModal");
});
action("closeBackups", () => close("backupsModal"));

async function browseFiles(path = ".") {
  if (busy) throw Error("Attendi che l’attività sia terminata.");
  $("fileList").textContent = ui("Reading the folder…");
  const result = await call("browse_project", sessionId, path);
  if (!result.ok) throw Error(result.error);
  explorerPath = path;
  $("explorerPath").textContent = path;
  $("explorerUp").disabled = path === ".";
  $("fileList").replaceChildren();
  const entries = [...result.result].sort(
    (a, b) =>
      Number(b.kind === "dir") - Number(a.kind === "dir") ||
      a.name.localeCompare(b.name),
  );
  for (const entry of entries) {
    const button = document.createElement("button");
    button.className = "file-entry";
    button.textContent =
      (entry.kind === "dir" ? "▸ " : entry.kind === "link" ? "↗ " : "· ") +
      entry.name;
    button.title = entry.name;
    const relative = path === "." ? entry.name : path + "/" + entry.name;
    button.addEventListener("click", () =>
      (entry.kind === "dir"
        ? browseFiles(relative)
        : previewFile(relative)
      ).catch((e) => toast(e.message)),
    );
    $("fileList").append(button);
  }
  if (!entries.length) $("fileList").textContent = ui("Empty folder.");
}
async function previewFile(path, line = 1) {
  if (busy) throw Error("Attendi che l’attività sia terminata.");
  $("filePreview").textContent = ui("Reading the file…");
  const result = await call("preview_project_file", sessionId, path, line);
  if (!result.ok) {
    $("filePreview").textContent = result.error;
    throw Error(result.error);
  }
  selectedFile = path;
  previewLine = line;
  previewTotal = result.result.total_lines;
  $("filePreviewTitle").textContent =
    path + " · " + previewTotal + " " + ui("lines");
  $("filePreview").textContent = result.result.content || ui("Empty file.");
  $("previousLines").disabled = line === 1;
  $("nextLines").disabled = line + 299 >= previewTotal;
  $("askAboutFile").disabled = false;
}
action("exploreFiles", async () => {
  selectedFile = "";
  $("askAboutFile").disabled = true;
  $("filePreview").textContent = ui("Select a file to read its contents.");
  $("filePreviewTitle").textContent = "Anteprima";
  $("previousLines").disabled = true;
  $("nextLines").disabled = true;
  open("explorerModal");
  await browseFiles();
});
action("closeExplorer", () => close("explorerModal"));
action("explorerRoot", () => browseFiles());
action("explorerUp", () =>
  browseFiles(explorerPath.split("/").slice(0, -1).join("/") || "."),
);
action("previousLines", () =>
  previewFile(selectedFile, Math.max(1, previewLine - 300)),
);
action("nextLines", () => previewFile(selectedFile, previewLine + 300));
action("askAboutFile", () => {
  $("prompt").value +=
    ($("prompt").value ? "\n" : "") +
    ui("Read the file") +
    " " +
    JSON.stringify(selectedFile) +
    " " +
    ui("in the project and") +
    " ";
  close("explorerModal");
  $("prompt").focus();
});
document.addEventListener("keydown", (e) => {
  const dialogs = [...document.querySelectorAll(".modal.open")];
  const current =
    dialogs.find((d) => d.id === "approvalModal") || dialogs.at(-1);
  if (e.key === "Escape" && current) {
    e.preventDefault();
    if (current.id === "questionModal") {
      /* Keep essential questions available; use Stop activity to cancel. */
    } else if (current.id === "approvalModal")
      decide(false).catch((error) => toast(error.message));
    else close(current.id);
  }
  if (e.key === "Tab" && current) {
    const controls = [
      ...current.querySelectorAll(
        "button:not(:disabled), input, select, textarea",
      ),
    ].filter((n) => n.offsetParent !== null);
    if (!controls.length) return;
    const first = controls[0],
      last = controls.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
  if (e.ctrlKey && e.key.toLowerCase() === "n" && !busy && !current) {
    e.preventDefault();
    newChat().catch((error) => toast(error.message));
  }
});
let searchTimer;
$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(
    () => refreshSessions().catch((e) => toast(e.message)),
    150,
  );
});
$("prompt").addEventListener("input", () => {
  $("prompt").style.height = "auto";
  $("prompt").style.height = Math.min(160, $("prompt").scrollHeight) + "px";
  updateSendButton();
});
$("permission").addEventListener("change", () => {
  $("fullConfirm").style.display =
    $("permission").value === "full" ? "flex" : "none";
  $("fullConsent").checked = false;
});
$("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send().catch((e) => toast(e.message));
  }
});
for (const button of document.querySelectorAll(".suggestion"))
  button.addEventListener("click", () => {
    $("prompt").value = ui(button.dataset.prompt);
    $("prompt").focus();
  });
window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
  try {
    settings = await call("get_settings");
    window.VeyqI18N.setLanguage(settings.lang);
    if (settings.recovery_notice) toast(settings.recovery_notice);
    header();
    await refreshSessions();
    if (sessions.length) await loadSession(sessions[0].id);
    else await newChat();
    setInterval(poll, 350);
    if (!settings.setup_completed) {
      await call("finish_setup");
      try {
        const r = await call("get_models");
        $("setupStatus").textContent = r.ok
          ? ui("Installed models") + ": " + r.models.join(", ")
          : ui(
              "The local engine is unavailable. Start it, install it with the setup button, or choose a remote API.",
            );
      } catch {}
      open("setupModal");
    }
    if (settings.auto_update)
      setTimeout(
        () =>
          checkUpdates(true).catch((e) => activity("Aggiornamenti", e.message)),
        2500,
      );
    setInterval(() => {
      if (settings.auto_update && !busy)
        checkUpdates(true).catch((e) => activity("Aggiornamenti", e.message));
    }, 3600000);
  } catch (e) {
    toast(e.message);
  }
});

function showQuestion(data) {
  if (questionId === data.id) return;
  questionId = data.id;
  $("questionText").textContent = data.question;
  $("questionAnswer").value = "";
  $("questionOptions").replaceChildren();
  for (const option of data.options || []) {
    const btn = document.createElement("button");
    btn.textContent = option;
    btn.addEventListener("click", () => {
      $("questionAnswer").value = option;
      $("questionAnswer").focus();
    });
    $("questionOptions").append(btn);
  }
  open("questionModal");
}
async function loadInstalledModels() {
  const r = await call("get_models");
  if (!r.ok) throw Error(r.error);
  $("installedModels").replaceChildren();
  $("models").replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = ui("Choose a model");
  $("installedModels").append(empty);
  for (const name of r.models) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    $("installedModels").append(opt);
    $("models").append(opt.cloneNode(true));
  }
  $("installedModels").value = $("model").value || settings.model;
}
async function showModelInfo(name) {
  const m = await call("get_model_info", name);
  infoModel = name;
  $("modelInfoTitle").textContent = name;
  $("modelInfoContent").replaceChildren();
  const list = document.createElement("dl");
  list.className = "model-facts";
  const yes = (v) => ui(v == null ? "Unknown" : v ? "Yes" : "No");
  for (const [label, value] of [
    ["Weight", ui(m.weight)],
    ["Capability level", ui(m.capability || "Unknown")],
    ["Optional GPU memory (minimum)", m.vram_min_gb],
    ["Estimated download", m.download_gb],
    ["Minimum RAM", m.ram_min_gb],
    ["Recommended RAM", m.ram_recommended_gb],
    ["Optional GPU memory", m.vram_recommended_gb],
    [
      "Tool calls",
      yes(
        m.installed_capabilities
          ? m.installed_capabilities.includes("tools")
          : m.tools,
      ),
    ],
    [
      "Vision",
      yes(
        m.installed_capabilities
          ? m.installed_capabilities.includes("vision")
          : m.vision,
      ),
    ],
  ]) {
    const key = document.createElement("dt"),
      val = document.createElement("dd");
    key.textContent = ui(label);
    val.textContent =
      value == null
        ? ui("Unknown")
        : String(value) + (typeof value === "number" ? " GB" : "");
    list.append(key, val);
  }
  $("modelInfoContent").append(list);
  for (const text of [ui("Suggested uses") + ": " + ui(m.uses), ui(m.note)]) {
    const p = document.createElement("p");
    p.className = "intro";
    p.textContent = text;
    $("modelInfoContent").append(p);
  }
  $("modelSource").hidden = !m.source;
  open("modelInfoModal");
}
async function showCatalog() {
  const r = await call("get_model_catalog");
  $("catalogList").replaceChildren();
  $("hardwareInfo").textContent =
    ui("Detected RAM") +
    ": " +
    (r.hardware.ram_gb ?? ui("Unknown")) +
    " GB · " +
    ui("Free disk") +
    ": " +
    r.hardware.disk_free_gb +
    " GB";
  for (const m of r.models) {
    const row = document.createElement("div");
    row.className = "model-card";
    const label = document.createElement("div"),
      name = document.createElement("b"),
      uses = document.createElement("p");
    name.textContent = m.name;
    uses.className = "sub";
    uses.textContent =
      ui(m.weight) + " · ≈" + m.download_gb + " GB · " + ui(m.uses);
    label.append(name, uses);
    const info = document.createElement("button");
    info.textContent = "ⓘ";
    info.title = ui("Model details");
    info.addEventListener("click", () =>
      showModelInfo(m.name).catch((e) => toast(e.message)),
    );
    const download = document.createElement("button");
    download.textContent = ui("Download");
    download.disabled = settings.provider !== "local";
    download.addEventListener("click", () =>
      downloadModel(m.name).catch((e) => toast(e.message)),
    );
    row.append(label, info, download);
    $("catalogList").append(row);
  }
  open("catalogModal");
}
async function downloadModel(name) {
  if (modelBusy) throw Error(ui("Wait for the current download to finish."));
  if (
    !confirm(
      ui(
        "Download this model? The local engine will contact its online catalog.",
      ) +
        " " +
        name,
    )
  )
    return;
  $("cancelDownload").hidden = false;
  $("catalogProgress").textContent = ui("Downloading…");
  modelBusy = true;
  try {
    const r = await call("model_action", name, "pull", true);
    if (r.cancelled) {
      toast("Download cancelled");
      return;
    }
    $("model").value = name;
    await loadInstalledModels();
    toast("Model installed. Select it in Settings to use it.");
  } finally {
    modelBusy = false;
    $("cancelDownload").hidden = true;
  }
}
action("cancelDownload", () => call("cancel_model_action"));
action("openCatalog", showCatalog);
action("closeCatalog", () => close("catalogModal"));
action("modelInfo", () => showModelInfo($("model").value));
action("closeModelInfo", () => close("modelInfoModal"));
action("modelSource", () => call("open_model_source", infoModel));
action("providerAccount", () => call("open_provider_account"));
async function setupEngine() {
  if (
    !confirm(
      ui(
        "Install or start the optional local engine? The official signed installer will be used if needed.",
      ),
    )
  )
    return;
  $("setupStatus").textContent = ui("Setting up the local engine…");
  const r = await call("setup_local_engine", true);
  toast(r.message);
  await loadInstalledModels();
}
action("setupEngine", setupEngine);
action("setupInstall", setupEngine);
action("setupSettings", () => {
  close("setupModal");
  return showSettings();
});
action("setupCatalog", () => {
  close("setupModal");
  return showCatalog();
});
action("closeSetup", () => close("setupModal"));
for (const [id, name] of [
  ["setupSmall", "qwen2.5:7b"],
  ["setupBalanced", "llama3.1:8b"],
  ["setupLarge", "qwen3:14b"],
])
  action(id, () => downloadModel(name));
action("newProject", () => {
  $("projectName").value = "";
  open("projectModal");
});
action("closeProject", () => close("projectModal"));
action("createProject", async () => {
  const p = await call("create_project", $("projectName").value);
  await call("assign_project", sessionId, p.id);
  await refreshSessions();
  await loadSession(sessionId);
  close("projectModal");
});
$("projectAssignment").addEventListener("change", () =>
  call("assign_project", sessionId, $("projectAssignment").value)
    .then(() => loadSession(sessionId))
    .then(refreshSessions)
    .catch((e) => toast(e.message)),
);
$("language").addEventListener("change", async () => {
  try {
    const lang = $("language").value;
    await call("set_language", lang);
    settings.lang = lang;
    window.VeyqI18N.setLanguage(lang);
    header();
    renderSessions();
    updateSendButton();
  } catch (e) {
    toast(e.message);
  }
});
$("installedModels").addEventListener("change", () => {
  if ($("installedModels").value) $("model").value = $("installedModels").value;
});
action("submitAnswer", async () => {
  await call("answer_question", questionId, $("questionAnswer").value);
  questionId = "";
  close("questionModal");
});
action("saveMemory", async () => {
  await call("save_memory", $("memoryText").value);
  toast("Memory saved");
  close("memoryModal");
});
action("toggleActivity", () =>
  document
    .querySelector(".shell")
    .classList.toggle(
      matchMedia("(max-width:950px)").matches
        ? "activity-mobile-open"
        : "activity-hidden",
    ),
);

action("stopQuestion", () => call("stop_run"));
