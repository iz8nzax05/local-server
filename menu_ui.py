"""
LocalServer menu — CustomTkinter UI with full server logic.
Uses the theme from the test UI; all buttons (Start/Stop, Upload, Refresh, logs, copy link) work.
"""
import tkinter as tk
import customtkinter as ctk
import json
import threading
import time
from pathlib import Path
import subprocess
import psutil
import pyperclip
from datetime import datetime

# Modern dark theme with teal accent
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

def _emoji_font(size=11, weight="normal"):
    return ctk.CTkFont(family="Segoe UI Emoji", size=size, weight=weight)


class LocalServerMenu(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LocalServer")
        self.logs_visible = False
        self.geometry("420x620")
        self.minsize(380, 560)

        # Server state (same as original)
        self.server_dir = Path("C:/LocalServer")
        self.metadata_path = self.server_dir / "data/file_metadata.json"
        self.tunnel_url_path = self.server_dir / "tunnel_url.txt"
        self.access_log_path = self.server_dir / "data/access_log.json"
        self.server_process = None
        self.tunnel_process = None
        self.activity_logs = []
        self.last_file_count = 0
        self.last_tunnel_url = None
        self.last_access_count = 0

        self._schedule_refresh = lambda: self.after(0, self.refresh_status)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_controls()
        self._build_files_section()
        self._build_logs_toggle()
        self._build_status_bar()

        # Dark title bar (Windows)
        try:
            import ctypes
            self.update()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

        self.refresh_status()
        self.refresh_files()
        self.start_auto_refresh()
        self.start_activity_monitor()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=("#2d2d30", "#252526"), height=84, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            header,
            text="● Server Stopped",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=("#8b8b8b", "#9d9d9d"),
        )
        self.status_label.grid(row=0, column=0, pady=(14, 2))

        self.tunnel_label = ctk.CTkLabel(
            header,
            text="Click 'Start Server' below",
            font=ctk.CTkFont(size=11),
            text_color=("#6b6b6b", "#6d6d6d"),
        )
        self.tunnel_label.grid(row=1, column=0, pady=(0, 12))

    def _build_controls(self):
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=14, pady=(12, 8))
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(
            controls,
            text="▶ START SERVER",
            command=self.start_server,
            height=40,
            font=_emoji_font(size=12, weight="bold"),
            fg_color=("#2d9d78", "#238f6c"),
            hover_color=("#268f6a", "#1e7a58"),
            text_color="#ffffff",
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 4), pady=4, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            controls,
            text="⏹ STOP",
            command=self.stop_server,
            height=40,
            font=_emoji_font(size=12, weight="bold"),
            fg_color=("#c73e3e", "#a83535"),
            hover_color=("#b03636", "#8f2b2b"),
            text_color="#ffffff",
            state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, padx=(4, 0), pady=4, sticky="ew")

        upload_btn = ctk.CTkButton(
            controls,
            text="📤 UPLOAD FILES",
            command=self.open_upload,
            height=38,
            font=_emoji_font(size=12, weight="bold"),
            fg_color=("#3d6ab5", "#345a9e"),
            hover_color=("#365fa3", "#2d4f88"),
            text_color="#ffffff",
        )
        upload_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)

        refresh_btn = ctk.CTkButton(
            controls,
            text="🔄 Refresh Status",
            command=self.refresh_status,
            height=36,
            font=_emoji_font(size=11),
            fg_color=("#3d3d40", "#383838"),
            hover_color=("#505052", "#454545"),
            text_color="#ffffff",
        )
        refresh_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

    def _build_files_section(self):
        files_label = ctk.CTkLabel(
            self,
            text="📁 RECENT FILES",
            font=_emoji_font(size=11, weight="bold"),
            text_color="#ffffff",
            anchor="center",
        )
        files_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 4))

        # One tk frame for listbox so refresh_files/copy_file_link work; matches test look (dark box)
        listbox_outer = tk.Frame(self, bg="#252526", highlightthickness=0)
        listbox_outer.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.grid_rowconfigure(3, weight=1)
        listbox_outer.grid_columnconfigure(0, weight=1)
        listbox_outer.grid_rowconfigure(0, weight=1)
        listbox_frame = tk.Frame(listbox_outer, bg="black")
        listbox_frame.pack(fill="both", expand=True, padx=4, pady=4)

        scrollbar = tk.Scrollbar(listbox_frame, bg="#3e3e42", width=0)
        scrollbar.pack(side="right", fill="y")

        self.files_listbox = tk.Listbox(
            listbox_frame,
            bg="black",
            fg="#ffffff",
            font=("Segoe UI Emoji", 10),
            selectbackground="#4068b8",
            selectforeground="white",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            cursor="hand2",
        )
        self.files_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.files_listbox.yview)

        self.files_listbox.bind("<Double-Button-1>", self.copy_file_link)
        self.files_listbox.bind("<Return>", self.copy_file_link)

    def _build_logs_toggle(self):
        self.logs_btn = ctk.CTkButton(
            self,
            text="📊 Show Logs ▼",
            command=self._toggle_logs,
            height=34,
            font=_emoji_font(size=11),
            fg_color=("#3d3d40", "#383838"),
            hover_color=("#505052", "#454545"),
            text_color="#ffffff",
        )
        self.logs_btn.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 10))

        self.logs_container = ctk.CTkFrame(self, fg_color="transparent")
        self.logs_container.grid(row=5, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.logs_container.grid_columnconfigure(0, weight=1)
        self.logs_container.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(5, weight=0)

        log_btn_frame = ctk.CTkFrame(self.logs_container, fg_color="transparent")
        log_btn_frame.grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkButton(
            log_btn_frame,
            text="🔄 Refresh",
            command=self.update_logs,
            height=26,
            font=_emoji_font(size=10),
            fg_color=("#4068b8", "#345a9e"),
            hover_color=("#365fa3", "#2d4f88"),
            text_color="#ffffff",
            width=80,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            log_btn_frame,
            text="🗑️ Clear Activity",
            command=self.clear_logs,
            height=26,
            font=_emoji_font(size=10),
            fg_color=("#b87858", "#9d6648"),
            hover_color=("#a06d4d", "#8b5a3f"),
            text_color="#ffffff",
            width=110,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            log_btn_frame,
            text="🧹 Clear ALL",
            command=self.clear_all_logs,
            height=26,
            font=_emoji_font(size=10),
            fg_color=("#d43737", "#a83535"),
            hover_color=("#c73e3e", "#8f2b2b"),
            text_color="#ffffff",
            width=80,
        ).pack(side="left", padx=2)

        self.logs_text = ctk.CTkTextbox(
            self.logs_container,
            height=160,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="black",
            text_color="#ffffff",
            border_width=0,
            corner_radius=4,
        )
        self.logs_text.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        try:
            self.logs_text._y_scrollbar.configure(width=0)
        except Exception:
            pass
        self.logs_container.grid_remove()

    def _toggle_logs(self):
        if self.logs_visible:
            self.logs_container.grid_remove()
            self.logs_btn.configure(text="📊 Show Logs ▼")
            self.logs_visible = False
            self.geometry("420x620")
        else:
            self.logs_container.grid()
            self.logs_btn.configure(text="📊 Hide Logs ▲")
            self.logs_visible = True
            self.geometry("420x820")
            self.update_logs()

    def _build_status_bar(self):
        status_bar = ctk.CTkFrame(self, fg_color=("#2d2d30", "#252526"), height=28, corner_radius=0)
        status_bar.grid(row=6, column=0, sticky="ew")
        status_bar.grid_propagate(False)
        status_bar.grid_columnconfigure(0, weight=1)

        self.status_bar_label = ctk.CTkLabel(
            status_bar,
            text="Ready",
            font=ctk.CTkFont(size=10),
            text_color=("#6b6b6b", "#6d6d6d"),
            anchor="w",
        )
        self.status_bar_label.grid(row=0, column=0, sticky="w", padx=12, pady=6)

    # ---------- Helpers (from original) ----------
    def is_server_running(self):
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline", []) or []
                if cmdline and "python" in (proc.info.get("name") or "").lower():
                    if any("server.py" in str(arg) for arg in cmdline):
                        return True
            except Exception:
                pass
        return False

    def get_tunnel_url(self):
        if self.tunnel_url_path.exists():
            try:
                return self.tunnel_url_path.read_text().strip()
            except Exception:
                pass
        return None

    def get_files(self):
        if not self.metadata_path.exists():
            return []
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            files = []
            for file_id, info in metadata.items():
                files.append({
                    "id": file_id,
                    "name": info["original_name"],
                    "size": self.human_size(info["size"]),
                    "time": info["upload_time"][:16].replace("T", " "),
                })
            files.sort(key=lambda x: x["time"], reverse=True)
            return files[:10]
        except Exception:
            return []

    def human_size(self, nbytes):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} PB"

    def add_activity_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.activity_logs.append(log_entry)
        if len(self.activity_logs) > 100:
            self.activity_logs.pop(0)
        if self.logs_visible and hasattr(self, "logs_text"):
            try:
                self.logs_text.insert("end", log_entry + "\n")
                self.logs_text.see("end")
            except Exception:
                pass

    def update_logs(self):
        if not self.logs_visible or not hasattr(self, "logs_text"):
            return
        try:
            self.logs_text.delete("1.0", "end")
        except Exception:
            return
        if self.is_server_running():
            tunnel_url = self.get_tunnel_url()
            if tunnel_url:
                self.logs_text.insert("end", f"🟢 Server Online | Tunnel: {tunnel_url}\n")
            else:
                self.logs_text.insert("end", "🟢 Server Online | ⏳ Waiting for tunnel...\n")
        else:
            self.logs_text.insert("end", "⚫ Server Offline\n")
        self.logs_text.insert("end", "=" * 70 + "\n\n")
        if self.activity_logs:
            for log in self.activity_logs:
                self.logs_text.insert("end", log + "\n")
        else:
            self.logs_text.insert("end", "No activity yet. Logs will appear here when:\n")
            self.logs_text.insert("end", "  • Server starts/stops\n")
            self.logs_text.insert("end", "  • Files are uploaded\n")
            self.logs_text.insert("end", "  • Links are copied\n")
            self.logs_text.insert("end", "  • Tunnel URL changes\n")
        try:
            self.logs_text.see("end")
        except Exception:
            pass

    def clear_logs(self):
        self.activity_logs = []
        if hasattr(self, "logs_text"):
            self.update_logs()
        self.add_activity_log("🗑️ Activity logs cleared")

    def clear_all_logs(self):
        self.activity_logs = []
        self.last_access_count = 0
        if self.access_log_path.exists():
            try:
                self.access_log_path.write_text("[]", encoding="utf-8")
            except Exception:
                pass
        if hasattr(self, "logs_text"):
            self.update_logs()
        self.add_activity_log("🧹 ALL logs cleared (activity + access logs)")

    def log_access_event(self, event):
        event_type = event.get("event", "unknown")
        filename = event.get("filename", "unknown")
        source = event.get("source", "unknown")
        try:
            ts = event.get("timestamp", "")
            time_only = ts[11:19] if len(ts) > 19 else ""
        except Exception:
            time_only = ""
        if event_type == "share_link_opened":
            emoji, msg = "🔗", f"Share link opened: {filename}"
        elif event_type == "preview_viewed":
            emoji, msg = "👁️", f"Preview viewed: {filename}"
        elif event_type == "download":
            emoji, msg = "⬇️", f"Downloaded: {filename}"
        elif event_type == "inline_view":
            emoji, msg = "▶️", f"Viewed inline: {filename}"
        else:
            emoji, msg = "❓", f"{event_type}: {filename}"
        source_emoji = "🌍" if source == "external" else "🏠"
        self.add_activity_log(f"{emoji} {msg} ({source_emoji} {source})")

    def start_activity_monitor(self):
        def monitor():
            while True:
                try:
                    current_files = self.get_files()
                    current_count = len(current_files)
                    if current_count > self.last_file_count:
                        new_file = current_files[0]
                        self.add_activity_log(f"📤 New upload: {new_file['name']} ({new_file['size']})")
                        self.last_file_count = current_count
                    elif current_count < self.last_file_count:
                        self.add_activity_log(f"🗑️ File deleted (total now: {current_count})")
                        self.last_file_count = current_count
                    current_tunnel = self.get_tunnel_url()
                    if current_tunnel != self.last_tunnel_url:
                        if current_tunnel:
                            self.add_activity_log(f"🌐 Tunnel URL updated: {current_tunnel}")
                        self.last_tunnel_url = current_tunnel
                    if self.access_log_path.exists():
                        try:
                            with open(self.access_log_path, "r", encoding="utf-8") as f:
                                access_logs = json.load(f)
                            current_access_count = len(access_logs)
                            if current_access_count > self.last_access_count:
                                for ev in access_logs[self.last_access_count :]:
                                    self.log_access_event(ev)
                                self.last_access_count = current_access_count
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(2)

        threading.Thread(target=monitor, daemon=True).start()

    # ---------- Refresh & copy ----------
    def refresh_status(self):
        running = self.is_server_running()
        tunnel_url = self.get_tunnel_url()

        if running:
            self.status_label.configure(text="● Server Running", text_color="#3eb89a")
            self.start_btn.configure(state="disabled", fg_color=("#2e2e32", "#2e2e32"))
            self.stop_btn.configure(state="normal", fg_color=("#c73e3e", "#a83535"))

            if tunnel_url:
                display_url = tunnel_url.replace("https://", "")
                if len(display_url) > 45:
                    display_url = display_url[:42] + "..."
                self.tunnel_label.configure(text=f"🌐 {display_url}", text_color="#4068b8")
            else:
                self.tunnel_label.configure(text="⏳ Waiting for tunnel URL...", text_color="#b87858")
        else:
            self.status_label.configure(text="● Server Stopped", text_color=("#8b8b8b", "#9d9d9d"))
            self.tunnel_label.configure(text="Click 'Start Server' below", text_color=("#6b6b6b", "#6d6d6d"))
            self.start_btn.configure(state="normal", fg_color=("#2d9d78", "#238f6c"))
            self.stop_btn.configure(state="disabled", fg_color=("#2e2e32", "#2e2e32"))

        self.refresh_files()
        if self.logs_visible:
            self.update_logs()
        self.status_bar_label.configure(text=f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

    def refresh_files(self):
        self.files_listbox.delete(0, tk.END)
        files = self.get_files()
        if not files:
            self.files_listbox.insert(tk.END, "  No files uploaded yet")
            self.files_listbox.configure(fg="#909090")
        else:
            self.files_listbox.configure(fg="#ffffff")
            for file in files:
                display = f"  📄 {file['name']}"
                if len(display) > 50:
                    display = display[:47] + "..."
                self.files_listbox.insert(tk.END, display)

    def copy_file_link(self, event=None):
        sel = self.files_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        files = self.get_files()
        if idx >= len(files):
            return
        file = files[idx]
        tunnel_url = self.get_tunnel_url()
        if not tunnel_url:
            self.status_bar_label.configure(text="⚠ No tunnel URL available - is server running?")
            return
        if not self.is_server_running():
            self.status_bar_label.configure(text="⚠ Server is offline - starting...")
            self.start_server()
            return
        link = f"{tunnel_url}/files/{file['id']}"
        pyperclip.copy(link)
        self.status_bar_label.configure(text=f"✓ Copied link for '{file['name']}'")
        self.add_activity_log(f"📋 Copied share link: {file['name']}")

    def open_upload(self):
        if not self.is_server_running():
            self.status_bar_label.configure(text="⚠ Starting server first...")
            self.add_activity_log("⚠ Server offline, starting before opening upload page...")
            self.start_server()
            time.sleep(3)
        subprocess.Popen(
            ["cmd", "/c", "start", "http://localhost:713"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.status_bar_label.configure(text="Opened upload page in browser")
        self.add_activity_log("🌐 Opened upload page in browser")

    def start_server(self):
        self.status_bar_label.configure(text="⏳ Starting server...")
        self.status_label.configure(text="● Server starting", text_color="#f39c12")
        self.add_activity_log("▶ Starting server...")

        def start():
            try:
                self.stop_server()
                time.sleep(1)
                self.server_process = subprocess.Popen(
                    ["python", "server.py"],
                    cwd=str(self.server_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.add_activity_log("  ✓ Flask server process started")
                time.sleep(2)
                self.tunnel_process = subprocess.Popen(
                    ["python", "tunnel_runner.py"],
                    cwd=str(self.server_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.add_activity_log("  ✓ Cloudflare tunnel started")
                time.sleep(8)
                self._schedule_refresh()
                if self.is_server_running():
                    self.after(0, lambda: self.status_bar_label.configure(text="✓ Server started successfully!"))
                    self.add_activity_log("✓ Server online and ready!")
                else:
                    self.after(0, lambda: self.status_bar_label.configure(text="⚠ Server failed to start"))
                    self.add_activity_log("⚠ Server failed to start")
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self.status_bar_label.configure(text=f"❌ Error: {err_msg}"))
                self.add_activity_log(f"❌ Error starting server: {err_msg}")

        threading.Thread(target=start, daemon=True).start()

    def stop_server(self):
        self.status_bar_label.configure(text="Stopping server...")
        self.add_activity_log("⏹ Stopping server...")
        try:
            if self.server_process:
                self.server_process.kill()
                self.server_process = None
            if self.tunnel_process:
                self.tunnel_process.kill()
                self.tunnel_process = None
            killed_count = 0
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = (proc.info or {}).get("cmdline", []) or []
                    name = (proc.info or {}).get("name") or ""
                    if cmdline and "python" in name.lower():
                        if any(("server.py" in str(a) or "tunnel_runner.py" in str(a)) for a in cmdline):
                            proc.kill()
                            killed_count += 1
                except Exception:
                    pass
            subprocess.Popen(
                ["taskkill", "/F", "/IM", "cloudflared.exe"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
            self.after(0, self.refresh_status)
            self.after(0, lambda: self.status_bar_label.configure(text="✓ Server stopped"))
            self.add_activity_log(f"✓ Server stopped ({killed_count} processes killed)")
            self.add_activity_log("🧹 Auto-clearing logs (server stopped)...")
            time.sleep(0.5)
            self.clear_all_logs()
            self.after(0, self.refresh_files)
        except Exception as e:
            self.status_bar_label.configure(text=f"Error: {str(e)}")
            self.add_activity_log(f"❌ Error stopping server: {str(e)}")

    def start_auto_refresh(self):
        def auto_refresh():
            while True:
                time.sleep(5)
                try:
                    self._schedule_refresh()
                except Exception:
                    pass

        threading.Thread(target=auto_refresh, daemon=True).start()

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    app = LocalServerMenu()
    app.run()
