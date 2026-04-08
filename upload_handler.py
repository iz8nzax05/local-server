import sys
import json
import logging
import ctypes
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "data" / "upload.log"
PROGRESS_PATH = BASE_DIR / "data" / "upload_progress.json"

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def show_notification(title, message):
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="MyServer",
            timeout=5,
        )
    except Exception:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except Exception:
            pass


def copy_to_clipboard(text):
    """Copy text to clipboard using Windows API directly (no console flash)."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    data = text.encode("utf-16-le") + b"\x00\x00"
    user32.OpenClipboard(0)
    user32.EmptyClipboard()
    h = kernel32.GlobalAlloc(0x0042, len(data))
    ptr = kernel32.GlobalLock(h)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(13, h)
    user32.CloseClipboard()


def get_tunnel_url():
    """Read the current Cloudflare tunnel URL if available."""
    tunnel_file = BASE_DIR / "tunnel_url.txt"
    if tunnel_file.exists():
        url = tunnel_file.read_text().strip()
        if url:
            return url
    return None


def _write_progress(state, filename, bytes_sent=0, bytes_total=0, error=None):
    try:
        data = {
            "state": state,
            "filename": filename,
            "bytes_sent": bytes_sent,
            "bytes_total": bytes_total,
        }
        if error is not None:
            data["error"] = str(error)[:200]
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def upload_file(file_path):
    config = load_config()
    file_path = Path(file_path)

    if not file_path.exists():
        msg = f"File not found: {file_path.name}"
        logging.error(msg)
        show_notification("Upload Failed", msg)
        return

    url = f"http://localhost:{config['server']['port']}/upload"
    file_size = file_path.stat().st_size
    logging.info(f"Uploading {file_path.name} ({file_size} bytes)")

    last_pct = -1
    last_write_time = [0]

    def on_progress(bytes_sent):
        nonlocal last_pct
        pct = int((bytes_sent / file_size) * 100) if file_size else 0
        now = time.time()
        if pct != last_pct or (now - last_write_time[0]) >= 0.5:
            last_pct = pct
            last_write_time[0] = now
            _write_progress("uploading", file_path.name, bytes_sent, file_size)

    class ProgressReader:
        def __init__(self):
            self._f = open(file_path, "rb")
            self._bytes_read = 0

        def read(self, size=-1):
            data = self._f.read(size)
            self._bytes_read += len(data)
            on_progress(self._bytes_read)
            return data

        def __len__(self):
            return file_size

        def close(self):
            self._f.close()

    _write_progress("uploading", file_path.name, 0, file_size)

    try:
        reader = ProgressReader()
        try:
            resp = requests.post(
                url,
                files={"file": (file_path.name, reader)},
                timeout=600,
            )
        finally:
            reader.close()

        if resp.status_code == 201:
            _write_progress("done", file_path.name, file_size, file_size)
            data = resp.json()
            link = data["link"]
            # Rewrite link to use tunnel URL if available
            tunnel_url = get_tunnel_url()
            if tunnel_url:
                file_id = link.split("/files/", 1)[-1]
                link = f"{tunnel_url}/preview/{file_id}"
            copy_to_clipboard(link)
            logging.info(f"Uploaded: {link}")
            show_notification("Link Copied!", link)
        else:
            error = resp.json().get("error", f"HTTP {resp.status_code}")
            _write_progress("failed", file_path.name, 0, file_size, error=error)
            logging.error(f"Server error: {error}")
            show_notification("Upload Failed", error)
    except requests.ConnectionError:
        msg = f"Server not running on port {config['server']['port']}"
        _write_progress("failed", file_path.name, 0, file_size, error=msg)
        logging.error(msg)
        show_notification("Upload Failed", msg)
    except Exception as e:
        _write_progress("failed", file_path.name, 0, file_size, error=str(e)[:200])
        logging.exception("Upload error")
        show_notification("Upload Failed", str(e)[:200])


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            show_notification("Upload Failed", "No file path provided")
            sys.exit(1)
        upload_file(sys.argv[1])
    except Exception as e:
        logging.exception("Unhandled error")
        show_notification("Upload Failed", str(e)[:200])
