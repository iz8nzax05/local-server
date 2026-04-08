"""
LocalServer Menu UI — Theme Test (Demo Only)
Clone of the menu window from C:\LocalServer\menu_app.py.
Uses CustomTkinter for a polished, modern look. Buttons and server do nothing.
"""
import customtkinter as ctk

# Modern dark theme with teal accent
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")  # Teal/green accent for Start/primary actions

# Font for labels/buttons that include emojis. Segoe UI Emoji (Windows) renders emojis
# at the same size and baseline as the text — fixes small/slanted emoji in CTkButton.
def _emoji_font(size=11, weight="normal"):
    return ctk.CTkFont(family="Segoe UI Emoji", size=size, weight=weight)


class MenuUIDemo(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LocalServer — Theme Test")
        self.logs_visible = False
        # Same as og: 400x600 when logs hidden, 400x800 when shown
        self.geometry("420x620")
        self.minsize(380, 560)

        # Main container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_controls()
        self._build_files_section()
        self._build_logs_toggle()
        self._build_status_bar()

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

        # Buttons with emojis: use Segoe UI Emoji font so emojis render big and aligned (not small/slanted)
        self.start_btn = ctk.CTkButton(
            controls,
            text="▶ START SERVER",
            command=self._noop,
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
            command=self._noop,
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
            command=self._noop,
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
            command=self._noop,
            height=36,
            font=_emoji_font(size=11),
            fg_color=("#3d3d40", "#383838"),
            hover_color=("#505052", "#454545"),
            text_color="#ffffff",
        )
        refresh_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

    def _build_files_section(self):
        # Centered; emoji font so 📁 matches og
        files_label = ctk.CTkLabel(
            self,
            text="📁 RECENT FILES",
            font=_emoji_font(size=11, weight="bold"),
            text_color="#ffffff",
            anchor="center",
        )
        files_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 4))

        files_container = ctk.CTkFrame(
            self,
            fg_color=("#2d2d30", "#252526"),
            corner_radius=6,
        )
        files_container.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.grid_rowconfigure(3, weight=1)
        files_container.grid_columnconfigure(0, weight=1)
        files_container.grid_rowconfigure(0, weight=1)

        # Scrollable list — black background, white text (like original)
        self.files_list = ctk.CTkScrollableFrame(
            files_container,
            fg_color="black",
            corner_radius=4,
        )
        self.files_list.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.files_list.grid_columnconfigure(0, weight=1)
        # Thin scrollbar like og (original uses width=0)
        try:
            self.files_list._scrollbar.configure(width=8)
        except Exception:
            pass

        # List content left-aligned; larger font so black-box text matches og readability
        items = [
            ("  No files uploaded yet", "#909090"),
            ("  📄 example-document.pdf", "#ffffff"),
            ("  📄 image.png", "#ffffff"),
        ]
        for text, color in items:
            lbl = ctk.CTkLabel(
                self.files_list,
                text=text,
                font=_emoji_font(size=13),
                text_color=color,
                anchor="w",
            )
            lbl.grid(sticky="w", pady=2)
            self.files_list.grid_columnconfigure(0, weight=1)

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

        # Logs section — collapsible like og; hidden by default
        # Og: Text height=10 lines (~160px), window 400x600 -> 400x800 when shown
        self.logs_container = ctk.CTkFrame(self, fg_color="transparent")
        self.logs_container.grid(row=5, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.logs_container.grid_columnconfigure(0, weight=1)
        self.logs_container.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(5, weight=0)

        # Log control buttons: emoji font so 🔄 🗑️ 🧹 match og (big, clean, not slanted)
        log_btn_frame = ctk.CTkFrame(self.logs_container, fg_color="transparent")
        log_btn_frame.grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkButton(
            log_btn_frame,
            text="🔄 Refresh",
            command=self._noop,
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
            command=self._noop,
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
            command=self._noop,
            height=26,
            font=_emoji_font(size=10),
            fg_color=("#d43737", "#a83535"),
            hover_color=("#c73e3e", "#8f2b2b"),
            text_color="#ffffff",
            width=80,
        ).pack(side="left", padx=2)

        # Logs text — larger font so black-box text matches og readability
        self.logs_text = ctk.CTkTextbox(
            self.logs_container,
            height=160,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="black",
            text_color="#ffffff",
            border_width=0,
            corner_radius=4,
        )
        self.logs_text.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        # Thin scrollbar like og
        try:
            self.logs_text._y_scrollbar.configure(width=8)
        except Exception:
            pass
        # Exact placeholder from original menu_app.py update_logs()
        self.logs_text.insert("1.0", "⚫ Server Offline\n")
        self.logs_text.insert("2.0", "=" * 70 + "\n\n")
        self.logs_text.insert("4.0", "No activity yet. Logs will appear here when:\n")
        self.logs_text.insert("5.0", "  • Server starts/stops\n")
        self.logs_text.insert("6.0", "  • Files are uploaded\n")
        self.logs_text.insert("7.0", "  • Links are copied\n")
        self.logs_text.insert("8.0", "  • Tunnel URL changes\n")
        self.logs_text.configure(state="disabled")

        # Start with logs hidden (same as og)
        self.logs_container.grid_remove()

    def _toggle_logs(self):
        """Show/hide logs section — same behavior as original."""
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

    def _build_status_bar(self):
        status_bar = ctk.CTkFrame(self, fg_color=("#2d2d30", "#252526"), height=28, corner_radius=0)
        status_bar.grid(row=6, column=0, sticky="ew")
        status_bar.grid_propagate(False)
        status_bar.grid_columnconfigure(0, weight=1)

        self.status_bar_label = ctk.CTkLabel(
            status_bar,
            text="Ready — Theme test (no server)",
            font=ctk.CTkFont(size=10),
            text_color=("#6b6b6b", "#6d6d6d"),
            anchor="w",
        )
        self.status_bar_label.grid(row=0, column=0, sticky="w", padx=12, pady=6)

    def _noop(self):
        """Buttons do nothing — demo only."""
        pass

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    app = MenuUIDemo()
    app.run()
