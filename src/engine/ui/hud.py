from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
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
        expanded_width: int | None = None,
        expanded_height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = config_path or (Path(__file__).resolve().parents[3] / "config.json")
        hud_cfg = self._load_hud_config()

        # Enforce configurable minimum dimension lock
        cfg_min_w = hud_cfg.get("min_width", 340)
        cfg_min_h = hud_cfg.get("min_height", 240)
        self.min_width: int = max(280, int(min_width if min_width is not None else cfg_min_w))
        self.min_height: int = max(180, int(min_height if min_height is not None else cfg_min_h))

        self.collapsed_width = collapsed_width
        self.collapsed_height = collapsed_height

        # Resizable expanded dimensions (persisted from config or initialized)
        cfg_exp_w = hud_cfg.get("expanded_width", 380)
        cfg_exp_h = hud_cfg.get("expanded_height", 340)
        target_exp_w = int(expanded_width if expanded_width is not None else cfg_exp_w)
        target_exp_h = int(expanded_height if expanded_height is not None else cfg_exp_h)
        self.expanded_width: int = max(self.min_width, target_exp_w)
        self.expanded_height: int = max(self.min_height, target_exp_h)

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
        self.resize_grip: tk.Label | None = None
        self.bottom_resize_bar: tk.Frame | None = None

        self._thread: threading.Thread | None = None
        self._drag_data: dict[str, int | bool] = {"x": 0, "y": 0, "moved": False}
        self._resize_data: dict[str, int | bool] = {
            "start_x": 0,
            "start_y": 0,
            "start_w": 0,
            "start_h": 0,
            "resizing": False,
        }
        self._is_running: bool = False
        self._pulse_active: bool = False
        self._pulse_state: bool = False

    def _load_hud_config(self) -> dict:
        """Reads HUD dimension parameters from config.json safely."""
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data.get("hud"), dict):
                        return data["hud"]
            except Exception as e:
                logger.warning("Could not read HUD config: %s", e)
        return {}

    def _save_geometry_to_config(self) -> None:
        """Persists custom HUD dimensions to config.json."""
        if not self.config_path:
            return
        try:
            cfg = {}
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            if "hud" not in cfg or not isinstance(cfg["hud"], dict):
                cfg["hud"] = {}

            cfg["hud"]["expanded_width"] = self.expanded_width
            cfg["hud"]["expanded_height"] = self.expanded_height
            cfg["hud"]["min_width"] = self.min_width
            cfg["hud"]["min_height"] = self.min_height

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            logger.info(
                "Saved custom HUD layout: %dx%d (min: %dx%d)",
                self.expanded_width, self.expanded_height, self.min_width, self.min_height
            )
        except Exception as e:
            logger.warning("Could not save HUD layout to config: %s", e)

    def set_min_dimensions(self, min_width: int, min_height: int) -> tuple[int, int]:
        """Sets fixed minimum dimension constraints with mathematical safety floor."""
        self.min_width = max(280, int(min_width))
        self.min_height = max(180, int(min_height))
        if self.expanded_width < self.min_width or self.expanded_height < self.min_height:
            self.set_dimensions(self.expanded_width, self.expanded_height)
        return self.min_width, self.min_height

    def set_dimensions(self, width: int, height: int) -> tuple[int, int]:
        """Applies dimensions clamped strictly against min_width and min_height."""
        clamped_w = max(self.min_width, int(width))
        clamped_h = max(self.min_height, int(height))
        self.expanded_width = clamped_w
        self.expanded_height = clamped_h
        if self.root and self.is_expanded:
            cur_x = self.root.winfo_x()
            cur_y = self.root.winfo_y()
            self.root.geometry(f"{clamped_w}x{clamped_h}+{cur_x}+{cur_y}")
            if self.top_canvas:
                self.top_canvas.configure(width=clamped_w)
            self._draw_pill()
        return clamped_w, clamped_h

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
        input_row.pack(fill="x", side="top")

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
        send_btn.pack(side="left")

        # Tokyo Night diagonal corner resize grip (◢)
        self.resize_grip = tk.Label(
            input_row,
            text="◢",
            bg="#1a1b26",
            fg="#7aa2f7",
            font=("Segoe UI", 8, "bold"),
            cursor="size_nw_se",
        )
        self.resize_grip.pack(side="right", padx=(4, 0))
        self.resize_grip.bind("<Button-1>", self._on_resize_start)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_drag)
        self.resize_grip.bind("<ButtonRelease-1>", self._on_resize_end)

        # Bottom subtle drag strip for vertical resizing
        self.bottom_resize_bar = tk.Frame(self.deck_frame, bg="#1a1b26", height=4, cursor="size_ns")
        self.bottom_resize_bar.pack(fill="x", side="bottom", pady=(2, 0))
        self.bottom_resize_bar.bind("<Button-1>", self._on_resize_start)
        self.bottom_resize_bar.bind("<B1-Motion>", self._on_resize_drag_vertical)
        self.bottom_resize_bar.bind("<ButtonRelease-1>", self._on_resize_end)

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

        cur_w = self.root.winfo_width() if self.root else self.collapsed_width
        if cur_w <= 1:
            cur_w = self.expanded_width if self.is_expanded else self.collapsed_width

        # Right-aligned symbol buttons (responsive to window width)
        # 1. Mute Button [ 🔊 / 🔇 ]
        mute_icon = "🔇" if self.is_muted else "🔊"
        self._create_canvas_button(cur_w - 110, 20, mute_icon, self._on_btn_mute, tags="btn_mute")

        # 2. Voice Button [ 🎙️ ]
        self._create_canvas_button(cur_w - 80, 20, "🎙️", self._on_btn_voice, tags="btn_voice")

        # 3. File Index Button [ 📁 ]
        self._create_canvas_button(cur_w - 50, 20, "📁", self._on_btn_file, tags="btn_file")

        # 4. Expand / Collapse Button [ ⤢ / ⤡ ]
        expand_icon = "⤡" if self.is_expanded else "⤢"
        self._create_canvas_button(cur_w - 20, 20, expand_icon, self.toggle_expand, tags="btn_expand")

    def _on_resize_start(self, event: tk.Event) -> None:
        """Captures initial screen position and dimensions at drag-resize start."""
        if not self.root:
            return
        self._resize_data["start_x"] = event.x_root
        self._resize_data["start_y"] = event.y_root
        self._resize_data["start_w"] = self.root.winfo_width()
        self._resize_data["start_h"] = self.root.winfo_height()
        self._resize_data["resizing"] = True

    def _on_resize_drag(self, event: tk.Event) -> None:
        """Dynamically resizes window diagonally with strict minimum dimension locks."""
        if not self.root or not self._resize_data.get("resizing", False):
            return

        dx = event.x_root - int(self._resize_data["start_x"])
        dy = event.y_root - int(self._resize_data["start_y"])

        new_w = int(self._resize_data["start_w"]) + dx
        new_h = int(self._resize_data["start_h"]) + dy

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        max_w = int(screen_w * 0.95)
        max_h = int(screen_h * 0.95)

        clamped_w = max(self.min_width, min(max_w, new_w))
        clamped_h = max(self.min_height, min(max_h, new_h))

        self.expanded_width = clamped_w
        self.expanded_height = clamped_h

        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{clamped_w}x{clamped_h}+{cur_x}+{cur_y}")

        if self.top_canvas:
            self.top_canvas.configure(width=clamped_w)
            self._draw_pill()

    def _on_resize_drag_vertical(self, event: tk.Event) -> None:
        """Dynamically resizes window height from bottom edge with minimum dimension lock."""
        if not self.root or not self._resize_data.get("resizing", False):
            return

        dy = event.y_root - int(self._resize_data["start_y"])
        new_h = int(self._resize_data["start_h"]) + dy

        screen_h = self.root.winfo_screenheight()
        max_h = int(screen_h * 0.95)
        clamped_h = max(self.min_height, min(max_h, new_h))

        self.expanded_height = clamped_h
        cur_w = self.root.winfo_width()
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"{cur_w}x{clamped_h}+{cur_x}+{cur_y}")

    def _on_resize_end(self, event: tk.Event) -> None:
        """Finalizes resizing and persists new geometry to config."""
        self._resize_data["resizing"] = False
        self._save_geometry_to_config()

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

    def _safe_after(self, delay_ms: int, func: Callable, *args: Any) -> None:
        """Safely dispatches callback to Tk mainloop or executes directly if outside mainloop."""
        if not self.root:
            return
        try:
            self.root.after(delay_ms, func, *args)
        except (RuntimeError, tk.TclError):
            try:
                func(*args)
            except Exception:
                pass

    def toggle_expand(self) -> None:
        """Toggles between collapsed 42px pill and expanded 340px card."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        """Smoothly expands window downward to reveal chat and input."""
        self.is_expanded = True
        self._safe_after(0, self._do_expand)

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
        self._safe_after(0, self._do_collapse)

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
            if not self.chat_display:
                return
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"{sender}: {text}\n\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

        self._safe_after(0, _do_append)

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

        self._safe_after(450, self._schedule_pulse)

    def on_state_change(self, old_state: State, new_state: State) -> None:
        """Thread-safe callback invoked by StateManager."""
        self.current_state_name = new_state.value
        self._safe_after(0, self._draw_pill)
        if self.root:
            self._safe_after(0, self.root.lift)
            self._safe_after(0, lambda: self.root.attributes("-topmost", True) if self.root else None)

    def show(self) -> None:
        if self.root:
            self._safe_after(0, self.root.deiconify)

    def hide(self) -> None:
        if self.root:
            self._safe_after(0, self.root.withdraw)

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
            self._safe_after(0, self.root.destroy)
            self.root = None
