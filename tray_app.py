import json
import time
import threading
from pathlib import Path
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import pyperclip
import subprocess
import psutil
import os
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext

class ServerTrayApp:
    def __init__(self):
        self.server_dir = Path("C:/LocalServer")
        self.metadata_path = self.server_dir / "data/file_metadata.json"
        self.tunnel_url_path = self.server_dir / "tunnel_url.txt"
        self.server_process = None
        self.tunnel_process = None
        self.server_running = False
        self.logs = []
        self.log_window = None

        # Create tray icon
        self.icon = self.create_icon()
        self.tray_icon = pystray.Icon("LocalServer", self.icon, menu=self.create_menu())

        # Auto-start server on tray app launch
        self.log("Tray app starting...")
        self.start_server()

        # Watch for file changes and server status
        self.start_watchers()

    def log(self, message):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        if len(self.logs) > 200:  # Keep last 200 lines
            self.logs.pop(0)

        # Update log window if open
        if self.log_window and self.log_window.winfo_exists():
            try:
                self.log_text.insert(tk.END, log_entry + "\n")
                self.log_text.see(tk.END)
            except:
                pass

    def create_icon(self):
        # Green when running, gray when stopped
        color = 'green' if self.server_running else 'gray'
        image = Image.new('RGB', (64, 64), color=color)
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='white')
        draw.text((32, 32), "S", fill=color, anchor='mm')
        return image

    def update_icon_color(self):
        """Update icon color based on server status"""
        self.icon = self.create_icon()
        self.tray_icon.icon = self.icon

    def get_tunnel_url(self):
        """Get current tunnel URL"""
        if self.tunnel_url_path.exists():
            try:
                url = self.tunnel_url_path.read_text().strip()
                return url if url else None
            except:
                return None
        return None

    def is_server_running(self):
        """Check if server processes are actually running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'python' in proc.info['name'].lower():
                    if any('server.py' in str(arg) for arg in cmdline):
                        return True
            except:
                pass
        return False

    def get_files(self):
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

        except Exception as e:
            return []

    def human_size(self, nbytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} PB"

    def copy_share_link(self, file_id):
        """Copy link with fresh tunnel URL"""
        tunnel_url = self.get_tunnel_url()
        if tunnel_url and self.is_server_running():
            link = f"{tunnel_url}/files/{file_id}"
            pyperclip.copy(link)
            self.log(f"✓ Copied link for file {file_id}")
            self.show_notification("✓ Link Copied", "Share link in clipboard")
        else:
            self.log("⚠ Server offline, starting...")
            self.show_notification("Server Offline", "Starting server...")
            self.start_server()

    def open_upload_page(self):
        """Open localhost upload interface"""
        if self.is_server_running():
            # Open browser without CMD window flash
            subprocess.Popen(["cmd", "/c", "start", "http://localhost:713"],
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self.log("Opened upload page in browser")
        else:
            self.log("Server offline, starting first...")
            self.show_notification("Starting Server", "Please wait 10 seconds...")
            self.start_server()
            time.sleep(10)
            # Open browser without CMD window flash
            subprocess.Popen(["cmd", "/c", "start", "http://localhost:713"],
                           creationflags=subprocess.CREATE_NO_WINDOW)

    def show_notification(self, title, message):
        try:
            self.tray_icon.notify(title, message)
        except:
            pass

    def show_logs(self):
        """Open log window"""
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.focus_force()
            return

        self.log_window = tk.Tk()
        self.log_window.title("LocalServer - Server Logs")
        self.log_window.geometry("700x500")

        # Header with status
        header = tk.Frame(self.log_window, bg='#2c3e50', height=40)
        header.pack(fill='x')

        status_color = '#27ae60' if self.server_running else '#7f8c8d'
        status_text = "🟢 Server Running" if self.server_running else "⚫ Server Stopped"

        tk.Label(header, text=status_text, bg='#2c3e50', fg='white',
                font=('Segoe UI', 10, 'bold'), padx=10, pady=10).pack(side='left')

        tunnel_url = self.get_tunnel_url()
        if tunnel_url:
            tk.Label(header, text=f"Tunnel: {tunnel_url}", bg='#2c3e50', fg='#3498db',
                    font=('Segoe UI', 8), padx=10).pack(side='left')

        # Log text area
        self.log_text = scrolledtext.ScrolledText(
            self.log_window,
            wrap=tk.WORD,
            bg='#1e1e1e',
            fg='#d4d4d4',
            font=('Consolas', 9),
            insertbackground='white'
        )
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Add existing logs
        for log_entry in self.logs:
            self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)

        # Button panel
        button_frame = tk.Frame(self.log_window, bg='#ecf0f1', height=50)
        button_frame.pack(fill='x', side='bottom')

        tk.Button(button_frame, text="🔄 Refresh", command=self.refresh_log_window,
                 bg='#3498db', fg='white', font=('Segoe UI', 9),
                 padx=15, pady=5).pack(side='left', padx=5, pady=5)

        tk.Button(button_frame, text="🗑️ Clear Logs", command=self.clear_logs,
                 bg='#e74c3c', fg='white', font=('Segoe UI', 9),
                 padx=15, pady=5).pack(side='left', padx=5, pady=5)

        tk.Button(button_frame, text="📋 Copy Tunnel URL", command=self.copy_tunnel_url,
                 bg='#27ae60', fg='white', font=('Segoe UI', 9),
                 padx=15, pady=5).pack(side='left', padx=5, pady=5)

        self.log_window.mainloop()

    def refresh_log_window(self):
        """Refresh log window header"""
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.destroy()
            self.show_logs()

    def clear_logs(self):
        """Clear log display"""
        self.logs = []
        if self.log_text:
            self.log_text.delete(1.0, tk.END)
        self.log("Logs cleared")

    def copy_tunnel_url(self):
        """Copy current tunnel URL to clipboard"""
        tunnel_url = self.get_tunnel_url()
        if tunnel_url:
            pyperclip.copy(tunnel_url)
            self.log(f"✓ Copied tunnel URL: {tunnel_url}")
            self.show_notification("✓ Copied", "Tunnel URL in clipboard")
        else:
            self.log("⚠ No tunnel URL available")

    def create_files_menu(self):
        files = self.get_files()
        tunnel_url = self.get_tunnel_url()
        server_running = self.is_server_running()

        if not files:
            return [item("(No files uploaded yet)", lambda: None, enabled=False)]

        if not server_running:
            return [
                item("⚠ Server Offline", lambda: None, enabled=False),
                item("→ Click 'Start Server' below", lambda: None, enabled=False)
            ]

        if not tunnel_url:
            return [
                item("⏳ Waiting for tunnel...", lambda: None, enabled=False),
                item("→ Try 'Refresh' in 5 sec", lambda: None, enabled=False)
            ]

        menu_items = []
        for file in files:
            name = file['name']
            if len(name) > 30:
                name = name[:27] + "..."

            menu_items.append(
                item(f"{name}", lambda _, fid=file['id']: self.copy_share_link(fid))
            )

        return menu_items

    def create_menu(self):
        files_menu = self.create_files_menu()
        server_running = self.is_server_running()

        status_text = "🟢 RUNNING" if server_running else "⚫ STOPPED"

        return pystray.Menu(
            item(f"LocalServer - {status_text}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("📊 Show Logs", self.show_logs),
            item("📤 Upload Files", self.open_upload_page),
            pystray.Menu.SEPARATOR,
            item("📁 Recent Files (click to copy)", pystray.Menu(*files_menu)),
            pystray.Menu.SEPARATOR,
            item("🔄 Refresh", self.refresh_menu),
            item("▶ Start Server" if not server_running else "🔄 Restart", self.start_server),
            item("⏹ Stop Server", self.stop_server, enabled=server_running),
            pystray.Menu.SEPARATOR,
            item("❌ Exit (keeps server running)", self.quit_app)
        )

    def refresh_menu(self):
        """Refresh menu with current data"""
        self.server_running = self.is_server_running()
        self.update_icon_color()
        self.tray_icon.menu = self.create_menu()
        self.tray_icon.update_menu()

        tunnel_url = self.get_tunnel_url()
        if tunnel_url:
            self.log(f"🔄 Refreshed - Tunnel ready")
        else:
            self.log("🔄 Refreshed - No tunnel URL")

    def start_server(self):
        """Start server in background (no windows)"""
        self.log("Starting server...")

        # Kill any existing server first
        self.stop_server()
        time.sleep(1)

        try:
            # Start server.py in background
            self.server_process = subprocess.Popen(
                ['python', 'server.py'],
                cwd=str(self.server_dir),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.log("✓ Flask server started")

            # Start tunnel_runner.py in background
            time.sleep(2)
            self.tunnel_process = subprocess.Popen(
                ['python', 'tunnel_runner.py'],
                cwd=str(self.server_dir),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.log("✓ Cloudflare tunnel started")

            self.show_notification("⏳ Starting", "Server starting, wait 10 sec...")

            # Monitor server output in background
            def monitor_server():
                while self.server_process and self.server_process.poll() is None:
                    try:
                        line = self.server_process.stdout.readline()
                        if line:
                            self.log(f"[SERVER] {line.strip()}")
                    except:
                        break

            def monitor_tunnel():
                while self.tunnel_process and self.tunnel_process.poll() is None:
                    try:
                        line = self.tunnel_process.stdout.readline()
                        if line:
                            self.log(f"[TUNNEL] {line.strip()}")
                    except:
                        break

            threading.Thread(target=monitor_server, daemon=True).start()
            threading.Thread(target=monitor_tunnel, daemon=True).start()

            # Wait and verify startup
            def verify_startup():
                time.sleep(10)
                self.refresh_menu()
                if self.is_server_running():
                    tunnel_url = self.get_tunnel_url()
                    self.log(f"✓ Server ready! Tunnel: {tunnel_url or 'pending'}")
                    self.show_notification("✓ Ready!", "Server is running")
                else:
                    self.log("⚠ Server failed to start")
                    self.show_notification("⚠ Failed", "Server didn't start")

            threading.Thread(target=verify_startup, daemon=True).start()

        except Exception as e:
            self.log(f"❌ Start failed: {str(e)}")
            self.show_notification("❌ Error", f"Failed to start: {str(e)}")

    def stop_server(self):
        """Stop server processes"""
        self.log("Stopping server...")

        try:
            # Kill our spawned processes
            if self.server_process:
                self.server_process.kill()
                self.server_process = None

            if self.tunnel_process:
                self.tunnel_process.kill()
                self.tunnel_process = None

            # Kill any remaining server processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'python' in proc.info['name'].lower():
                        if any(('server.py' in str(arg) or 'tunnel_runner.py' in str(arg)) for arg in cmdline):
                            proc.kill()
                            self.log(f"Killed process: {proc.info['pid']}")
                except:
                    pass

            # Kill cloudflared without CMD window flash
            subprocess.Popen(["taskkill", "/F", "/IM", "cloudflared.exe"],
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.log("✓ Server stopped")
            self.show_notification("⏹ Stopped", "Server stopped, tray still running")
            time.sleep(1)
            self.refresh_menu()

        except Exception as e:
            self.log(f"⚠ Stop error: {str(e)}")

    def start_watchers(self):
        """Watch for file changes and server status"""
        def watcher():
            last_modified = 0
            last_server_status = False
            last_tunnel_url = None

            while True:
                try:
                    # Check if files changed
                    if self.metadata_path.exists():
                        current_modified = self.metadata_path.stat().st_mtime
                        if current_modified > last_modified:
                            last_modified = current_modified
                            self.log("📁 New file uploaded")
                            threading.Thread(target=self.refresh_menu, daemon=True).start()

                    # Check server status
                    current_server_status = self.is_server_running()
                    if current_server_status != last_server_status:
                        last_server_status = current_server_status
                        self.server_running = current_server_status
                        status = "online" if current_server_status else "offline"
                        self.log(f"🔄 Server {status}")
                        threading.Thread(target=self.refresh_menu, daemon=True).start()

                    # Check tunnel URL changes
                    current_tunnel_url = self.get_tunnel_url()
                    if current_tunnel_url != last_tunnel_url:
                        last_tunnel_url = current_tunnel_url
                        if current_tunnel_url:
                            self.log(f"🌐 Tunnel URL updated: {current_tunnel_url}")

                except:
                    pass

                time.sleep(3)

        threading.Thread(target=watcher, daemon=True).start()

    def quit_app(self):
        """Exit tray app (server keeps running)"""
        self.log("Tray app closing (server still running)")
        self.tray_icon.stop()

    def run(self):
        self.tray_icon.run()

if __name__ == "__main__":
    try:
        # Check if already running
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] != current_pid and 'python' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline', [])
                    if any('tray_app.py' in str(arg) for arg in cmdline):
                        print("Tray app already running!")
                        exit(0)
            except:
                pass

        app = ServerTrayApp()
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Tray app error: {e}")
