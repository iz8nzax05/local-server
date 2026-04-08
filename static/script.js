// ===== Drag & Drop Upload =====
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const progressBar = document.getElementById("uploadProgress");
const progressFill = document.getElementById("progressFill");

if (dropZone) {
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files);
        }
    });

    dropZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            uploadFiles(fileInput.files);
        }
    });
}

async function uploadFiles(files) {
    for (const file of files) {
        await uploadSingleFile(file);
    }
    window.location.reload();
}

function uploadSingleFile(file) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append("file", file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/upload");

        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                progressBar.hidden = false;
                const pct = (e.loaded / e.total) * 100;
                progressFill.style.width = pct + "%";
            }
        });

        xhr.addEventListener("load", () => {
            progressBar.hidden = true;
            progressFill.style.width = "0%";
            if (xhr.status === 201) {
                resolve(JSON.parse(xhr.responseText));
            } else {
                showToast("Upload failed");
                reject(new Error(xhr.responseText));
            }
        });

        xhr.addEventListener("error", () => {
            progressBar.hidden = true;
            showToast("Upload failed: network error");
            reject(new Error("Network error"));
        });

        xhr.send(formData);
    });
}

// ===== Copy Link =====
function copyLink(link) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(link).then(() => {
            showToast("Link copied!");
        }).catch(() => {
            fallbackCopy(link);
        });
    } else {
        fallbackCopy(link);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast("Link copied!");
}

// ===== Delete File =====
async function deleteFile(fileId) {
    if (!confirm("Delete this file permanently?")) return;

    const resp = await fetch("/files/" + fileId, { method: "DELETE" });
    if (resp.ok) {
        const card = document.querySelector('[data-id="' + fileId + '"]');
        if (card) {
            card.style.opacity = "0";
            card.style.transform = "translateX(40px)";
            setTimeout(() => card.remove(), 300);
        }
    } else {
        showToast("Delete failed");
    }
}

// ===== Toast =====
function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => {
        requestAnimationFrame(() => toast.classList.add("show"));
    });
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// ===== Recent activity + auto-refresh file list =====
const activityList = document.getElementById("activityList");
const activityEmpty = document.getElementById("activityEmpty");

function formatActivityTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function activityClass(event) {
    if (event === "upload") return "activity-upload";
    if (event === "upload_failed") return "activity-failed";
    if (event === "download") return "activity-download";
    if (event === "share_link_opened" || event === "preview_viewed" || event === "inline_view") return "activity-share";
    return "";
}

function activityLabel(entry) {
    const ev = entry.event;
    const name = entry.filename || "—";
    if (ev === "upload") return "Uploaded: " + name;
    if (ev === "upload_failed") {
        const err = entry.error || "unknown";
        return (entry.filename && entry.filename !== "—") ? "Failed " + entry.filename + ": " + err : "Failed: " + err;
    }
    if (ev === "download") return "Downloaded: " + name;
    if (ev === "share_link_opened") return "Share link opened: " + name;
    if (ev === "preview_viewed") return "Preview: " + name;
    if (ev === "inline_view") return "Viewed: " + name;
    return ev + ": " + name;
}

function renderActivity(activity) {
    if (!activityList || !activityEmpty) return;
    activityList.innerHTML = "";
    if (!activity || activity.length === 0) {
        activityList.classList.add("hidden");
        activityEmpty.classList.add("visible");
        return;
    }
    activityEmpty.classList.remove("visible");
    activityList.classList.remove("hidden");
    activity.slice().reverse().forEach(function (entry) {
        const li = document.createElement("li");
        li.className = activityClass(entry.event);
        li.innerHTML = "<span class=\"activity-time\">" + formatActivityTime(entry.timestamp) + "</span>" +
            "<span class=\"activity-msg\">" + activityLabel(entry) + "</span>";
        activityList.appendChild(li);
    });
}

function fetchActivity() {
    fetch("/api/activity")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
            if (data && data.activity) renderActivity(data.activity);
        })
        .catch(function () {});
}

function pollFilesAndReload() {
    fetch("/api/files")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
            if (!data) return;
            var key = (data.last_updated || "") + "|" + (data.files ? data.files.length : 0);
            if (typeof window._filesPollKey === "undefined") window._filesPollKey = key;
            if (window._filesPollKey !== key) {
                window._filesPollKey = key;
                window.location.reload();
            }
        })
        .catch(function () {});
}

if (activityList) {
    fetchActivity();
    setInterval(fetchActivity, 3000);
}
pollFilesAndReload();
setInterval(pollFilesAndReload, 4000);
