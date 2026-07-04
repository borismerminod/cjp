"""Client d'appel au LLM, via un modèle GGUF chargé directement dans le process (llama-cpp-python)."""

import os
import re
import sys
from pathlib import Path
from typing import Iterable


def _register_nvidia_dll_dirs() -> None:
    """llama-cpp-python charge ses DLL avec un mode qui ignore os.add_dll_directory() sous Windows ;
    seule la variable PATH est prise en compte. Il faut donc y ajouter nous-mêmes les répertoires
    des DLL runtime CUDA/cuBLAS installées via les paquets pip nvidia-cuda-runtime-cu12 / nvidia-cublas-cu12.
    """
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return

    # "nvidia" est un namespace package (pas de __init__.py) : __file__ est None,
    # il faut passer par __path__ pour retrouver son emplacement sur le disque.
    nvidia_roots = [Path(p) for p in nvidia.__path__]
    bin_dirs = [
        root / sub
        for root in nvidia_roots
        for sub in ("cuda_runtime/bin", "cublas/bin", "cuda_nvrtc/bin")
    ]
    existing = [str(d) for d in bin_dirs if d.is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing) + os.pathsep + os.environ.get("PATH", "")


_register_nvidia_dll_dirs()

from llama_cpp import Llama  # noqa: E402 (doit être importé après l'ajustement du PATH ci-dessus)

from config import Config

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMClient:
    def __init__(self, config: Config):
        self.llm = Llama(
            model_path=str(config.model_path),
            n_ctx=config.n_ctx,
            n_gpu_layers=config.n_gpu_layers,
            verbose=False,
        )
        self.max_tokens = config.max_tokens
        self._warmup()

    def _warmup(self) -> None:
        """La première inférence GPU paie un coût de compilation JIT (~20-30s) ;
        on l'absorbe ici plutôt que lors du premier message de l'utilisateur."""
        list(self.llm.create_chat_completion(messages=[{"role": "user", "content": "Salut"}], max_tokens=1, stream=True))

    def stream(self, messages: list[dict]) -> Iterable[dict]:
        return self.llm.create_chat_completion(messages=messages, stream=True, max_tokens=self.max_tokens)

    def complete(self, messages: list[dict]) -> str:
        response = self.llm.create_chat_completion(messages=messages, stream=False, max_tokens=self.max_tokens)
        content = response["choices"][0]["message"]["content"] or ""
        return THINK_BLOCK_RE.sub("", content).strip()

    def close(self) -> None:
        self.llm.close()
