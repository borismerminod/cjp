# -*- mode: python ; coding: utf-8 -*-
"""Configuration PyInstaller pour empaqueter cjp en exécutable Windows (--onedir, GPU/CUDA inclus).

Usage : venv\\Scripts\\python.exe -m PyInstaller build.spec --noconfirm
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# DLL de llama-cpp-python (llama.dll, ggml-cuda.dll, ...) — llama_cpp les cherche dans son
# propre dossier "lib/" relatif à __file__, donc on préserve cette structure de destination.
llama_cpp_binaries = collect_dynamic_libs("llama_cpp")

# DLL runtime CUDA/cuBLAS des paquets nvidia-*-cu12 — llm_client.py lit nvidia.__path__ pour
# les localiser au runtime, donc on préserve la structure de package "nvidia/<sous-paquet>/bin/".
nvidia_binaries = (
    collect_dynamic_libs("nvidia.cuda_runtime")
    + collect_dynamic_libs("nvidia.cublas")
    + collect_dynamic_libs("nvidia.cuda_nvrtc")
)

# Données de pygments (styles/lexers) et imports dynamiques que l'analyse statique de
# PyInstaller peut manquer (résolution par nom de chaîne, ex: get_lexer_by_name).
datas = collect_data_files("pygments")
hidden_imports = (
    collect_submodules("pygments.lexers")
    + collect_submodules("pygments.styles")
    + collect_submodules("ddgs.engines")
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=llama_cpp_binaries + nvidia_binaries,
    # .env.example n'est volontairement pas mis dans `datas` : PyInstaller le placerait dans
    # _internal/ alors qu'il doit se trouver à côté de cjp.exe (voir get_app_dir() dans
    # config.py) — il est copié manuellement après la construction, voir README.
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cjp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cjp",
)
