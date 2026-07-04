"""Point d'entrée de l'agent de code. Boucle principale de chat."""

from rich.console import Console
from rich.status import Status

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from config import load_config
from context_manager import ContextManager
from llm_client import LLMClient

EXIT_COMMANDS = {"/exit", "/quit"}

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


class ThinkStreamSplitter:
    """Sépare à la volée un flux de texte en blocs 'réflexion' (<think>...</think>) et 'réponse finale'.

    Tolère que les balises soient coupées entre deux morceaux de flux, et fonctionne
    normalement si le modèle ne produit aucune balise <think>.
    """

    def __init__(self, on_reasoning, on_answer):
        self._pending = ""
        # Le template de chat du modèle insère "<think>\n" avant que la génération
        # ne commence : le flux ne contient donc jamais la balise d'ouverture, seulement "</think>".
        self._in_think = True
        self._on_reasoning = on_reasoning
        self._on_answer = on_answer

    def feed(self, piece: str) -> None:
        buffer = self._pending + piece
        while True:
            tag, tag_len = (THINK_CLOSE, len(THINK_CLOSE)) if self._in_think else (THINK_OPEN, len(THINK_OPEN))
            idx = buffer.find(tag)
            if idx != -1:
                emit = self._on_reasoning if self._in_think else self._on_answer
                emit(buffer[:idx])
                buffer = buffer[idx + tag_len :]
                self._in_think = not self._in_think
                continue

            safe_len = max(0, len(buffer) - (tag_len - 1))
            if safe_len:
                emit = self._on_reasoning if self._in_think else self._on_answer
                emit(buffer[:safe_len])
                buffer = buffer[safe_len:]
            break
        self._pending = buffer

    def flush(self) -> None:
        if self._pending:
            emit = self._on_reasoning if self._in_think else self._on_answer
            emit(self._pending)
            self._pending = ""


def print_agent_response(console: Console, client: LLMClient, context: ContextManager) -> None:
    state = {"reasoning_started": False, "answer_started": False, "full_answer": ""}

    def on_reasoning(text: str) -> None:
        if not text:
            return
        if not state["reasoning_started"]:
            console.print("[dim]réflexion...[/dim]")
            state["reasoning_started"] = True
        console.print(text, end="", style="dim italic", markup=False)

    def on_answer(text: str) -> None:
        if not text:
            return
        if not state["answer_started"]:
            if state["reasoning_started"]:
                console.print()
            console.print("\n[bold magenta]Agent[/bold magenta] : ", end="")
            state["answer_started"] = True
        console.print(text, end="", markup=False)
        state["full_answer"] += text

    splitter = ThinkStreamSplitter(on_reasoning, on_answer)
    for chunk in client.stream(context.history):
        delta = chunk["choices"][0]["delta"]
        content = delta.get("content")
        if content:
            splitter.feed(content)
    splitter.flush()

    console.print()
    context.add_message("assistant", state["full_answer"])


def handle_command(text: str, console: Console, context: ContextManager) -> bool:
    """Traite une commande. Retourne True si `text` en était une (le LLM n'est pas appelé)."""
    if text == "/reset":
        context.reset()
        console.print("[yellow]Contexte réinitialisé.[/yellow]")
        return True

    if text == "/resume":
        sessions = context.list_sessions()
        if not sessions:
            console.print("[yellow]Aucune session enregistrée.[/yellow]")
        else:
            console.print("Sessions disponibles : " + ", ".join(sessions))
        return True

    if text.startswith("/resume "):
        session_id = text.split(" ", 1)[1].strip()
        if context.resume(session_id):
            console.print(f"[green]Session {session_id} restaurée ({len(context.history)} messages).[/green]")
        else:
            console.print(f"[red]Session {session_id} introuvable.[/red]")
        return True

    return False


def main() -> None:
    console = Console()

    try:
        config = load_config()
    except RuntimeError as e:
        console.print(f"[red]Erreur de configuration :[/red] {e}")
        return

    console.print("[bold green]cjp[/bold green] — chat de base (Phase 1)")
    with Status("Chargement du modèle...", console=console, spinner="dots"):
        client = LLMClient(config)
    context = ContextManager(config.sessions_dir, config.max_context_chars, llm_client=client)

    console.print(f"Modèle : [bold]{config.model_path.name}[/bold] (CPU, contexte {config.n_ctx})")
    console.print("Commandes : [bold]/reset[/bold], [bold]/resume [id][/bold], [bold]/exit[/bold]\n")

    session: PromptSession = PromptSession(history=InMemoryHistory())

    while True:
        try:
            text = session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nÀ bientôt !")
            break

        if not text:
            continue

        if text in EXIT_COMMANDS:
            console.print("À bientôt !")
            break

        if handle_command(text, console, context):
            continue

        context.add_message("user", text)
        try:
            print_agent_response(console, client, context)
        except Exception as e:
            console.print(f"[red]Erreur lors de l'appel au modèle : {e}[/red]")


if __name__ == "__main__":
    main()
