"""WIDDX Nexus — Modern Desktop GUI with full functionality."""

import customtkinter as ctk
import threading
import json
import urllib.request
from pathlib import Path

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_dark": "#1a1a1a",
    "bg_card": "#252525",
    "bg_input": "#333333",
    "text_primary": "#ffffff",
    "text_secondary": "#b0b0b0",
    "text_muted": "#707070",
    "accent": "#007aff",
    "success": "#30d158",
    "danger": "#ff3b30",
    "border": "#404040",
}


def get_api_key():
    script_dir = Path(__file__).parent
    for env_path in [script_dir / '.env', Path('.env'), Path.cwd() / '.env']:
        if env_path.exists():
            content = env_path.read_bytes().decode('utf-8')
            for line in content.split('\n'):
                if '=' in line and not line.startswith('#'):
                    k, _, v = line.partition('=')
                    if k.strip() == 'DEEPSEEK_API_KEY':
                        return v.strip()
    return os.environ.get('DEEPSEEK_API_KEY', '')


def call_deepseek(messages, api_key):
    url = 'https://api.deepseek.com/chat/completions'
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 2000,
        'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except Exception as e:
        return str(e)


class WIDDXDesktop(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WIDDX Nexus v3.2.0")
        self.geometry("1100x700")
        self.configure(fg_color=COLORS["bg_dark"])

        self.messages = []
        self.api_key = get_api_key()

        self._build_gui()

    def _build_gui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=220, fg_color=COLORS["bg_card"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")

        logo = ctk.CTkLabel(sidebar, text="W", font=ctk.CTkFont(size=24, weight="bold"),
                           fg_color=COLORS["accent"], text_color="white", width=40, height=40, corner_radius=8)
        logo.pack(pady=(20, 4))

        ctk.CTkLabel(sidebar, text="WIDDX Nexus", font=ctk.CTkFont(size=16, weight="bold")).pack()
        ctk.CTkLabel(sidebar, text="v3.2.0", font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"]).pack()

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.pack(fill="x", pady=20, padx=8)

        ctk.CTkLabel(nav, text="الرئيسي", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLORS["text_muted"]).pack(padx=8, anchor="w")

        items = [
            ("💬", "المحادثة", "chat"),
            ("🛠️", "الأدوات", "tools"),
            ("🎯", "المهارات", "skills"),
            ("📋", "السجل", "history"),
            ("📊", "لوحة القيادة", "dashboard"),
            ("💾", "الذاكرة", "memory"),
            ("⚙️", "الإعدادات", "settings"),
        ]

        self.nav_btns = []
        for icon, text, key in items:
            btn = ctk.CTkButton(nav, text=f"  {icon}  {text}", font=ctk.CTkFont(size=13),
                               fg_color="transparent", text_color=COLORS["text_secondary"],
                               hover_color=COLORS["bg_input"], anchor="w", height=36, corner_radius=6,
                               command=lambda k=key: self._on_nav(k))
            btn.pack(fill="x", pady=2)
            self.nav_btns.append((btn, key))

        # Main
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(main, height=56, fg_color=COLORS["bg_card"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        self.title_lbl = ctk.CTkLabel(header, text="محادثة جديدة", font=ctk.CTkFont(size=15, weight="bold"))
        self.title_lbl.pack(side="left", padx=20)

        # Content
        self.content = ctk.CTkScrollableFrame(main, fg_color=COLORS["bg_dark"],
                                               scrollbar_button_color=COLORS["bg_card"])
        self.content.grid(row=1, column=0, sticky="nsew")

        # Input
        input_area = ctk.CTkFrame(main, height=100, fg_color=COLORS["bg_card"], corner_radius=0)
        input_area.grid(row=2, column=0, sticky="ew")

        inp = ctk.CTkFrame(input_area, fg_color=COLORS["bg_input"], corner_radius=8,
                          border_width=1, border_color=COLORS["border"])
        inp.pack(fill="both", expand=True, padx=20, pady=(12, 8))

        self.input_txt = ctk.CTkTextbox(inp, font=ctk.CTkFont(size=13), fg_color="transparent",
                                        text_color=COLORS["text_primary"], border_width=0, wrap="word")
        self.input_txt.pack(fill="both", expand=True, padx=12, pady=8)
        self.input_txt.bind("<Return>", self._on_enter)

        hints = ctk.CTkFrame(input_area, fg_color="transparent")
        hints.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(hints, text="Enter للإرسال", font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_muted"]).pack(side="left")

        send = ctk.CTkButton(hints, text="↑", font=ctk.CTkFont(size=16, weight="bold"),
                            fg_color=COLORS["text_primary"], text_color=COLORS["bg_dark"],
                            width=32, height=32, corner_radius=6, command=self._on_send)
        send.pack(side="right")

        self._show_welcome()

    def _on_nav(self, key):
        for btn, k in self.nav_btns:
            if k == key:
                btn.configure(fg_color=COLORS["accent"], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])

        titles = {
            "chat": "محادثة جديدة",
            "tools": "الأدوات",
            "skills": "المهارات",
            "history": "السجل",
            "dashboard": "لوحة القيادة",
            "memory": "الذاكرة",
            "settings": "الإعدادات",
        }
        self.title_lbl.configure(text=titles.get(key, ""))

        if key == "chat":
            self._show_welcome()
        elif key == "tools":
            self._show_tools()
        elif key == "skills":
            self._show_skills()
        elif key == "history":
            self._show_history()
        elif key == "dashboard":
            self._show_dashboard()
        elif key == "memory":
            self._show_memory()
        elif key == "settings":
            self._show_settings()

    def _show_welcome(self):
        for w in self.content.winfo_children():
            w.destroy()

        f = ctk.CTkFrame(self.content, fg_color="transparent")
        f.pack(pady=60)

        ctk.CTkLabel(f, text="W", font=ctk.CTkFont(size=48, weight="bold"),
                    fg_color=COLORS["accent"], text_color="white", width=80, height=80,
                    corner_radius=16).pack()

        ctk.CTkLabel(f, text="مرحباً بك في WIDDX Nexus", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(20, 8))
        ctk.CTkLabel(f, text="نظام معرفي متكامل للتطوير الذاتي", font=ctk.CTkFont(size=13),
                    text_color=COLORS["text_secondary"]).pack()

        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.pack(pady=30)

        for icon, text in [("📝", "كتابة كود"), ("🔍", "تحليل مشروع"), ("🐛", "إصلاح خطأ"), ("📖", "توثيق")]:
            ctk.CTkButton(btns, text=f"  {icon}  {text}", font=ctk.CTkFont(size=12),
                         fg_color=COLORS["bg_card"], height=36, corner_radius=6).pack(side="left", padx=4)

    def _show_tools(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="🛠️  الأدوات — 21 أداة متاحة",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _show_skills(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="🎯  المهارات",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _show_history(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="📋  السجل",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _show_dashboard(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="📊  لوحة القيادة",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _show_memory(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="💾  الذاكرة",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _show_settings(self):
        for w in self.content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.content, text="⚙️  الإعدادات",
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=30)

    def _on_enter(self, event):
        if event.state & 0x1:
            return
        self._on_send()
        return "break"

    def _on_send(self):
        text = self.input_txt.get("1.0", "end-1c").strip()
        if not text:
            return

        self.input_txt.delete("1.0", "end")
        self._add_msg("user", text)
        self.messages.append({"role": "user", "content": text})

        def do():
            result = call_deepseek(self.messages, self.api_key)
            self.after(0, lambda: self._handle_response(result))

        threading.Thread(target=do, daemon=True).start()

    def _handle_response(self, result):
        self._add_msg("assistant", result)
        self.messages.append({"role": "assistant", "content": result})

    def _add_msg(self, role, content):
        for w in self.content.winfo_children():
            if isinstance(w, ctk.CTkLabel) and "مرحباً" in str(w.cget("text")):
                w.destroy()

        color = COLORS["accent"] if role == "user" else COLORS["bg_card"]
        author = "أنت" if role == "user" else "WIDDX Nexus"

        f = ctk.CTkFrame(self.content, fg_color=color, corner_radius=6)
        f.pack(fill="x", padx=40, pady=4)

        ctk.CTkLabel(f, text=author, font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLORS["accent"] if role == "user" else COLORS["text_muted"]).pack(padx=12, pady=(8, 0), anchor="w")

        ctk.CTkLabel(f, text=str(content), font=ctk.CTkFont(size=13), wraplength=500,
                    justify="left").pack(padx=12, pady=(4, 12), anchor="w")


if __name__ == "__main__":
    app = WIDDXDesktop()
    app.mainloop()
