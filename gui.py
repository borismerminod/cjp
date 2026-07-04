"""Interface graphique Tkinter pour l'agent de code."""

import dataclasses
import gc
import json
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import psutil

from config import load_config
from context_manager import ContextManager
from llm_client import LLMClient
from markdown_render import render_markdown
from syntax_highlight import highlight_code
from think_splitter import ThinkStreamSplitter

KNOWN_MODELS_PATH = Path(__file__).parent / "known_models.json"
SESSION_TITLES_PATH = Path(__file__).parent / "session_titles.json"
CODE_BLOCK_RE = re.compile(r"```[ \t]*(\w*)\n(.*?)```", re.DOTALL)
_PROCESS = psutil.Process()


def load_known_models() -> dict:
    try:
        data = json.loads(KNOWN_MODELS_PATH.read_text(encoding="utf-8"))
        data.setdefault("models", [])
        data.setdefault("last_used", None)
        return data
    except Exception:
        return {"models": [], "last_used": None}


def save_known_models(data: dict) -> None:
    KNOWN_MODELS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session_titles() -> dict:
    try:
        return json.loads(SESSION_TITLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_session_titles(data: dict) -> None:
    SESSION_TITLES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def format_session_label(session_id: str, titles: dict) -> str:
    custom_title = titles.get(session_id)
    if custom_title:
        return custom_title
    try:
        return datetime.strptime(session_id, "%Y%m%d-%H%M%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return session_id


class ChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("cjp")
        self.root.geometry("1100x700")

        self.event_queue: queue.Queue = queue.Queue()
        self.state = "loading"  # "loading" | "generating" | "idle"
        self.client: LLMClient | None = None
        self.current_model_path: str | None = None
        self._pending_answer = ""
        self._reasoning_toggle_inserted = None
        self._stop_event = threading.Event()
        self._gen_start_time = 0.0
        self._gen_token_count = 0
        self._current_tps_text = ""
        self._current_mem_text = ""

        self.base_config = load_config()
        self.known_models = load_known_models()
        self._seed_known_models_with_default()
        self.session_titles = load_session_titles()

        self.context = ContextManager(self.base_config.sessions_dir, self.base_config.max_context_chars)

        self._build_widgets()
        self._refresh_model_combobox()
        self._refresh_sidebar()

        self.root.after(50, self._poll_queue)
        self._start_resource_polling()
        self.start_model_load(self._initial_model_path())

    # ------------------------------------------------------------------ setup

    def _seed_known_models_with_default(self) -> None:
        default_path = str(self.base_config.model_path)
        if not any(m["path"] == default_path for m in self.known_models["models"]):
            self.known_models["models"].append({"path": default_path, "label": Path(default_path).stem})
            save_known_models(self.known_models)

    def _initial_model_path(self) -> str:
        last_used = self.known_models.get("last_used")
        if last_used and Path(last_used).is_file():
            return last_used
        return str(self.base_config.model_path)

    def _build_widgets(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        top_bar = ttk.Frame(self.root, padding=6)
        top_bar.pack(side="top", fill="x")

        ttk.Label(top_bar, text="Modèle :").pack(side="left", padx=(0, 4))
        self.model_combobox = ttk.Combobox(top_bar, state="readonly", width=40)
        self.model_combobox.pack(side="left", padx=(0, 6))
        self.model_combobox.bind("<<ComboboxSelected>>", self._on_model_selected)

        self.browse_button = ttk.Button(top_bar, text="Parcourir...", command=self._on_browse_clicked)
        self.browse_button.pack(side="left")

        self.loading_label = ttk.Label(top_bar, text="", foreground="#b8860b")
        self.loading_label.pack(side="left", padx=10)

        self.stats_label = ttk.Label(top_bar, text="", foreground="#555555")
        self.stats_label.pack(side="right", padx=6)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(side="top", fill="both", expand=True)

        sidebar = ttk.Frame(body, padding=6, width=220)
        body.add(sidebar, weight=0)

        self.new_conv_button = ttk.Button(sidebar, text="Nouvelle conversation", command=self.new_conversation)
        self.new_conv_button.pack(side="top", fill="x", pady=(0, 6))

        self.sessions_tree = ttk.Treeview(sidebar, show="tree", selectmode="browse")
        self.sessions_tree.pack(side="top", fill="both", expand=True)
        self.sessions_tree.bind("<<TreeviewSelect>>", self._on_session_selected)
        self.sessions_tree.bind("<Button-3>", self._on_session_right_click)

        main_panel = ttk.Frame(body, padding=6)
        body.add(main_panel, weight=1)

        transcript_frame = ttk.Frame(main_panel)
        transcript_frame.pack(side="top", fill="both", expand=True)

        self.transcript = tk.Text(transcript_frame, wrap="word", state="disabled", padx=8, pady=8)
        self.transcript.pack(side="left", fill="both", expand=True)
        transcript_scroll = ttk.Scrollbar(transcript_frame, orient="vertical", command=self.transcript.yview)
        transcript_scroll.pack(side="right", fill="y")
        self.transcript.configure(yscrollcommand=transcript_scroll.set)

        self.transcript.tag_configure("user", foreground="#1a4fb4", spacing1=8, spacing3=2)
        self.transcript.tag_configure("assistant", foreground="#1a1a1a", spacing1=2, spacing3=8)
        self.transcript.tag_configure("reasoning", foreground="#888888", font=("TkDefaultFont", 9, "italic"), elide=True)
        self.transcript.tag_configure("reasoning_toggle", foreground="#4a7fd6", underline=True)
        self.transcript.tag_configure(
            "code",
            font=("Consolas", 10),
            background="#eeeeee",
            lmargin1=16,
            lmargin2=16,
            rmargin=16,
            spacing1=4,
            spacing3=4,
        )
        self.transcript.tag_configure("md_bold", font=("TkDefaultFont", 10, "bold"))
        self.transcript.tag_configure("md_italic", font=("TkDefaultFont", 10, "italic"))
        self.transcript.tag_configure("md_inline_code", font=("Consolas", 9), background="#e4e4e4")
        self.transcript.tag_configure("md_h1", font=("TkDefaultFont", 15, "bold"), spacing1=6, spacing3=2)
        self.transcript.tag_configure("md_h2", font=("TkDefaultFont", 13, "bold"), spacing1=5, spacing3=2)
        self.transcript.tag_configure("md_h3", font=("TkDefaultFont", 11, "bold"), spacing1=4, spacing3=2)
        self.transcript.tag_configure("md_bullet", lmargin1=16, lmargin2=28)
        # Priorité d'affichage Tkinter = ordre de première configuration des tags (pas
        # l'ordre du tuple passé à insert()). "code" est configuré ci-dessus une fois
        # pour toutes ; chaque tag fg_{couleur} n'est configuré que la première fois
        # qu'il apparaît (toujours après "code"), donc la couleur pygments l'emporte
        # naturellement sans avoir besoin de tag_raise().
        self.transcript.tag_bind("reasoning_toggle", "<Button-1>", self._on_reasoning_toggle_clicked)
        self.transcript.tag_bind("reasoning_toggle", "<Enter>", lambda e: self.transcript.configure(cursor="hand2"))
        self.transcript.tag_bind("reasoning_toggle", "<Leave>", lambda e: self.transcript.configure(cursor=""))
        self.transcript.bind("<Button-3>", self._on_transcript_right_click)

        input_area = ttk.Frame(main_panel)
        input_area.pack(side="bottom", fill="x", pady=(6, 0))

        self.input_text = tk.Text(input_area, height=3, wrap="word")
        self.input_text.pack(side="left", fill="both", expand=True)
        self.input_text.bind("<Return>", self._on_input_return)
        self.input_text.bind("<Shift-Return>", lambda e: None)

        self.send_button = ttk.Button(input_area, text="Envoyer", command=self.send_message)
        self.send_button.pack(side="right", padx=(6, 0), fill="y")

        self._reasoning_block_counter = 0
        self._code_block_counter = 0
        self._current_block_id: int | None = None
        self._message_texts: dict[str, str] = {}
        self._fg_tags: set[str] = set()

    # ------------------------------------------------------------------ état UI

    def _set_ui_state(self, state: str) -> None:
        self.state = state
        busy = state in ("loading", "generating")
        widget_state = "disabled" if busy else "normal"
        self.model_combobox.configure(state="disabled" if busy else "readonly")
        self.browse_button.configure(state=widget_state)
        self.new_conv_button.configure(state=widget_state)
        self.input_text.configure(state=widget_state)
        self.loading_label.configure(text="Chargement du modèle..." if state == "loading" else "")
        if state == "generating":
            self.send_button.configure(text="Arrêter", command=self.stop_generation, state="normal")
        else:
            self.send_button.configure(text="Envoyer", command=self.send_message, state=widget_state)

    # ------------------------------------------------------------------ chargement du modèle

    def start_model_load(self, model_path: str) -> None:
        self._set_ui_state("loading")
        threading.Thread(target=self._load_model_worker, args=(model_path,), daemon=True).start()

    def _load_model_worker(self, model_path: str) -> None:
        try:
            cfg = dataclasses.replace(self.base_config, model_path=Path(model_path))
            client = LLMClient(cfg)
            self.event_queue.put(("model_loaded", (client, model_path)))
        except Exception as e:
            self.event_queue.put(("model_error", e))

    def _on_model_loaded(self, client: LLMClient, model_path: str) -> None:
        old_client = self.client
        self.client = client
        self.current_model_path = model_path
        self.context.llm_client = client
        self.known_models["last_used"] = model_path
        save_known_models(self.known_models)
        self._select_model_in_combobox(model_path)
        self._set_ui_state("idle")

        if old_client is not None:
            old_client.close()
            del old_client
            gc.collect()

    def _on_model_error(self, error: Exception) -> None:
        self._set_ui_state("idle" if self.client is not None else "loading")
        messagebox.showerror("Erreur de chargement du modèle", str(error))

    # ------------------------------------------------------------------ combo modèles

    def _refresh_model_combobox(self) -> None:
        labels = [m["label"] for m in self.known_models["models"]]
        self.model_combobox.configure(values=labels)

    def _select_model_in_combobox(self, model_path: str) -> None:
        for m in self.known_models["models"]:
            if m["path"] == model_path:
                self.model_combobox.set(m["label"])
                return

    def _resolve_label_to_path(self, label: str) -> str | None:
        for m in self.known_models["models"]:
            if m["label"] == label:
                return m["path"]
        return None

    def _on_model_selected(self, event=None) -> None:
        label = self.model_combobox.get()
        path = self._resolve_label_to_path(label)
        if not path:
            return
        if path == self.current_model_path:
            return
        self.start_model_load(path)

    def _on_browse_clicked(self) -> None:
        path = filedialog.askopenfilename(title="Choisir un modèle GGUF", filetypes=[("Modèles GGUF", "*.gguf")])
        if not path:
            return
        if not any(m["path"] == path for m in self.known_models["models"]):
            self.known_models["models"].append({"path": path, "label": Path(path).stem})
            save_known_models(self.known_models)
            self._refresh_model_combobox()
        self._select_model_in_combobox(path)
        self.start_model_load(path)

    # ------------------------------------------------------------------ conversations (sidebar)

    def _refresh_sidebar(self) -> None:
        selected = self.context.session_id
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        for session_id in reversed(self.context.list_sessions()):
            label = format_session_label(session_id, self.session_titles)
            self.sessions_tree.insert("", "end", iid=session_id, text=label)
        if self.sessions_tree.exists(selected):
            self.sessions_tree.selection_set(selected)

    def new_conversation(self) -> None:
        if self.state != "idle":
            return
        self.context.reset()
        self._clear_transcript()
        self.sessions_tree.selection_remove(self.sessions_tree.selection())

    def _on_session_selected(self, event=None) -> None:
        if self.state != "idle":
            return
        selection = self.sessions_tree.selection()
        if not selection:
            return
        session_id = selection[0]
        if session_id == self.context.session_id:
            return
        if self.context.resume(session_id):
            self._render_full_transcript()

    def _on_session_right_click(self, event) -> None:
        item = self.sessions_tree.identify_row(event.y)
        if not item:
            return
        self.sessions_tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Renommer", command=lambda: self._rename_session(item))
        menu.add_command(label="Supprimer", command=lambda: self._delete_session(item))
        menu.tk_popup(event.x_root, event.y_root)

    def _rename_session(self, session_id: str) -> None:
        current = self.session_titles.get(session_id, "")
        new_title = simpledialog.askstring(
            "Renommer la conversation", "Nouveau nom :", initialvalue=current, parent=self.root
        )
        if new_title is None:
            return
        new_title = new_title.strip()
        if new_title:
            self.session_titles[session_id] = new_title
        else:
            self.session_titles.pop(session_id, None)
        save_session_titles(self.session_titles)
        self._refresh_sidebar()

    def _delete_session(self, session_id: str) -> None:
        if not messagebox.askyesno("Supprimer", "Supprimer définitivement cette conversation ?"):
            return
        was_active = session_id == self.context.session_id
        self.context.delete_session(session_id)
        if self.session_titles.pop(session_id, None) is not None:
            save_session_titles(self.session_titles)
        self._refresh_sidebar()
        if was_active:
            self._clear_transcript()

    # ------------------------------------------------------------------ transcript

    def _clear_transcript(self) -> None:
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")

    def _render_full_transcript(self) -> None:
        self._clear_transcript()
        for message in self.context.history:
            if message["role"] == "user":
                self._append_transcript("Vous : " + message["content"] + "\n", "user")
            elif message["role"] == "assistant":
                self._reasoning_block_counter += 1
                block_id = self._reasoning_block_counter
                self._message_texts[f"answer_msg_{block_id}"] = message["content"]
                self._append_transcript("Agent : ", "assistant")
                self._render_message_content(message["content"], block_id)
                self._append_transcript("\n", "assistant")

    def _render_message_content(self, text: str, block_id: int) -> None:
        """Insère le texte d'une réponse déjà complète : rendu Markdown léger pour la
        prose, coloration syntaxique pour les blocs de code (```lang ... ```), tout en
        gardant la copie (clic droit) possible sur le message entier ou un bloc de code."""
        base_tags = ("assistant", f"answer_msg_{block_id}")
        pos = 0
        for match in CODE_BLOCK_RE.finditer(text):
            before = text[pos : match.start()]
            if before:
                self._render_prose(before, base_tags)
            language = match.group(1).strip() or None
            code = match.group(2).rstrip("\n")
            self._code_block_counter += 1
            code_id = self._code_block_counter
            self._message_texts[f"code_{code_id}"] = code  # texte brut complet, pour la copie

            code_tags_base = base_tags + ("code", f"code_{code_id}")
            for fragment, color in highlight_code(code, language):
                tags = code_tags_base
                if color is not None:
                    fg_tag = f"fg_{color.lstrip('#')}"
                    if fg_tag not in self._fg_tags:
                        self.transcript.tag_configure(fg_tag, foreground=color)
                        self._fg_tags.add(fg_tag)
                    tags = tags + (fg_tag,)
                self._append_transcript(fragment, tags)
            self._append_transcript("\n", code_tags_base)
            pos = match.end()
        remaining = text[pos:]
        if remaining:
            self._render_prose(remaining, base_tags)

    def _render_prose(self, text: str, base_tags: tuple) -> None:
        def emit(segment: str, extra_tags: tuple) -> None:
            if segment:
                self._append_transcript(segment, base_tags + extra_tags)

        render_markdown(text, emit)

    def _reformat_message_with_code_blocks(self, block_id: int, full_text: str) -> None:
        """Reprend en fin de streaming le rendu brut d'une réponse pour y détecter et
        styler les blocs de code (non fait pendant le streaming, trop coûteux token par token)."""
        tag = f"answer_msg_{block_id}"
        ranges = self.transcript.tag_ranges(tag)
        if not ranges:
            return
        start, end = str(ranges[0]), str(ranges[-1])
        self.transcript.configure(state="normal")
        self.transcript.delete(start, end)
        self.transcript.configure(state="disabled")
        self._render_message_content(full_text, block_id)

    def _append_transcript(self, text: str, tags) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", text, tags)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _on_transcript_right_click(self, event) -> None:
        index = self.transcript.index(f"@{event.x},{event.y}")
        tags = self.transcript.tag_names(index)

        code_tag = next((t for t in tags if t.startswith("code_")), None)
        if code_tag:
            text = self._message_texts.get(code_tag, "")
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Copier le code", command=lambda: self._copy_to_clipboard(text))
            menu.tk_popup(event.x_root, event.y_root)
            return

        message_tag = next((t for t in tags if t.startswith("answer_msg_")), None)
        if not message_tag:
            return
        text = self._message_texts.get(message_tag, "")
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Copier le message", command=lambda: self._copy_to_clipboard(text))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # ------------------------------------------------------------------ envoi de message

    def _on_input_return(self, event) -> str:
        self.send_message()
        return "break"

    def send_message(self) -> None:
        if self.state != "idle":
            return
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            return
        self.input_text.delete("1.0", "end")

        self._append_transcript("Vous : " + text + "\n", "user")
        self._append_transcript("Agent : ", "assistant")

        self._reasoning_block_counter += 1
        block_id = self._reasoning_block_counter
        self._current_block_id = block_id
        self._message_texts[f"answer_msg_{block_id}"] = ""

        self._stop_event.clear()
        self._gen_start_time = time.monotonic()
        self._gen_token_count = 0

        self._set_ui_state("generating")
        target_context = self.context
        threading.Thread(target=self._send_worker, args=(target_context, text, block_id), daemon=True).start()

    def stop_generation(self) -> None:
        if self.state != "generating":
            return
        self._stop_event.set()

    def _send_worker(self, context: ContextManager, text: str, block_id: int) -> None:
        context.add_message("user", text)
        self.event_queue.put(("sidebar_refresh", None))

        def on_reasoning(t: str) -> None:
            self.event_queue.put(("reasoning_chunk", (context, block_id, t)))

        def on_answer(t: str) -> None:
            self.event_queue.put(("answer_chunk", (context, block_id, t)))

        splitter = ThinkStreamSplitter(on_reasoning, on_answer)
        try:
            for chunk in self.client.stream(list(context.history)):
                if self._stop_event.is_set():
                    break
                content = chunk["choices"][0]["delta"].get("content")
                if content:
                    splitter.feed(content)
            splitter.flush()
        except Exception as e:
            self.event_queue.put(("stream_error", (context, e)))
            return

        self.event_queue.put(("stream_done", context))

    def _on_answer_chunk(self, context: ContextManager, block_id: int, text: str) -> None:
        self._pending_answer += text
        self._message_texts[f"answer_msg_{block_id}"] += text
        self._count_generated_token()
        if context is not self.context:
            return
        self._append_transcript(text, ("assistant", f"answer_msg_{block_id}"))

    def _count_generated_token(self) -> None:
        # Approximation : llama-cpp-python envoie généralement un token par chunk en streaming.
        self._gen_token_count += 1
        elapsed = time.monotonic() - self._gen_start_time
        if elapsed > 0:
            self._current_tps_text = f"{self._gen_token_count / elapsed:.1f} tok/s"
            self._refresh_stats_label()

    def _on_reasoning_chunk(self, context: ContextManager, block_id: int, text: str) -> None:
        self._count_generated_token()
        if context is not self.context:
            return
        # Les morceaux de réflexion et de réponse arrivent strictement dans l'ordre
        # (réflexion entière avant la réponse finale) : insérer à "end" suffit, pas
        # besoin de suivre un index dédié qui deviendrait invalide après coup.
        if self._reasoning_toggle_inserted != block_id:
            self._reasoning_toggle_inserted = block_id
            self._append_transcript("[réflexion ▸]\n", ("reasoning_toggle", f"toggle_{block_id}"))
            # Initialise explicitement "elide" sur le tag du bloc : sans ça, tag_cget()
            # renvoie "" (non défini) tant qu'on n'a jamais basculé le tag, et le premier
            # clic sur le repli/dépli se contente de re-cacher ce qui était déjà masqué
            # par défaut via le tag "reasoning" (double-clic nécessaire pour le déplier).
            self.transcript.configure(state="normal")
            self.transcript.tag_configure(f"reasoning_{block_id}", elide=True)
            self.transcript.configure(state="disabled")
        self._append_transcript(text, ("reasoning", f"reasoning_{block_id}"))

    def _on_reasoning_toggle_clicked(self, event) -> None:
        index = self.transcript.index(f"@{event.x},{event.y}")
        tags = self.transcript.tag_names(index)
        for tag in tags:
            if tag.startswith("toggle_"):
                block_id = tag.split("_", 1)[1]
                reasoning_tag = f"reasoning_{block_id}"
                ranges = self.transcript.tag_ranges(reasoning_tag)
                if not ranges:
                    continue
                currently_elided = self.transcript.tag_cget(reasoning_tag, "elide")
                is_hidden = currently_elided in ("1", True, "true")
                self.transcript.configure(state="normal")
                self.transcript.tag_configure(reasoning_tag, elide=not is_hidden)
                self.transcript.configure(state="disabled")
                break

    def _on_stream_done(self, context: ContextManager) -> None:
        full_answer = self._pending_answer
        self._pending_answer = ""
        self._reasoning_toggle_inserted = None
        if context is self.context and self._current_block_id is not None:
            self._reformat_message_with_code_blocks(self._current_block_id, full_answer)
        threading.Thread(target=self._finalize_answer_worker, args=(context, full_answer), daemon=True).start()

    def _finalize_answer_worker(self, context: ContextManager, full_answer: str) -> None:
        # Une génération arrêtée avant l'apparition de la réponse finale (encore en pleine
        # réflexion) ne produit aucun texte de réponse : ne pas polluer l'historique avec
        # un message assistant vide dans ce cas.
        if full_answer.strip():
            context.add_message("assistant", full_answer)
        self.event_queue.put(("assistant_saved", context))

    def _on_assistant_saved(self, context: ContextManager) -> None:
        self.event_queue.put(("sidebar_refresh", None))
        if context is self.context:
            self._append_transcript("\n", "assistant")
            self._set_ui_state("idle")
        elif self.state == "generating":
            self._set_ui_state("idle")

    def _on_stream_error(self, context: ContextManager, error: Exception) -> None:
        self._pending_answer = ""
        self._reasoning_toggle_inserted = None
        if context is self.context:
            self._append_transcript(f"\n[Erreur : {error}]\n", "assistant")
        self._set_ui_state("idle")

    # ------------------------------------------------------------------ ressources (tok/s, RAM, VRAM)

    def _start_resource_polling(self) -> None:
        self.root.after(2000, self._poll_resource_stats)

    def _poll_resource_stats(self) -> None:
        threading.Thread(target=self._resource_stats_worker, daemon=True).start()
        self.root.after(2000, self._poll_resource_stats)

    def _resource_stats_worker(self) -> None:
        try:
            rss_mb = _PROCESS.memory_info().rss / (1024 * 1024)
            ram_text = f"RAM {rss_mb:.0f} Mo"
        except Exception:
            ram_text = "RAM N/A"
        vram_text = self._query_vram()
        self.event_queue.put(("resource_stats", f"{ram_text}   {vram_text}"))

    def _query_vram(self) -> str:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            used, total = out.stdout.strip().split(",")
            return f"VRAM {used.strip()}/{total.strip()} Mo"
        except Exception:
            return "VRAM N/A"

    def _refresh_stats_label(self) -> None:
        self.stats_label.configure(text=f"{self._current_tps_text}   {self._current_mem_text}")

    # ------------------------------------------------------------------ boucle d'événements

    def _poll_queue(self) -> None:
        try:
            while True:
                tag, payload = self.event_queue.get_nowait()
                if tag == "model_loaded":
                    client, model_path = payload
                    self._on_model_loaded(client, model_path)
                elif tag == "model_error":
                    self._on_model_error(payload)
                elif tag == "answer_chunk":
                    context, block_id, text = payload
                    self._on_answer_chunk(context, block_id, text)
                elif tag == "reasoning_chunk":
                    context, block_id, text = payload
                    self._on_reasoning_chunk(context, block_id, text)
                elif tag == "stream_done":
                    self._on_stream_done(payload)
                elif tag == "stream_error":
                    context, error = payload
                    self._on_stream_error(context, error)
                elif tag == "assistant_saved":
                    self._on_assistant_saved(payload)
                elif tag == "sidebar_refresh":
                    self._refresh_sidebar()
                elif tag == "resource_stats":
                    self._current_mem_text = payload
                    self._refresh_stats_label()
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)


def run_app() -> None:
    root = tk.Tk()
    try:
        ChatApp(root)
    except RuntimeError as e:
        messagebox.showerror("Erreur de configuration", str(e))
        return
    root.mainloop()
