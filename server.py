import json
import os
import sys
import time
import string
import secrets
import mimetypes
import threading
from pathlib import Path
from datetime import datetime, timedelta

from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, abort, url_for, redirect
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ACCESS_LOG_PATH = BASE_DIR / "data" / "access_log.json"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


config = load_config()

METADATA_PATH = BASE_DIR / config["storage"]["metadata_file"]
UPLOAD_FOLDER = BASE_DIR / config["storage"]["upload_folder"]

app = Flask(
    __name__,
    static_folder=str(BASE_DIR / "static"),
    template_folder=str(BASE_DIR / "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = None  # No upload size limit

_metadata_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs():
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    if not METADATA_PATH.exists():
        METADATA_PATH.write_text("{}")


def reconcile_upload_folder():
    """
    Remove orphan files (on disk but not in metadata) and prune metadata entries
    for missing files. Prevents 'space used but no links' after crashes or
    corrupted/lost metadata.
    """
    try:
        metadata = load_metadata()
        valid_stored_names = {info["stored_name"] for info in metadata.values()}
        # Remove orphan files (on disk but not in metadata)
        for f in list(UPLOAD_FOLDER.iterdir()):
            if f.is_file() and f.name not in valid_stored_names:
                try:
                    f.unlink()
                    print(f"[reconcile] Removed orphan file: {f.name}")
                except OSError as e:
                    print(f"[reconcile] Could not remove {f.name}: {e}")
        # Prune metadata entries whose file no longer exists
        changed = False
        for file_id, info in list(metadata.items()):
            path = UPLOAD_FOLDER / info["stored_name"]
            if not path.exists():
                del metadata[file_id]
                changed = True
        if changed:
            save_metadata(metadata)
            print("[reconcile] Pruned metadata for missing files.")
    except Exception as e:
        print(f"[reconcile] Error: {e}")


def load_metadata():
    with _metadata_lock:
        with open(METADATA_PATH, "r") as f:
            return json.load(f)


def save_metadata(metadata):
    with _metadata_lock:
        tmp = METADATA_PATH.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(metadata, f, indent=2)
        tmp.replace(METADATA_PATH)


def generate_file_id(length=8):
    chars = string.ascii_letters + string.digits
    metadata = load_metadata()
    while True:
        file_id = "".join(secrets.choice(chars) for _ in range(length))
        if file_id not in metadata:
            return file_id


def human_size(nbytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def get_storage_usage():
    total = 0
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file():
            total += f.stat().st_size
    return total


def get_base_url():
    """Build base URL from the incoming request so links work via Cloudflare or localhost."""
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    return f"{scheme}://{request.host}"


def is_local_request():
    """Check if the request is coming from localhost (not through Cloudflare).
    Cloudflare adds Cf-Connecting-Ip header, so its presence means it's a tunnel request."""
    return "Cf-Connecting-Ip" not in request.headers


def log_access(event_type, file_id=None, filename=None, ip=None, **extra):
    """Log access events for monitoring (upload, download, upload_failed, etc.)."""
    try:
        # Determine IP and source (may be None for non-request contexts)
        if ip is None and request:
            ip = request.headers.get("Cf-Connecting-Ip") or request.remote_addr
        else:
            ip = ip or "—"

        source = "local" if (request and is_local_request()) else "external"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "file_id": file_id,
            "filename": filename,
            "ip": ip,
            "source": source,
            "user_agent": (request.headers.get("User-Agent", "")[:100] if request else ""),
            **extra,
        }

        # Load existing logs
        if ACCESS_LOG_PATH.exists():
            with open(ACCESS_LOG_PATH, "r") as f:
                logs = json.load(f)
        else:
            logs = []

        # Add new entry
        logs.append(log_entry)

        # Keep last 100 entries
        if len(logs) > 100:
            logs = logs[-100:]

        # Save
        with open(ACCESS_LOG_PATH, "w") as f:
            json.dump(logs, f, indent=2)
    except:
        pass  # Don't break server if logging fails


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if not is_local_request():
        abort(404)
    metadata = load_metadata()
    files = []
    for file_id, info in metadata.items():
        files.append({
            "id": file_id,
            "name": info["original_name"],
            "size": info["size"],
            "size_human": human_size(info["size"]),
            "upload_time": info["upload_time"],
            "mime_type": info["mime_type"],
            "link": f"{get_base_url()}/files/{file_id}",
            "preview_link": f"{get_base_url()}/preview/{file_id}",
            "is_image": info["mime_type"].startswith("image/"),
            "is_video": info["mime_type"].startswith("video/"),
        })
    files.sort(key=lambda x: x["upload_time"], reverse=True)

    storage_used = get_storage_usage()
    max_storage = config["storage"]["max_storage_mb"] * 1024 * 1024 if config["storage"]["max_storage_mb"] else 0

    return render_template(
        "index.html",
        files=files,
        storage_used=human_size(storage_used),
        storage_used_bytes=storage_used,
        max_storage=human_size(max_storage) if max_storage else "Unlimited",
        max_storage_bytes=max_storage,
        hostname=config["server"]["name"],
    )


@app.route("/upload", methods=["POST"])
def upload():
    if not is_local_request():
        abort(403)
    if "file" not in request.files:
        log_access("upload_failed", filename="—", error="No file part in request")
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        log_access("upload_failed", filename="—", error="No file selected")
        return jsonify({"error": "No file selected"}), 400

    max_mb = config["storage"]["max_storage_mb"]
    if max_mb > 0 and get_storage_usage() > max_mb * 1024 * 1024:
        return jsonify({"error": "Storage limit exceeded"}), 507

    file_id = generate_file_id()
    original_name = file.filename
    ext = Path(original_name).suffix
    stored_name = f"{file_id}{ext}"
    save_path = UPLOAD_FOLDER / stored_name

    file.save(str(save_path))
    file_size = save_path.stat().st_size

    if max_mb > 0 and get_storage_usage() > max_mb * 1024 * 1024:
        save_path.unlink()
        log_access("upload_failed", filename=original_name, error="Storage limit exceeded")
        return jsonify({"error": "Storage limit exceeded"}), 507

    mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"

    metadata = load_metadata()
    metadata[file_id] = {
        "original_name": original_name,
        "stored_name": stored_name,
        "upload_time": datetime.now().isoformat(),
        "size": file_size,
        "mime_type": mime_type,
    }
    save_metadata(metadata)
    log_access("upload", file_id=file_id, filename=original_name)

    link = f"{get_base_url()}/files/{file_id}"
    return jsonify({
        "file_id": file_id,
        "link": link,
        "name": original_name,
        "size": file_size,
    }), 201


@app.route("/files/<file_id>")
def share_file(file_id):
    """Redirect shared links to preview page instead of direct download"""
    metadata = load_metadata()
    if file_id in metadata:
        log_access("share_link_opened", file_id, metadata[file_id]["original_name"])
    return redirect(url_for('preview_file', file_id=file_id))


@app.route("/download/<file_id>")
def download_file(file_id):
    """Direct download endpoint"""
    metadata = load_metadata()
    if file_id not in metadata:
        abort(404)
    info = metadata[file_id]
    log_access("download", file_id, info["original_name"])
    return send_from_directory(
        str(UPLOAD_FOLDER),
        info["stored_name"],
        download_name=info["original_name"],
        as_attachment=True,
    )


@app.route("/preview/<file_id>")
def preview_file(file_id):
    metadata = load_metadata()
    if file_id not in metadata:
        abort(404)
    info = metadata[file_id]
    log_access("preview_viewed", file_id, info["original_name"])
    inline_url = url_for("serve_inline", file_id=file_id)

    # Read tunnel URL for external sharing
    tunnel_url_path = BASE_DIR / "tunnel_url.txt"
    if tunnel_url_path.exists():
        tunnel_url = tunnel_url_path.read_text().strip()
        share_link = f"{tunnel_url}/files/{file_id}"
    else:
        share_link = f"{get_base_url()}/files/{file_id}"

    return render_template(
        "preview.html",
        file=info,
        file_id=file_id,
        inline_url=inline_url,
        link=f"{get_base_url()}/download/{file_id}",
        share_link=share_link,
        is_image=info["mime_type"].startswith("image/"),
        is_video=info["mime_type"].startswith("video/"),
        is_audio=info["mime_type"].startswith("audio/"),
        hostname=config["server"]["name"],
    )


@app.route("/inline/<file_id>")
def serve_inline(file_id):
    metadata = load_metadata()
    if file_id not in metadata:
        abort(404)
    info = metadata[file_id]
    log_access("inline_view", file_id, info["original_name"])
    return send_from_directory(
        str(UPLOAD_FOLDER),
        info["stored_name"],
        download_name=info["original_name"],
        as_attachment=False,
    )


@app.route("/files/<file_id>", methods=["DELETE"])
def delete_file(file_id):
    if not is_local_request():
        abort(403)
    metadata = load_metadata()
    if file_id not in metadata:
        return jsonify({"error": "File not found"}), 404

    info = metadata[file_id]
    file_path = UPLOAD_FOLDER / info["stored_name"]

    if file_path.exists():
        file_path.unlink()

    del metadata[file_id]
    save_metadata(metadata)

    return jsonify({"status": "deleted", "file_id": file_id}), 200


# ---------------------------------------------------------------------------
# API for UI feedback (activity log, file list polling)
# ---------------------------------------------------------------------------

@app.route("/api/activity")
def api_activity():
    """Recent activity (uploads, downloads, failures) for server UI."""
    if not is_local_request():
        abort(404)
    try:
        if ACCESS_LOG_PATH.exists():
            with open(ACCESS_LOG_PATH, "r") as f:
                logs = json.load(f)
        else:
            logs = []
        return jsonify({"activity": logs[-50:]})  # last 50
    except Exception:
        return jsonify({"activity": []})


@app.route("/api/files")
def api_files():
    """Lightweight file list for polling so UI can refresh when new uploads appear."""
    if not is_local_request():
        abort(404)
    metadata = load_metadata()
    files = []
    last_updated = None
    for file_id, info in metadata.items():
        files.append({
            "id": file_id,
            "name": info["original_name"],
            "upload_time": info["upload_time"],
        })
        t = info["upload_time"]
        if last_updated is None or t > last_updated:
            last_updated = t
    files.sort(key=lambda x: x["upload_time"], reverse=True)
    return jsonify({"files": files, "last_updated": last_updated or ""})


# ---------------------------------------------------------------------------
# Cleanup scheduler
# ---------------------------------------------------------------------------

def cleanup_old_files():
    while True:
        days = config["cleanup"]["auto_delete_days"]
        interval = config["cleanup"]["check_interval_hours"] * 3600
        if days > 0:
            cutoff = datetime.now() - timedelta(days=days)
            metadata = load_metadata()
            to_delete = []
            for file_id, info in metadata.items():
                upload_time = datetime.fromisoformat(info["upload_time"])
                if upload_time < cutoff:
                    to_delete.append(file_id)
            for file_id in to_delete:
                info = metadata[file_id]
                file_path = UPLOAD_FOLDER / info["stored_name"]
                if file_path.exists():
                    file_path.unlink()
                del metadata[file_id]
            if to_delete:
                save_metadata(metadata)
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ensure_dirs()
    reconcile_upload_folder()

    if config["cleanup"]["auto_delete_days"] > 0:
        is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        if not app.debug or is_reloader:
            t = threading.Thread(target=cleanup_old_files, daemon=True)
            t.start()

    print(f"Starting {config['server']['name']} on port {config['server']['port']}...")
    print(f"Web UI: http://localhost:{config['server']['port']}")
    app.run(
        host=config["server"]["host"],
        port=config["server"]["port"],
        debug=config["server"].get("debug", False),
    )
