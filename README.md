# cjp

Agent de code en Python (CLI), sur le modèle d'Aider / Claude Code.

## Ce qui est installé pour ce projet

Tout est confiné à un environnement virtuel Python (`venv/`) local au projet — rien n'est installé
globalement sur la machine, à l'exception d'un pilote NVIDIA à jour (déjà présent) et de Python lui-même.

**Dépendances Python** (listées dans [requirements.txt](requirements.txt), installées dans `venv/`) :

| Paquet | Rôle |
|---|---|
| `llama-cpp-python` | Fait tourner le modèle GGUF directement dans le process Python (build accéléré GPU/CUDA, récupéré depuis le dépôt de wheels précompilées du projet plutôt que PyPI) |
| `nvidia-cuda-runtime-cu12` | Runtime CUDA (DLL) nécessaire à `llama-cpp-python` pour utiliser le GPU |
| `nvidia-cublas-cu12` | Bibliothèque cuBLAS (calcul matriciel GPU) nécessaire à `llama-cpp-python` |
| `rich` | Rendu terminal (couleurs, markdown, spinner de chargement) |
| `prompt_toolkit` | Saisie utilisateur avancée (historique, autocomplétion) |
| `python-dotenv` | Lecture du fichier `.env` |

**Modèle** : le fichier `.gguf` du modèle (`ornith-1.0-9b-Q4_K_M.gguf`, ~5,6 Go) n'est pas installé par
ce projet — il est référencé via le chemin `MODEL_PATH` dans `.env`. Dans la configuration actuelle,
ce fichier a été téléchargé au préalable par [LM Studio](https://lmstudio.ai/) et se trouve sous
`C:\Users\<toi>\.lmstudio\models\...`. LM Studio lui-même n'est plus nécessaire pour faire tourner
l'agent (le modèle n'est plus chargé que par notre propre code), mais le fichier `.gguf` doit rester
présent sur le disque à cet emplacement.

## Installation

Prérequis : Python 3.11, un pilote NVIDIA à jour (pour l'accélération GPU).

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

pip install -r requirements.txt
```

Copier `.env.example` vers `.env` et ajuster `MODEL_PATH` vers l'emplacement réel du fichier `.gguf` :

```
MODEL_PATH=C:\chemin\vers\ton-modele.gguf
N_CTX=4096
N_GPU_LAYERS=-1
MAX_TOKENS=2048
MAX_CONTEXT_CHARS=8000
```

- `N_GPU_LAYERS=-1` décharge toutes les couches sur le GPU (rapide, ~60 tokens/s testé sur une RTX 5060 8 Go). Mettre `0` pour forcer un fonctionnement CPU uniquement (beaucoup plus lent, ~10 tokens/s).
- `MAX_TOKENS` borne la longueur de chaque réponse (utile car certains modèles de raisonnement peuvent "réfléchir" très longuement).

## Lancement

```bash
venv\Scripts\activate      # si pas déjà fait dans le terminal courant
python main.py
```

Le chargement du modèle prend quelques secondes (spinner affiché). Le modèle utilisé (`ornith-1.0-9b`)
sépare sa réflexion (balises `<think>...</think>`) de sa réponse finale ; la réflexion s'affiche en
italique grisée pendant le streaming, la réponse finale en clair. Seule la réponse finale est conservée
dans l'historique de conversation.

Commandes disponibles :
- `/reset` — réinitialise le contexte de conversation
- `/resume` — liste les sessions enregistrées
- `/resume <id>` — restaure une session précédente
- `/exit` ou `Ctrl+D` — quitte le programme

L'historique de chaque session est sauvegardé automatiquement dans `sessions/`.

## Désinstallation

Tout est contenu dans le dossier du projet, la désinstallation se limite donc à :

```bash
deactivate          # si le venv est actuellement activé
```

Puis supprimer :
- le dossier `venv/` (contient toutes les dépendances Python listées ci-dessus — rien n'a été installé hors de ce dossier)
- le dossier `sessions/` (historiques de conversation sauvegardés), si tu veux aussi effacer ton historique
- le fichier `.env` (contient ta configuration locale, notamment `MODEL_PATH`)

Le fichier `.gguf` du modèle n'est pas géré par ce projet (il appartient à LM Studio) : pour le supprimer,
il faut le retirer directement depuis l'interface de LM Studio ou supprimer le fichier indiqué par
`MODEL_PATH` sur le disque.

Le reste du dossier du projet (`main.py`, `config.py`, etc.) peut ensuite être supprimé normalement,
comme n'importe quel dossier.
