const params = new URLSearchParams(window.location.search);
const docId = params.get("id");

const userEmailEl = document.getElementById("user-email");
const logoutBtn = document.getElementById("logout-btn");
const docTitle = document.getElementById("doc-title");
const docMeta = document.getElementById("doc-meta");
const textPanel = document.getElementById("text-panel");
const downloadLink = document.getElementById("download-link");
const deleteBtn = document.getElementById("delete-btn");
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const answerArea = document.getElementById("answer-area");

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderTextSkeleton() {
  const lines = Array.from({ length: 8 }, () => `<div class="skeleton skeleton-text-block"></div>`).join("");
  textPanel.innerHTML = lines;
}

async function requireAuth() {
  const res = await fetch("/api/auth/me", { credentials: "include" });
  if (!res.ok) {
      window.location.replace("/index.html");
    return null;
  }
  const data = await res.json();
  userEmailEl.textContent = data.user.email;
  return data.user;
}

async function loadDocument() {
  if (!docId) {
    showToast("No document specified", "error");
    return;
  }
  renderTextSkeleton();
  const res = await fetch(`/api/documents/${docId}`, { credentials: "include" });
  if (res.status === 401) {
       window.location.replace("/index.html");
    return;
  }
  if (res.status === 404) {
    docTitle.textContent = "Not found";
    textPanel.textContent = "This document doesn't exist, or doesn't belong to you.";
    return;
  }
  const data = await res.json();
  const doc = data.document;

  docTitle.textContent = doc.filename;
  docMeta.textContent = `${doc.page_count} pages · ${formatSize(doc.file_size)} · uploaded ${formatDate(doc.uploaded_at)}`;
  downloadLink.href = `/api/documents/${doc.id}/download`;

  textPanel.innerHTML = doc.pages
    .map((p) => `<span class="page-marker">Page ${p.page}</span>${escapeHtml(p.text || "(no extractable text on this page)")}`)
    .join("\n");
}

deleteBtn.addEventListener("click", async () => {
  if (!confirm("Delete this document? This cannot be undone.")) return;
  const res = await fetch(`/api/documents/${docId}`, { method: "DELETE", credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    showToast(data.error || "Could not delete document", "error");
    return;
  }
  showToast("Document deleted", "success");
     window.location.replace("/index.html");
});

askBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) return;

  askBtn.disabled = true;
  askBtn.innerHTML = `<span class="btn-spinner"></span>Asking…`;
  answerArea.innerHTML = `<div class="answer-block"><span class="spinner"></span>Searching this document…</div>`;

  try {
    const res = await fetch("/api/rag/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ question, document_id: docId }),
    });
    const data = await res.json();

    if (!res.ok) {
      answerArea.innerHTML = `<div class="answer-block">${escapeHtml(data.error || "Something went wrong")}</div>`;
      showToast(data.error || "Could not get an answer", "error");
      return;
    }

    const sourcesHtml = (data.sources || [])
      .map((s) => `<div class="src">p.${s.page} · score ${s.score} — "${escapeHtml(s.excerpt)}${s.excerpt.length >= 300 ? "…" : ""}"</div>`)
      .join("");

    answerArea.innerHTML = `
      <div class="answer-block">${escapeHtml(data.answer)}</div>
      ${sourcesHtml ? `<div class="sources-list"><strong>Retrieved chunks:</strong>${sourcesHtml}</div>` : ""}
    `;
  } catch (err) {
    answerArea.innerHTML = `<div class="answer-block">Could not reach the server. Please try again.</div>`;
    showToast("Could not reach the server. Please try again.", "error");
  } finally {
    askBtn.disabled = false;
    askBtn.textContent = "Ask";
  }
});

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") askBtn.click();
});

logoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
     window.location.replace("/index.html");
});

(async function init() {
  const user = await requireAuth();
  if (user) loadDocument();
})();

// See the matching comment in library.js: without this, navigating back to
// this page after logout can show a stale, still-logged-in DOM snapshot
// from the browser's back/forward cache instead of re-checking auth.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    window.location.reload();
  }
});
