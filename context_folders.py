"""Listage des fichiers des dossiers/fichiers de contexte, pour l'index @mention."""

from pathlib import Path

MAX_ENTRIES = 5000


def list_files_recursive(roots: list[Path], max_entries: int = MAX_ENTRIES) -> list[tuple[str, Path]]:
    """Renvoie une liste de (label, chemin_absolu) pour les fichiers sous `roots`.

    `roots` peut contenir des dossiers (listés récursivement, label "nom_dossier/chemin/relatif")
    et des fichiers ajoutés individuellement (label = leur seul nom de fichier). Résultat trié,
    tronqué à max_entries pour ne pas geler l'UI sur un dossier énorme.

    Le respect de .gitignore est hors scope v1 : tous les fichiers sont listés.
    """
    entries: list[tuple[str, Path]] = []
    for root in roots:
        if root.is_file():
            entries.append((root.name, root))
            if len(entries) >= max_entries:
                return sorted(entries, key=lambda e: e[0])
        elif root.is_dir():
            for path in root.rglob("*"):
                if path.is_file():
                    label = f"{root.name}/{path.relative_to(root).as_posix()}"
                    entries.append((label, path))
                    if len(entries) >= max_entries:
                        return sorted(entries, key=lambda e: e[0])
    return sorted(entries, key=lambda e: e[0])
