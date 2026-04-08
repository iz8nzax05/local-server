"""
COPY OF ORIGINAL: C:\LocalServer\menu_app.py
Full LocalServer menu UI (tkinter) — server, tunnel, upload, logs all work.
Kept in this folder for comparison with the CustomTkinter test UI.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import threading
import time
from pathlib import Path
import subprocess
import psutil
import pyperclip
from datetime import datetime

class LocalServerMenu:
    def __init__(self):
        self.server_dir = Path("C:/LocalServer")
        self.metadata_path = self.server_dir / "data/file_metadata.json"
        self.tunnel_url_path = self.server_dir / "tunnel_url.txt"
        self.access_log_path = self.server_dir / "data/access_log.json"
        self.server_process = None
        self.tunnel_process = None
        self.activity_logs = []  # Store real-time activity
        self.last_file_count = 0
        self.last_tunnel_url = None
        self.last_access_count = 0

        # Create main window
        self.root = tk.Tk()
        self.root.title("LocalServer")
        self.root.geometry("400x600")
        self.root.configure(bg='#1e1e1e')  # Dark bg like your Pygame projects

        # Enable dark title bar (Windows 10/11)
        try:
            import ctypes
            self.root.update()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)),
                ctypes.sizeof(ctypes.c_int)
            )
        except:
            pass  # Silently fail if not supported

        # Set window to stay on top initially (can be toggled)
        self.always_on_top = False

        self.setup_ui()
        self.start_auto_refresh()
        self.start_activity_monitor()

    def setup_ui(self):
        # Header with server status - darker modern look
        header = tk.Frame(self.root, bg='#2d2d30', height=80)
        header.pack(fill='x')
        header.pack_propagate(False)

        self.status_label = tk.Label(
            header,
            text="⚫ Server Stopped",
            bg='#2d2d30',
            fg='#b0b0b0',  # Slightly darker light gray
            font=('Segoe UI', 14, 'bold'),
            pady=10
        )
        self.status_label.pack()

        self.tunnel_label = tk.Label(
            header,
            text="Click 'Start Server' below",
            bg='#2d2d30',
            fg='#707070',  # Darker dimmed gray
            font=('Segoe UI', 8)
        )
        self.tunnel_label.pack()

        # Main controls
        controls = tk.Frame(self.root, bg='#1e1e1e')
        controls.pack(fill='x', padx=10, pady=10)

        # Server control buttons
        btn_frame1 = tk.Frame(controls, bg='#1e1e1e')
        btn_frame1.pack(fill='x', pady=5)

        self.start_btn = tk.Button(
            btn_frame1,
            text="▶ START SERVER",
            command=self.start_server,
            bg='#3eb89a',  # Softer teal success
            fg='white',  # White text for better contrast
            font=('Segoe UI', 10, 'bold'),
            padx=20,
            pady=10,
            cursor='hand2',
            relief='flat',
            bd=0
        )
        self.start_btn.pack(side='left', expand=True, fill='x', padx=2)

        self.stop_btn = tk.Button(
            btn_frame1,
            text="⏹ STOP",
            command=self.stop_server,
            bg='#d43737',  # Softer red danger
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            padx=20,
            pady=10,
            cursor='hand2',
            state='disabled',
            relief='flat',
            bd=0
        )
        self.stop_btn.pack(side='left', expand=True, fill='x', padx=2)

        # Upload button - blue accent (softer)
        upload_btn = tk.Button(
            controls,
            text="📤 UPLOAD FILES",
            command=self.open_upload,
            bg='#4068b8',  # Softer blue accent
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            pady=10,
            cursor='hand2',
            relief='flat',
            bd=0
        )
        upload_btn.pack(fill='x', pady=5)

        # Refresh button
        refresh_btn = tk.Button(
            controls,
            text="🔄 Refresh Status",
            command=self.refresh_status,
            bg='#2e2e32',  # Darker medium gray button
            fg='white',  # Full white text
            font=('Segoe UI', 9),
            pady=8,
            cursor='hand2',
            relief='flat',
            bd=0
        )
        refresh_btn.pack(fill='x', pady=5)

        # Recent files section
        files_label = tk.Label(
            self.root,
            text="📁 RECENT FILES",
            bg='#1e1e1e',
            fg='white',  # Bright white
            font=('Segoe UI', 10, 'bold'),
            pady=10
        )
        files_label.pack()

        # Files listbox - dark theme
        files_frame = tk.Frame(self.root, bg='#2d2d30')
        files_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(files_frame, bg='#3e3e42', width=0)  # Invisible scrollbar
        scrollbar.pack(side='right', fill='y')

        self.files_listbox = tk.Listbox(
            files_frame,
            bg='black',  # Pure black background
            fg='white',  # Pure white text
            font=('Segoe UI', 9),
            selectbackground='#4068b8',  # Softer blue accent
            selectforeground='white',
            activestyle='none',
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            cursor='hand2'
        )
        self.files_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.files_listbox.yview)

        self.files_listbox.bind('<Double-Button-1>', self.copy_file_link)
        self.files_listbox.bind('<Return>', self.copy_file_link)

        # Logs section (collapsible)
        self.logs_visible = False
        self.logs_frame = None

        logs_toggle_btn = tk.Button(
            self.root,
            text="📊 Show Logs ▼",
            command=self.toggle_logs,
            bg='#2e2e32',  # Darker medium gray
            fg='#b0b0b0',  # Darker light gray
            font=('Segoe UI', 9),
            pady=5,
            cursor='hand2',
            relief='flat',
            bd=0
        )
        logs_toggle_btn.pack(fill='x', padx=10, pady=(0, 10))

        self.logs_toggle_btn = logs_toggle_btn

        # Status bar - dark
        status_bar = tk.Frame(self.root, bg='#2d2d30', height=25)
        status_bar.pack(fill='x', side='bottom')

        self.status_bar_label = tk.Label(
            status_bar,
            text="Ready",
            bg='#2d2d30',
            fg='#707070',  # Darker dimmed
            font=('Segoe UI', 8),
            anchor='w',
            padx=10
        )
        self.status_bar_label.pack(fill='x')

        # Initial refresh
        self.refresh_status()
        self.refresh_files()

    def toggle_logs(self):
        """Show/hide logs section"""
        if self.logs_visible:
            # Hide logs
            if self.logs_frame:
                self.logs_frame.destroy()
                self.logs_frame = None
            self.logs_toggle_btn.config(text="📊 Show Logs ▼")
            self.logs_visible = False
            self.root.geometry("400x600")
        else:
            # Show logs - dark theme
            self.logs_frame = tk.Frame(self.root, bg='#1e1e1e')
            self.logs_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            # Create frame for logs with invisible scrollbar
            logs_scroll_frame = tk.Frame(self.logs_frame, bg='#1e1e1e')
            logs_scroll_frame.pack(fill='both', expand=True, pady=(0, 5))

            logs_scrollbar = tk.Scrollbar(logs_scroll_frame, width=0)  # Invisible scrollbar
            logs_scrollbar.pack(side='right', fill='y')

            self.logs_text = tk.Text(
                logs_scroll_frame,
                bg='black',  # Pure black background
                fg='white',  # Pure white text
                font=('Consolas', 8),
                height=10,
                wrap=tk.WORD,
                relief='flat',
                bd=0,
                yscrollcommand=logs_scrollbar.set
            )
            self.logs_text.pack(side='left', fill='both', expand=True)
            logs_scrollbar.config(command=self.logs_text.yview)

            # Button panel for log controls
            log_btn_frame = tk.Frame(self.logs_frame, bg='#1e1e1e')
            log_btn_frame.pack(fill='x')

            tk.Button(log_btn_frame, text="🔄 Refresh", command=self.update_logs,
                     bg='#4068b8', fg='white', font=('Segoe UI', 8),
                     padx=10, pady=3, relief='flat', bd=0, cursor='hand2').pack(side='left', padx=2)

            tk.Button(log_btn_frame, text="🗑️ Clear Activity", command=self.clear_logs,
                     bg='#b87858', fg='white', font=('Segoe UI', 8),
                     padx=10, pady=3, relief='flat', bd=0, cursor='hand2').pack(side='left', padx=2)

            tk.Button(log_btn_frame, text="🧹 Clear ALL", command=self.clear_all_logs,
                     bg='#d43737', fg='white', font=('Segoe UI', 8),
                     padx=10, pady=3, relief='flat', bd=0, cursor='hand2').pack(side='left', padx=2)

            # Add current logs
            self.update_logs()

            self.logs_toggle_btn.config(text="📊 Hide Logs ▲")
            self.logs_visible = True
            self.root.geometry("400x800")

    def add_activity_log(self, message):
        """Add activity log entry"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.activity_logs.append(log_entry)

        # Keep last 100 entries
        if len(self.activity_logs) > 100:
            self.activity_logs.pop(0)

        # Update logs display if visible
        if self.logs_visible and hasattr(self, 'logs_text'):
            try:
                self.logs_text.insert(tk.END, log_entry + "\n")
                self.logs_text.see(tk.END)
            except:
                pass

    def update_logs(self):
        """Update logs display"""
        if not self.logs_visible or not self.logs_frame:
            return

        self.logs_text.delete(1.0, tk.END)

        # Show current status header
        if self.is_server_running():
            tunnel_url = self.get_tunnel_url()
            if tunnel_url:
                self.logs_text.insert(tk.END, f"🟢 Server Online | Tunnel: {tunnel_url}\n")
            else:
                self.logs_text.insert(tk.END, "🟢 Server Online | ⏳ Waiting for tunnel...\n")
        else:
            self.logs_text.insert(tk.END, "⚫ Server Offline\n")

        self.logs_text.insert(tk.END, "=" * 70 + "\n\n")

        # Show activity logs
        if self.activity_logs:
            for log in self.activity_logs:
                self.logs_text.insert(tk.END, log + "\n")
        else:
            self.logs_text.insert(tk.END, "No activity yet. Logs will appear here when:\n")
            self.logs_text.insert(tk.END, "  • Server starts/stops\n")
            self.logs_text.insert(tk.END, "  • Files are uploaded\n")
            self.logs_text.insert(tk.END, "  • Links are copied\n")
            self.logs_text.insert(tk.END, "  • Tunnel URL changes\n")

        self.logs_text.see(tk.END)

    def clear_logs(self):
        """Clear activity logs only"""
        self.activity_logs = []
        if hasattr(self, 'logs_text'):
            self.update_logs()
        self.add_activity_log("🗑️ Activity logs cleared")

    def clear_all_logs(self):
        """Clear all logs including server access logs"""
        self.activity_logs = []
        self.last_access_count = 0

        # Clear server access log file
        if self.access_log_path.exists():
            try:
                with open(self.access_log_path, 'w') as f:
                    json.dump([], f)
            except:
                pass

        if hasattr(self, 'logs_text'):
            self.update_logs()

        self.add_activity_log("🧹 ALL logs cleared (activity + access logs)")

    def start_activity_monitor(self):
        """Monitor server activity and log events"""
        def monitor():
            while True:
                try:
                    # Monitor file uploads
                    current_files = self.get_files()
                    current_count = len(current_files)

                    if current_count > self.last_file_count:
                        # New file uploaded
                        new_file = current_files[0]  # Most recent
                        self.add_activity_log(f"📤 New upload: {new_file['name']} ({new_file['size']})")
                        self.last_file_count = current_count
                    elif current_count < self.last_file_count:
                        # File deleted
                        self.add_activity_log(f"🗑️ File deleted (total now: {current_count})")
                        self.last_file_count = current_count

                    # Monitor tunnel URL changes
                    current_tunnel = self.get_tunnel_url()
                    if current_tunnel != self.last_tunnel_url:
                        if current_tunnel:
                            self.add_activity_log(f"🌐 Tunnel URL updated: {current_tunnel}")
                        self.last_tunnel_url = current_tunnel

                    # Monitor access logs (NEW!)
                    if self.access_log_path.exists():
                        try:
                            with open(self.access_log_path, 'r') as f:
                                access_logs = json.load(f)

                            current_access_count = len(access_logs)
                            if current_access_count > self.last_access_count:
                                # New access events
                                new_events = access_logs[self.last_access_count:]
                                for event in new_events:
                                    self.log_access_event(event)
                                self.last_access_count = current_access_count
                        except:
                            pass

                except:
                    pass

                time.sleep(2)

        threading.Thread(target=monitor, daemon=True).start()

    def log_access_event(self, event):
        """Format and log access events"""
        event_type = event.get("event", "unknown")
        filename = event.get("filename", "unknown")
        source = event.get("source", "unknown")
        ip = event.get("ip", "unknown")

        # Get just the time from timestamp
        try:
            timestamp = event.get("timestamp", "")
            time_only = timestamp[11:19] if len(timestamp) > 19 else ""
        except:
            time_only = ""

        # Format based on event type
        if event_type == "share_link_opened":
            emoji = "🔗"
            msg = f"Share link opened: {filename}"
        elif event_type == "preview_viewed":
            emoji = "👁️"
            msg = f"Preview viewed: {filename}"
        elif event_type == "download":
            emoji = "⬇️"
            msg = f"Downloaded: {filename}"
        elif event_type == "inline_view":
            emoji = "▶️"
            msg = f"Viewed inline: {filename}"
        else:
            emoji = "❓"
            msg = f"{event_type}: {filename}"

        # Add source indicator
        if source == "external":
            source_emoji = "🌍"
        else:
            source_emoji = "🏠"

        self.add_activity_log(f"{emoji} {msg} ({source_emoji} {source})")

    def is_server_running(self):
        """Check if server is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'python' in proc.info['name'].lower():
                    if any('server.py' in str(arg) for arg in cmdline):
                        return True
            except:
                pass
        return False

    def get_tunnel_url(self):
        """Get current tunnel URL"""
        if self.tunnel_url_path.exists():
            try:
                return self.tunnel_url_path.read_text().strip()
            except:
                return None
        return None

    def get_files(self):
        """Get recent uploaded files"""
        if not self.metadata_path.exists():
            return []

        try:
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)

            files = []
            for file_id, info in metadata.items():
                files.append({
                    'id': file_id,
                    'name': info['original_name'],
                    'size': self.human_size(info['size']),
                    'time': info['upload_time'][:16].replace('T', ' ')
                })

            files.sort(key=lambda x: x['time'], reverse=True)
            return files[:10]
        except:
            return []

    def human_size(self, nbytes):
        """Convert bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} PB"

    def refresh_status(self):
        """Refresh server status display"""
        running = self.is_server_running()
        tunnel_url = self.get_tunnel_url()

        if running:
            self.status_label.config(text="🟢 Server Running", fg='#3eb89a')  # Softer teal
            self.start_btn.config(state='disabled', bg='#2e2e32')  # Darker disabled gray
            self.stop_btn.config(state='normal', bg='#d43737')  # Softer red

            if tunnel_url:
                # Shorten URL for display
                display_url = tunnel_url.replace('https://', '')
                if len(display_url) > 45:
                    display_url = display_url[:42] + '...'
                self.tunnel_label.config(text=f"🌐 {display_url}", fg='#4068b8')  # Softer blue
            else:
                self.tunnel_label.config(text="⏳ Waiting for tunnel URL...", fg='#b87858')  # Softer orange
        else:
            self.status_label.config(text="⚫ Server Stopped", fg='#707070')  # Darker dimmed gray
            self.tunnel_label.config(text="Click 'Start Server' to begin", fg='#707070')
            self.start_btn.config(state='normal', bg='#3eb89a')  # Softer teal
            self.stop_btn.config(state='disabled', bg='#2e2e32')  # Darker disabled gray

        self.refresh_files()
        if self.logs_visible:
            self.update_logs()

        self.status_bar_label.config(text=f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

    def refresh_files(self):
        """Refresh files list"""
        self.files_listbox.delete(0, tk.END)

        files = self.get_files()
        if not files:
            self.files_listbox.insert(tk.END, "  No files uploaded yet")
            self.files_listbox.config(fg='#707070')  # Darker dimmed gray for empty state
        else:
            self.files_listbox.config(fg='white')  # Pure white text
            for file in files:
                display = f"  📄 {file['name']}"
                if len(display) > 50:
                    display = display[:47] + "..."
                self.files_listbox.insert(tk.END, display)
                # Store file ID in a hidden way
                self.files_listbox.itemconfig(tk.END, {'selectbackground': '#4068b8'})  # Softer blue

    def copy_file_link(self, event=None):
        """Copy selected file's share link"""
        selection = self.files_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        files = self.get_files()

        if idx >= len(files):
            return

        file = files[idx]
        tunnel_url = self.get_tunnel_url()

        if not tunnel_url:
            self.status_bar_label.config(text="⚠ No tunnel URL available - is server running?")
            return

        if not self.is_server_running():
            self.status_bar_label.config(text="⚠ Server is offline - starting...")
            self.start_server()
            return

        link = f"{tunnel_url}/files/{file['id']}"
        pyperclip.copy(link)
        self.status_bar_label.config(text=f"✓ Copied link for '{file['name']}'")
        self.add_activity_log(f"📋 Copied share link: {file['name']}")


    def open_upload(self):
        """Open upload page in browser"""
        if not self.is_server_running():
            self.status_bar_label.config(text="⚠ Starting server first...")
            self.add_activity_log("⚠ Server offline, starting before opening upload page...")
            self.start_server()
            time.sleep(3)

        # Open browser without CMD window flash
        subprocess.Popen(["cmd", "/c", "start", "http://localhost:713"],
                        creationflags=subprocess.CREATE_NO_WINDOW)
        self.status_bar_label.config(text="Opened upload page in browser")
        self.add_activity_log("🌐 Opened upload page in browser")

    def start_server(self):
        """Start server in background"""
        self.status_bar_label.config(text="⏳ Starting server...")
        self.status_label.config(text="⏳ Starting...", fg='#f39c12')
        self.add_activity_log("▶ Starting server...")

        def start():
            try:
                # Kill existing first
                self.stop_server()
                time.sleep(1)

                # Start server
                self.server_process = subprocess.Popen(
                    ['python', 'server.py'],
                    cwd=str(self.server_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.add_activity_log("  ✓ Flask server process started")

                time.sleep(2)

                # Start tunnel
                self.tunnel_process = subprocess.Popen(
                    ['python', 'tunnel_runner.py'],
                    cwd=str(self.server_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.add_activity_log("  ✓ Cloudflare tunnel started")

                # Wait and refresh
                time.sleep(8)
                self.refresh_status()

                if self.is_server_running():
                    self.status_bar_label.config(text="✓ Server started successfully!")
                    self.add_activity_log("✓ Server online and ready!")
                else:
                    self.status_bar_label.config(text="⚠ Server failed to start")
                    self.add_activity_log("⚠ Server failed to start")
            except Exception as e:
                self.status_bar_label.config(text=f"❌ Error: {str(e)}")
                self.add_activity_log(f"❌ Error starting server: {str(e)}")

        threading.Thread(target=start, daemon=True).start()

    def stop_server(self):
        """Stop server"""
        self.status_bar_label.config(text="Stopping server...")
        self.add_activity_log("⏹ Stopping server...")

        try:
            # Kill spawned processes
            if self.server_process:
                self.server_process.kill()
                self.server_process = None

            if self.tunnel_process:
                self.tunnel_process.kill()
                self.tunnel_process = None

            # Kill any remaining
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'python' in proc.info['name'].lower():
                        if any(('server.py' in str(arg) or 'tunnel_runner.py' in str(arg)) for arg in cmdline):
                            proc.kill()
                            killed_count += 1
                except:
                    pass

            # Kill cloudflared without CMD window flash
            subprocess.Popen(["taskkill", "/F", "/IM", "cloudflared.exe"],
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            time.sleep(1)
            self.refresh_status()
            self.status_bar_label.config(text="✓ Server stopped")
            self.add_activity_log(f"✓ Server stopped ({killed_count} processes killed)")

            # Auto-clear all logs when server stops
            self.add_activity_log("🧹 Auto-clearing logs (server stopped)...")
            time.sleep(0.5)
            self.clear_all_logs()
            self.refresh_files()  # Clear file list display

        except Exception as e:
            self.status_bar_label.config(text=f"Error: {str(e)}")
            self.add_activity_log(f"❌ Error stopping server: {str(e)}")

    def start_auto_refresh(self):
        """Auto-refresh status every 5 seconds"""
        def auto_refresh():
            while True:
                time.sleep(5)
                try:
                    self.refresh_status()
                except:
                    pass

        threading.Thread(target=auto_refresh, daemon=True).start()

    def run(self):
        """Run the app"""
        self.root.mainloop()

if __name__ == "__main__":
    app = LocalServerMenu()
    app.run()
