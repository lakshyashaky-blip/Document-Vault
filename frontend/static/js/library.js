const docList = document.getElementById("doc-list");
const emptyState = document.getElementById("empty-state");
const uploadPanel = document.getElementById("upload-panel");
const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const userEmailEl = document.getElementById("user-email");
const logoutBtn = document.getElementById("logout-btn");

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

function renderSkeleton(count = 3) {
  docList.innerHTML = "";
  emptyState.style.display = "none";
  for (let i = 0; i < count; i++) {
    const li = document.createElement("li");
    li.className = "skeleton-row";
    li.innerHTML = `
      <span class="skeleton skeleton-idx"></span>
      <div class="skeleton-main">
        <span class="skeleton skeleton-line-title"></span>
        <span class="skeleton skeleton-line-meta"></span>
      </div>
    `;
    docList.appendChild(li);
  }
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

async function loadDocuments() {
  renderSkeleton();
  const res = await fetch("/api/documents", { credentials: "include" });
  if (res.status === 401) {
    window.location.replace("/index.html");
    return;
  }
  const data = await res.json();
  renderDocuments(data.documents || []);
}

function renderDocuments(docs) {
  docList.innerHTML = "";
  emptyState.style.display = docs.length ? "none" : "block";

  docs.forEach((doc, i) => {
    const li = document.createElement("li");
    li.className = "doc-row";
    li.innerHTML = `
      <div class="doc-row-top">
        <span class="pdf-stamp">PDF</span>
        <button class="btn-danger" data-id="${doc.id}">Delete</button>
      </div>
      <div class="doc-main">
        <a class="doc-name" href="/document.html?id=${doc.id}">${escapeHtml(doc.filename)}</a>
        <div class="doc-meta">${doc.page_count} pages · ${formatSize(doc.file_size)}<br>uploaded ${formatDate(doc.uploaded_at)}</div>
      </div>
    `;
    li.querySelector("button.btn-danger").addEventListener("click", (e) => {
      e.stopPropagation();
      deleteDocument(doc.id, doc.filename);
    });
    docList.appendChild(li);
  });
}

async function deleteDocument(id, filename) {
  if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;
  const res = await fetch(`/api/documents/${id}`, { method: "DELETE", credentials: "include" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    showToast(data.error || "Could not delete document", "error");
    return;
  }
  showToast(`Deleted "${filename}"`, "success");
  loadDocuments();
}

function validateFile(file) {
  if (!file) return "Choose a PDF file first";
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    return "Only PDF files are allowed";
  }
  if (file.size > 20 * 1024 * 1024) return "File exceeds the 20 MB limit";
  return null;
}

async function uploadFile(file) {
  const error = validateFile(file);
  if (error) {
    showToast(error, "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  uploadBtn.innerHTML = `<span class="btn-spinner"></span>Uploading…`;

  // First upload embeds text locally and may download the embedding model
  // on the very first run ever, which can take a while — let the user know.
  const slowNotice = setTimeout(() => {
    showToast("Still working — first-time setup can take a minute…", "info", 6000);
  }, 4000);

  try {
    const res = await fetch("/api/documents", {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Upload failed", "error");
      return;
    }
    fileInput.value = "";
    showToast(`Uploaded "${data.document.filename}"`, "success");
    loadDocuments();
  } catch (err) {
    showToast("Could not reach the server. Please try again.", "error");
  } finally {
    clearTimeout(slowNotice);
    uploadBtn.disabled = false;
    uploadBtn.textContent = "Upload";
  }
}

uploadBtn.addEventListener("click", () => uploadFile(fileInput.files[0]));

// ---- Drag and drop ----
let dragCounter = 0;

uploadPanel.addEventListener("dragenter", (e) => {
  e.preventDefault();
  dragCounter++;
  uploadPanel.classList.add("drag-over");
});

uploadPanel.addEventListener("dragover", (e) => {
  e.preventDefault();
});

uploadPanel.addEventListener("dragleave", (e) => {
  e.preventDefault();
  dragCounter--;
  if (dragCounter <= 0) {
    dragCounter = 0;
    uploadPanel.classList.remove("drag-over");
  }
});

uploadPanel.addEventListener("drop", (e) => {
  e.preventDefault();
  dragCounter = 0;
  uploadPanel.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

logoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
  window.location.replace("/index.html");
});

(async function init() {
  const user = await requireAuth();
  if (user) loadDocuments();
})();

// See the matching comment in document.js — forces a fresh auth check if
// this page is restored from the browser's back/forward cache after logout.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    window.location.reload();
  }
});
