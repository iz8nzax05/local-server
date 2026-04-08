# LocalServer

A local file sharing server with a desktop UI, Cloudflare tunnel for external access, and real-time activity monitoring. Drop a file in via browser, double-click the filename in the menu, and the share link is on your clipboard.

---

## How it works

**Flask backend (`server.py`)** — serves files on port 713. Each uploaded file gets a random 8-character ID. Upload is restricted to localhost only; download and preview are public via the tunnel URL. Routes:

- `POST /upload` — saves file, writes metadata JSON entry
- `GET /files/<id>` — share link, logs access event, redirects to preview
- `GET /preview/<id>` — preview page with download + inline view
- `GET /download/<id>` — direct download
- `DELETE /files/<id>` — removes file + metadata entry
- `GET /api/files` — JSON list of all files
- `GET /api/activity` — recent access log

On startup, `reconcile_upload_folder()` diffs the uploads folder against metadata and removes orphans in both directions — prevents ghost entries after crashes.

**Tunnel (`tunnel_runner.py`)** — spawns `cloudflared` as a subprocess, watches stdout for the `trycloudflare.com` URL, writes it to `tunnel_url.txt`. The menu and server read from that file whenever they need the current public URL.

**Menu app (`menu_app.py`)** — CustomTkinter window. Polls server status and `tunnel_url.txt` every 5 seconds in a background thread. File list shows the 10 most recent uploads; double-click copies `<tunnel_url>/files/<id>` to clipboard. Activity log tracks uploads, link copies, tunnel URL changes, and access events live.

**Upload handler (`upload_handler.py`)** — handles chunked uploads from the browser and shows a Windows toast notification on completion.

---

## Setup

**The project expects to live at `C:\LocalServer`.** `menu_app.py` and `tray_app.py` both have `self.server_dir = Path("C:/LocalServer")` hardcoded. If you put it somewhere else, edit those two lines.

1. Clone or copy the project to `C:\LocalServer`
2. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) — it's expected at `C:\Program Files (x86)\cloudflared\cloudflared.exe`. If yours is elsewhere, edit line 9 of `tunnel_runner.py`.
3. Install dependencies:
   ```bash
   pip install flask requests pyperclip plyer customtkinter psutil pystray pillow
   ```
4. Run the menu:
   ```bash
   python menu_app.py
   ```
5. Click **Start Server** — Flask starts on port 713, tunnel comes up within ~10 seconds
6. Click **Upload Files** to open the browser upload page
7. Double-click any file in the list to copy its share link

**Optional — right-click context menu** (right-click any file → "Share to My Server"):
```bash
python context_menu.py --install
# to remove:
python context_menu.py --uninstall
```

---

## Security model

| Route | Access |
|---|---|
| `POST /upload` | Localhost only |
| `DELETE /files/<id>` | Localhost only |
| `GET /` (file list) | Localhost only |
| `GET /api/files`, `/api/activity` | Localhost only |
| `GET /files/<id>`, `/preview/<id>`, `/download/<id>` | **Public** (via tunnel) |

"Localhost only" is enforced by checking for the absence of the `Cf-Connecting-Ip` header — Cloudflare always adds this, so tunnel traffic is blocked from upload/delete/listing routes.

Share links are public by design, but each file gets a random 8-character ID (`secrets.choice` from 62 chars). There's no file enumeration endpoint exposed publicly.

**Access logging** — `data/access_log.json` records the IP, user agent, and event type for every download/preview/share link open. This file stays local and is excluded from the repo via `.gitignore`.

---

## Files

| File | Purpose |
|---|---|
| `server.py` | Flask server, routes, metadata, access logging |
| `menu_app.py` | CustomTkinter desktop UI |
| `tray_app.py` | Alternative system tray UI |
| `tunnel_runner.py` | Cloudflare tunnel subprocess + URL extraction |
| `upload_handler.py` | Chunked upload handler + toast notifications |
| `context_menu.py` | Windows context menu integration |
| `cleanup_orphans.py` | Standalone orphan file cleaner |
| `config.json` | Port, storage paths, auto-delete settings |
| `templates/` | Upload page + file preview page (HTML) |
| `static/` | CSS + JS for the web UI |

**~2,000 lines** across 7 Python modules.
