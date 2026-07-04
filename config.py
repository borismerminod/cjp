"""Chargement de la configuration de l'application depuis le fichier .env."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_N_CTX = 4096
DEFAULT_N_GPU_LAYERS = -1
DEFAULT_MAX_CONTEXT_CHARS = 8000
DEFAULT_MAX_TOKENS = 2048


def get_app_dir() -> Path:
    """Dossier de référence pour les données de l'application (.env, known_models.json,
    sessions/, ...). Pointe à côté de l'exécutable une fois empaqueté (PyInstaller), ou à
    côté des sources en développement — jamais le répertoire de travail courant, qui peut
    différer selon comment l'app est lancée."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


@dataclass
class Config:
    model_path: Path
    n_ctx: int
    n_gpu_layers: int
    max_tokens: int
    project_root: Path
    sessions_dir: Path
    max_context_chars: int


def load_config() -> Config:
    project_root = get_app_dir()
    load_dotenv(project_root / ".env")

    sessions_dir = project_root / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    model_path_str = os.getenv("MODEL_PATH")
    if not model_path_str:
        raise RuntimeError("MODEL_PATH n'est pas défini dans .env (voir .env.example).")
    model_path = Path(model_path_str)
    if not model_path.is_file():
        raise RuntimeError(f"MODEL_PATH pointe vers un fichier introuvable : {model_path}")

    return Config(
        model_path=model_path,
        n_ctx=int(os.getenv("N_CTX", DEFAULT_N_CTX)),
        n_gpu_layers=int(os.getenv("N_GPU_LAYERS", DEFAULT_N_GPU_LAYERS)),
        max_tokens=int(os.getenv("MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        project_root=project_root,
        sessions_dir=sessions_dir,
        max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", DEFAULT_MAX_CONTEXT_CHARS)),
    )
