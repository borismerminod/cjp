"""Gestion du contexte de conversation : historique, dossiers de contexte, persistance et résumé."""

import json
import time
from pathlib import Path

SUMMARY_PROMPT = (
    "Résume cette conversation en quelques phrases, en conservant les décisions "
    "et informations importantes pour la suite de l'échange."
)


class ContextManager:
    def __init__(self, sessions_dir: Path, max_context_chars: int, llm_client=None):
        self.sessions_dir = sessions_dir
        self.max_context_chars = max_context_chars
        self.llm_client = llm_client
        self.history: list[dict] = []
        self.context_folders: list[str] = []
        self.context_files: list[str] = []
        self.session_id = self._new_session_id()

    def _new_session_id(self) -> str:
        return time.strftime("%Y%m%d-%H%M%S")

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self._enforce_context_limit()
        self.save()

    def add_context_folder(self, path: str) -> None:
        if path not in self.context_folders:
            self.context_folders.append(path)
            self.save()

    def remove_context_folder(self, path: str) -> None:
        if path in self.context_folders:
            self.context_folders.remove(path)
            self.save()

    def add_context_file(self, path: str) -> None:
        if path not in self.context_files:
            self.context_files.append(path)
            self.save()

    def remove_context_file(self, path: str) -> None:
        if path in self.context_files:
            self.context_files.remove(path)
            self.save()

    def context_folders_as_paths(self) -> list[Path]:
        return [Path(p) for p in self.context_folders] + [Path(p) for p in self.context_files]

    def _enforce_context_limit(self) -> None:
        total_chars = sum(len(m["content"]) for m in self.history)
        if total_chars <= self.max_context_chars or len(self.history) <= 2:
            return

        to_summarize, kept = self.history[:-2], self.history[-2:]
        summary = self._summarize(to_summarize)
        self.history = [{"role": "system", "content": f"Résumé de la conversation précédente : {summary}"}, *kept]

    def _summarize(self, messages: list[dict]) -> str:
        if not self.llm_client:
            return " ".join(m["content"] for m in messages)[:500]
        prompt = [{"role": "system", "content": SUMMARY_PROMPT}, *messages]
        return self.llm_client.complete(prompt)

    def reset(self) -> None:
        self.history.clear()
        self.context_folders = []
        self.context_files = []
        self.session_id = self._new_session_id()

    def save(self) -> None:
        path = self.sessions_dir / f"{self.session_id}.json"
        data = {
            "history": self.history,
            "context_folders": self.context_folders,
            "context_files": self.context_files,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def resume(self, session_id: str) -> bool:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # Ancien format de session (avant l'ajout des dossiers/fichiers de contexte) : une
            # simple liste de messages, sans contexte associé.
            data = {"history": data, "context_folders": [], "context_files": []}
        self.history = data.get("history", [])
        self.context_folders = data.get("context_folders", [])
        self.context_files = data.get("context_files", [])
        self.session_id = session_id
        return True

    def list_sessions(self) -> list[str]:
        return sorted(p.stem for p in self.sessions_dir.glob("*.json"))

    def delete_session(self, session_id: str) -> bool:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return False
        path.unlink()
        if session_id == self.session_id:
            self.reset()
        return True
