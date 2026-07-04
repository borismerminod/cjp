"""Outils de lecture/écriture de fichiers, restreints aux dossiers de contexte ajoutés."""

import difflib
from pathlib import Path
from typing import Callable

MAX_LIST_ENTRIES = 500


class SandboxError(Exception):
    """Chemin en dehors des dossiers de contexte autorisés."""


def resolve_in_sandbox(path_str: str, allowed_roots: list[Path]) -> Path:
    """Résout `path_str` (relatif à l'une des racines, ou absolu) et vérifie qu'il tombe bien
    sous l'une des racines autorisées (dossier) ou correspond exactement à l'une d'elles
    (fichier ajouté individuellement). Lève SandboxError sinon.

    Tolère deux conventions pour un chemin relatif à un dossier : "relatif/au/dossier" et
    "nom_dossier/relatif/au/dossier" (ce dernier correspond au label affiché dans le popup
    @mention et l'index de fichiers, que le modèle a tendance à recopier tel quel). Pour un
    fichier ajouté individuellement, accepte son seul nom de fichier (ex: "notes.txt").

    Point de sécurité unique : ne jamais faire confiance au chemin fourni par le modèle sans
    passer par cette fonction.
    """
    candidate = Path(path_str)

    file_roots = [r for r in allowed_roots if r.is_file()]
    dir_roots = [r for r in allowed_roots if not r.is_file()]

    if candidate.is_absolute():
        target = candidate.resolve()
        for root in file_roots:
            if target == root.resolve():
                return target
        for root in dir_roots:
            if target.is_relative_to(root.resolve()):
                return target
        raise SandboxError(f"Chemin en dehors des dossiers/fichiers de contexte autorisés : {path_str}")

    for root in file_roots:
        resolved_root = root.resolve()
        if candidate.name == resolved_root.name:
            return resolved_root

    for root in dir_roots:
        resolved_root = root.resolve()
        parts = candidate.parts
        candidates = []
        if parts and parts[0] == resolved_root.name:
            # Interprétation "nom_dossier/relatif" (label @mention) : prioritaire, car c'est
            # la convention utilisée partout ailleurs (index de fichiers, list_directory).
            candidates.append(resolved_root / Path(*parts[1:]) if len(parts) > 1 else resolved_root)
        candidates.append(resolved_root / candidate)
        for c in candidates:
            target = c.resolve()
            if target.is_relative_to(resolved_root):
                return target
    raise SandboxError(f"Chemin en dehors des dossiers/fichiers de contexte autorisés : {path_str}")


READ_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Lit le contenu d'un fichier du projet.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin du fichier (relatif à un dossier de contexte)"}},
            "required": ["path"],
        },
    },
}

LIST_DIRECTORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": "Liste les fichiers et sous-dossiers d'un dossier du projet.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin du dossier (relatif à un dossier de contexte, vide pour la racine)"}},
            "required": [],
        },
    },
}

WRITE_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Crée un nouveau fichier ou réécrit entièrement un fichier existant. Nécessite une confirmation de l'utilisateur avant application.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin du fichier (relatif à un dossier de contexte)"},
                "content": {"type": "string", "description": "Contenu complet du fichier"},
            },
            "required": ["path", "content"],
        },
    },
}

EDIT_FILE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Remplace un extrait précis de texte dans un fichier existant. old_text doit "
            "apparaître exactement une fois dans le fichier. Nécessite une confirmation de "
            "l'utilisateur avant application."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin du fichier (relatif à un dossier de contexte)"},
                "old_text": {"type": "string", "description": "Extrait exact à remplacer (doit apparaître une seule fois)"},
                "new_text": {"type": "string", "description": "Texte de remplacement"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
}


def read_file(path: str, allowed_roots: list[Path]) -> str:
    """Ne lève jamais d'exception : message d'erreur textuel en cas de problème."""
    try:
        target = resolve_in_sandbox(path, allowed_roots)
        if not target.is_file():
            return f"Erreur : fichier introuvable : {path}"
        return target.read_text(encoding="utf-8", errors="replace")
    except SandboxError as e:
        return f"Erreur : {e}"
    except Exception as e:
        return f"Erreur lors de la lecture du fichier : {e}"


def list_directory(path: str, allowed_roots: list[Path]) -> str:
    """Liste (texte) le contenu d'un dossier, nombre d'entrées limité."""
    try:
        if path:
            target = resolve_in_sandbox(path, allowed_roots)
        else:
            dir_roots = [r for r in allowed_roots if not r.is_file()]
            if not dir_roots:
                return "Erreur : aucun dossier de contexte disponible (seulement des fichiers individuels)."
            target = dir_roots[0].resolve()
        if not target.is_dir():
            return f"Erreur : dossier introuvable : {path}"
        entries = sorted(target.rglob("*"))[:MAX_LIST_ENTRIES]
        if not entries:
            return "(dossier vide)"
        lines = [f"{'[dossier] ' if e.is_dir() else ''}{e.relative_to(target)}" for e in entries]
        suffix = "\n... (liste tronquée)" if len(entries) == MAX_LIST_ENTRIES else ""
        return "\n".join(lines) + suffix
    except SandboxError as e:
        return f"Erreur : {e}"
    except Exception as e:
        return f"Erreur lors du listage du dossier : {e}"


def _build_diff_text(path_label: str, old_content: str, new_content: str) -> str:
    # lineterm par défaut ("\n") : les lignes de contenu ont déjà leur propre fin de ligne
    # (splitlines(keepends=True)), mais les en-têtes ---/+++/@@ générés par difflib n'en ont
    # pas et doivent être terminés explicitement, sous peine de tout coller sur une ligne.
    diff_lines = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=path_label,
        tofile=path_label,
    )
    return "".join(diff_lines) or "(aucune modification textuelle)"


def preview_write_file(path: str, content: str, allowed_roots: list[Path]) -> tuple[str, Callable[[], None]]:
    """Calcule le diff sans rien écrire. Renvoie (texte_diff, fonction_d'application)."""
    target = resolve_in_sandbox(path, allowed_roots)
    old_content = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    diff_text = _build_diff_text(str(path), old_content, content)

    def apply_fn() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return diff_text, apply_fn


def preview_edit_file(
    path: str, old_text: str, new_text: str, allowed_roots: list[Path]
) -> tuple[str, Callable[[], None]]:
    """Vérifie que old_text apparaît exactement une fois, calcule le diff complet du fichier,
    sans rien écrire. Renvoie (texte_diff, fonction_d'application)."""
    target = resolve_in_sandbox(path, allowed_roots)
    if not target.is_file():
        raise SandboxError(f"Fichier introuvable : {path}")
    old_content = target.read_text(encoding="utf-8", errors="replace")

    occurrences = old_content.count(old_text)
    if occurrences != 1:
        raise SandboxError(
            f"old_text apparaît {occurrences} fois dans {path} (doit être exactement 1) — "
            "précise un extrait plus long/plus spécifique, en respectant l'indentation exacte."
        )

    new_content = old_content.replace(old_text, new_text, 1)
    diff_text = _build_diff_text(str(path), old_content, new_content)

    def apply_fn() -> None:
        target.write_text(new_content, encoding="utf-8")

    return diff_text, apply_fn
