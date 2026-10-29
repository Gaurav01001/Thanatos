from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from engine.core.state import State

logger = logging.getLogger(__name__)


class FloatingHUD:
    """An expandable, translucent, borderless floating Mini-Deck HUD for Thanatos.
    
    Modes:
      - Collapsed (42px pill): Displays status dot, state name, and quick symbol buttons.
      - Expanded (340px card): Displays live chat history, file indexer, and text entry box.
    """

    STATE_COLORS: ClassVar[dict[str, str]] = {
        "idle": "#7aa2f7",       # Tokyo Night Soft Cyan
        "listening": "#7dcfff",  # Electric Blue (Active Ear)
        "transcribing": "#2ac3de", # Aqua Teal (Processing Speech)
        "thinking": "#e0af68",   # Warm Amber
        "speaking": "#9ece6a",   # Mint Green
        "executing": "#bb9af7",  # Purple
        "error": "#f7768e",      # Coral Red
    }

    def __init__(
        self,
        on_click: Callable[[], None] | None = None,
        on_mute_toggle: Callable[[], bool] | None = None,
        on_voice_toggle: Callable[[], None] | None = None,
        on_upload_file: Callable[[str], str] | None = None,
        on_submit_query: Callable[[str], None] | None = None,
        collapsed_width: int = 340,
        collapsed_height: int = 42,
        expanded_width: int = 380,
        expanded_height: int = 340,
    ) -> None:
        self.collapsed_width = collapsed_width
        self.collapsed_height = collapsed_height
        self.expanded_width = expanded_width
        self.expanded_height = expanded_height

        self.on_click = on_click
        self.on_mute_toggle = on_mute_toggle
        self.on_voice_toggle = on_voice_toggle
        self.on_upload_file = on_upload_file
        self.on_submit_query = on_submit_query

        self.current_state_name: str = "idle"
        self.is_muted: bool = False
        self.is_expanded: bool = False

        self.root: tk.Tk | None = None
        self.top_canvas: tk.Canvas | None = None
        self.deck_frame: tk.Frame | None = None
        self.chat_display: tk.Text | None = None
        self.entry_box: tk.Entry | None = None
        self.status_label: tk.Label | None = None

        self._thread: threading.Thread | None = None
        self._drag_data: dict[str, int | bool] = {"x": 0, "y": 0, "moved": False}
        self._is_running: bool = False
        self._pulse_active: bool = False
        self._pulse_state: bool = False

    def _setup_window(self) -> None:
        """Initializes the borderless, topmost, translucent Tkinter window."""
        self.root = tk.Tk()
        self.root.title("Thanatos Mini-Deck")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg="#1a1b26")

        # Position horizontally near the top of the primary monitor
        screen_w = self.root.winfo_screenwidth()
        x_pos = (screen_w - self.collapsed_width) // 2
        y_pos = 32
        self.root.geometry(f"{self.collapsed_width}x{self.collapsed_height}+{x_pos}+{y_pos}")

        # 1. Top bar canvas (Pill Header & Controls)
        self.top_canvas = tk.Canvas(
            self.root,
            width=self.collapsed_width,
            height=self.collapsed_height,
            bg="#1a1b26",
            highlightthickness=2,
            highlightbackground="#7aa2f7",
        )
        self.top_canvas.pack(fill="x", side="top")

        # Bind dragging & hotkeys
        self.top_canvas.bind("<Button-1>", self._on_mouse_down)
        self.top_canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.top_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.root.bind("<Escape>", lambda e: self.collapse())

        # 2. Expanded Mini-Deck Frame (Hidden by default)
        self.deck_frame = tk.Frame(self.root, bg="#1a1b26", padx=8, pady=6)

        # Chat scrollable view
        self.chat_display = tk.Text(
            self.deck_frame,
            height=10,
            bg="#16161e",
            fg="#c0caf5",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            padx=6,
            pady=6,
        )
        self.chat_display.pack(fill="both", expand=True, pady=(0, 4))
        self.chat_display.insert("end", "Thanatos Desktop Companion Ready.\nAsk a question or click 📁 to index files.\n\n")
        self.chat_display.configure(state="disabled")

        # Status note bar
        self.status_label = tk.Label(
            self.deck_frame,
            text="📁 Click 📁 to index PDF/Notes into RAG",
            bg="#1a1b26",
            fg="#7aa2f7",
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        # Bottom Entry & Send Row
        input_row = tk.Frame(self.deck_frame, bg="#1a1b26")
        input_row.pack(fill="x")

        self.entry_box = tk.Entry(
            input_row,
            bg="#24283b",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=("Segoe UI", 9),
            relief="flat",
        )
        self.entry_box.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 4))
        self.entry_box.bind("<Return>", lambda e: self._handle_submit())

        send_btn = tk.Button(
            input_row,
            text=" ⮞ ",
            bg="#7aa2f7",
            fg="#1a1b26",
            font=("Segoe UI Bold", 9),
            relief="flat",
            command=self._handle_submit,
            cursor="hand2",
        )
        send_btn.pack(side="right")

        # Map and stay on top
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()

        self._draw_pill()
        self._schedule_pulse()

    def _draw_pill(self) -> None:
        """Renders status dot, labels, and action buttons in the top canvas."""
        if not self.top_canvas:
            return

        self.top_canvas.delete("all")
        color = self.STATE_COLORS.get(self.current_state_name, "#7aa2f7")
        self.top_canvas.configure(highlightbackground=color)

        # Pulsing dot
        dot_color = color
        if self._pulse_active and self._pulse_state:
            dot_color = "#ffffff"

        self.top_canvas.create_oval(12, 14, 24, 26, fill=dot_color, outline="", tags="dot")

        # Dynamic State Title
        state_title = f"Thanatos · {self.current_state_name.upper()}"
        self.top_canvas.create_text(
            32, 20, anchor="w", text=state_title, fill="#c0caf5",
            font=("Segoe UI Semibold", 9), tags="title",
        )

        # Right-aligned symbol buttons
        # 1. Mute Button [ 🔊 / 🔇 ]
        mute_icon = "🔇" if self.is_muted else "🔊"
        self._create_canvas_button(205, 20, mute_icon, self._on_btn_mute, tags="btn_mute")

        # 2. Voice Button [ 🎙️ ]
        self._create_canvas_button(235, 20, "🎙️", self._on_btn_voice, tags="btn_voice")

        # 3. File Index Button [ 📁 ]
        self._create_canvas_button(265, 20, "📁", self._on_btn_file, tags="btn_file")

        # 4. Expand / Collapse Button [ ⤢ / ⤡ ]
        expand_icon = "⤡" if self.is_expanded else "⤢"
        self._create_canvas_button(295, 20, expand_icon, self.toggle_expand, tags="btn_expand")

    def _create_canvas_button(self, x: int, y: int, text: str, callback: Callable[[], None], tags: str) -> None:
        """Creates a clickable text button on the top canvas."""
        if not self.top_canvas:
            return
        btn_id = self.top_canvas.create_text(
            x, y, text=text, fill="#c0caf5", font=("Segoe UI", 10), tags=tags
        )
        self.top_canvas.tag_bind(btn_id, "<Button-1>", lambda e: callback())

    def _on_btn_mute(self) -> None:
        """Invoked when user clicks the mute button on the pill."""
        if self.on_mute_toggle:
            self.is_muted = self.on_mute_toggle()
        else:
            self.is_muted = not self.is_muted
        self._draw_pill()

    def _on_btn_voice(self) -> None:
        """Invoked when user clicks the microphone button."""
        if self.on_voice_toggle:
            self.on_voice_toggle()

    def _on_btn_file(self) -> None:
        """Opens file dialog and triggers document indexing."""
        if not self.root:
            return
        filepath = filedialog.askopenfilename(
            parent=self.root,
            title="Index Document into Thanatos RAG",
            filetypes=[
                ("Documents & Code", "*.pdf;*.txt;*.md;*.docx;*.py;*.json"),
                ("All Files", "*.*"),
            ],
        )
        if filepath and self.on_upload_file:
            self.expand()
            self.append_message("System", f"Indexing: {filepath}...")
            
            def _async_index():
                result = self.on_upload_file(filepath)
                self.append_message("Thanatos", result)

            threading.Thread(target=_async_index, daemon=True).start()

    def toggle_expand(self) -> None:
        """Toggles between collapsed 42px pill and expanded 340px card."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        """Smoothly expands window downward to reveal chat and input."""
        self.is_expanded = True
        if self.root:
            self.root.after(0, self._do_expand)

    def _do_expand(self) -> None:
        if not self.root or not self.deck_frame:
            return
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{self.expanded_width}x{self.expanded_height}+{cur_x}+{cur_y}")
        self.deck_frame.pack(fill="both", expand=True)
        if self.entry_box:
            self.entry_box.focus_set()
        self._draw_pill()

    def collapse(self) -> None:
        """Shrinks back into the discreet 42px top pill."""
        self.is_expanded = False
        if self.root:
            self.root.after(0, self._do_collapse)

    def _do_collapse(self) -> None:
        if not self.root or not self.deck_frame:
            return
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.deck_frame.pack_forget()
        self.root.geometry(f"{self.collapsed_width}x{self.collapsed_height}+{cur_x}+{cur_y}")
        self._draw_pill()

    def append_message(self, sender: str, text: str) -> None:
        """Thread-safe method to append a message to the chat view."""
        if not self.root or not self.chat_display:
            return

        def _do_append():
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"{sender}: {text}\n\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

        self.root.after(0, _do_append)

    def _handle_submit(self) -> None:
        """Submits user text query from the expanded entry box."""
        if not self.entry_box:
            return
        text = self.entry_box.get().strip()
        if not text:
            return

        self.entry_box.delete(0, "end")
        self.append_message("You", text)

        if self.on_submit_query:
            threading.Thread(target=self.on_submit_query, args=(text,), daemon=True).start()

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["moved"] = False

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if not self.root:
            return
        dx = event.x - int(self._drag_data["x"])
        dy = event.y - int(self._drag_data["y"])
        if abs(dx) > 3 or abs(dy) > 3:
            self._drag_data["moved"] = True
            new_x = self.root.winfo_x() + dx
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"+{new_x}+{new_y}")

    def _on_mouse_up(self, event: tk.Event) -> None:
        # If user clicked on pill title/dot without dragging, trigger default click action
        if not self._drag_data.get("moved", False) and event.x < 190 and self.on_click:
            self.on_click()

    def _schedule_pulse(self) -> None:
        """Schedules gentle pulsing animations during active states."""
        if not self.root:
            return

        self._pulse_active = self.current_state_name in ("thinking", "speaking", "listening", "transcribing")
        if self._pulse_active:
            self._pulse_state = not self._pulse_state
            self._draw_pill()
        elif self._pulse_state:
            self._pulse_state = False
            self._draw_pill()

        self.root.after(450, self._schedule_pulse)

    def on_state_change(self, old_state: State, new_state: State) -> None:
        """Thread-safe callback invoked by StateManager."""
        self.current_state_name = new_state.value
        if self.root:
            self.root.after(0, self._draw_pill)
            self.root.after(0, self.root.lift)
            self.root.after(0, lambda: self.root.attributes("-topmost", True))

    def show(self) -> None:
        if self.root:
            self.root.after(0, self.root.deiconify)

    def hide(self) -> None:
        if self.root:
            self.root.after(0, self.root.withdraw)

    def start(self) -> None:
        """Starts the HUD in a dedicated daemon thread."""
        if self._is_running:
            return

        self._is_running = True

        def _runner():
            self._setup_window()
            if self.root:
                self.root.mainloop()

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()
        logger.info("Floating HUD active on screen")

    def stop(self) -> None:
        """Closes and destroys the HUD window cleanly."""
        self._is_running = False
        if self.root:
            try:
                self.root.after(0, self.root.destroy)
            except Exception:  # noqa: BLE001, S110
                pass
            self.root = None
