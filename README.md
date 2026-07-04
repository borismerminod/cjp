# cjp

Agent de code en Python avec interface graphique (Tkinter), sur le modèle d'Aider / Claude Code.

## Ce qui est installé pour ce projet

Tout est confiné à un environnement virtuel Python (`venv/`) local au projet — rien n'est installé
globalement sur la machine, à l'exception d'un pilote NVIDIA à jour (déjà présent) et de Python lui-même
(Tkinter fait partie de la bibliothèque standard Python, aucune installation séparée n'est nécessaire).

**Dépendances Python** (listées dans [requirements.txt](requirements.txt), installées dans `venv/`) :

| Paquet | Rôle |
|---|---|
| `llama-cpp-python` | Fait tourner le modèle GGUF directement dans le process Python (build accéléré GPU/CUDA, récupéré depuis le dépôt de wheels précompilées du projet plutôt que PyPI) |
| `nvidia-cuda-runtime-cu12` | Runtime CUDA (DLL) nécessaire à `llama-cpp-python` pour utiliser le GPU |
| `nvidia-cublas-cu12` | Bibliothèque cuBLAS (calcul matriciel GPU) nécessaire à `llama-cpp-python` |
| `python-dotenv` | Lecture du fichier `.env` |
| `pygments` | Coloration syntaxique des blocs de code dans les réponses |
| `psutil` | Mesure de la RAM utilisée par l'application (affichage des stats) |
| `ddgs` | Recherche web (DuckDuckGo, Bing, Brave, Google, Mojeek, Startpage, Yahoo, Yandex — sans clé API) utilisable par le modèle |

**Modèle** : le fichier `.gguf` du modèle n'est pas installé par ce projet — il est référencé via un
chemin choisi dans l'interface (ou `MODEL_PATH` dans `.env` au premier lancement). Le modèle par défaut
utilisé jusqu'ici (`ornith-1.0-9b-Q4_K_M.gguf`, ~5,6 Go) a été téléchargé au préalable par
[LM Studio](https://lmstudio.ai/) et se trouve sous `C:\Users\<toi>\.lmstudio\models\...`. LM Studio
lui-même n'est plus nécessaire pour faire tourner l'agent (le modèle n'est plus chargé que par notre
propre code), mais le fichier `.gguf` doit rester présent sur le disque à cet emplacement.

## Installation

Prérequis : Python 3.11, un pilote NVIDIA à jour (pour l'accélération GPU).

```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

pip install -r requirements.txt
```

Copier `.env.example` vers `.env` et ajuster `MODEL_PATH` vers l'emplacement réel d'un fichier `.gguf`
(ce chemin ne sert que de modèle par défaut au tout premier lancement — d'autres modèles peuvent ensuite
être ajoutés directement depuis l'interface) :

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

Une fenêtre s'ouvre avec :
- une **combo liste de modèles** en haut, avec un bouton "Parcourir..." pour choisir un autre fichier `.gguf` via l'explorateur Windows (le modèle sélectionné est mémorisé pour les prochains lancements, dans `known_models.json`) ;
- une **combo liste de mode** (chat / agent / plan, voir plus bas) et des boutons **"+ Dossier"**/**"+ Fichier"** pour ajouter du contexte ; les dossiers/fichiers ajoutés apparaissent sous forme d'étiquettes juste en dessous, chacune avec une croix "✕" pour la retirer directement ;
- une case à cocher **"Recherche web"** pour autoriser ou non le modèle à chercher sur internet, accompagnée d'une **combo liste de moteurs** (DuckDuckGo par défaut, ou Bing/Brave/Google/Mojeek/Startpage/Yahoo/Yandex) ;
- à droite, un **indicateur de stats** (vitesse de génération en tokens/s, RAM utilisée par l'application, VRAM utilisée sur le GPU) ;
- un **panneau latéral gauche** listant les conversations précédentes (par date de création, ou un nom personnalisé si renommée), avec un bouton "Nouvelle conversation" ; clic droit sur une conversation pour la renommer ou la supprimer ;
- une **zone principale** affichant les échanges, avec rendu Markdown léger (gras, italique, titres, listes) et coloration syntaxique par langage dans les blocs de code ; la réflexion du modèle (balises `<think>...</think>`) est repliée par défaut sous une ligne `[réflexion ▸]` cliquable pour l'afficher ; clic droit sur un message ou un bloc de code pour le copier ;
- une **zone de saisie** en bas (Entrée pour envoyer, Maj+Entrée pour un saut de ligne) ; taper `@` y ouvre une liste des fichiers des dossiers de contexte ajoutés, pour en cibler un précisément (son contenu est alors joint au message envoyé).

### Recherche web

Quand la case "Recherche web" est cochée (activée par défaut), le modèle peut chercher sur internet
quand c'est pertinent (actualités, informations récentes, etc.) via le moteur choisi dans la combo liste
juste à côté : une ligne "🔍 Recherche : <requête>" s'affiche pendant qu'il interroge le moteur, sans
qu'aucune action ne soit nécessaire de ta part. Il peut enchaîner jusqu'à 3 recherches pour une même
question afin d'affiner sa requête si besoin, avant de synthétiser une réponse finale. Décocher la case
désactive complètement cette capacité pour les messages suivants. Note : Ecosia n'est pas supporté par
la bibliothèque de recherche utilisée (`ddgs`), seuls les moteurs listés ci-dessus sont disponibles.

### Modes chat / agent / plan

- **chat** : mode par défaut, le modèle discute (avec recherche web en option), sans toucher aux fichiers.
- **agent** : le modèle peut lire (`read_file`, `list_directory`) et modifier (`write_file`, `edit_file`)
  les fichiers des dossiers de contexte ajoutés. **Chaque modification est présentée sous forme de diff
  coloré dans la conversation, avec des liens "Accepter"/"Rejeter" — rien n'est écrit sur le disque tant
  que tu n'as pas cliqué "Accepter".**
- **plan** : le modèle peut lire/explorer les fichiers mais n'a **structurellement** pas accès aux outils
  d'écriture (ils ne lui sont même pas proposés). Il doit produire un plan structuré, étape par étape.
  Un lien "Accepter le plan" apparaît à la fin de sa réponse ; cliquer dessus bascule automatiquement en
  mode agent et relance l'exécution du plan (avec les mêmes confirmations de diff que ci-dessus).

Les dossiers **et fichiers individuels** ajoutés au contexte définissent à la fois la liste des fichiers
proposés par `@` et le périmètre autorisé pour les outils de fichiers (aucun accès en dehors) — ils sont
propres à chaque conversation (ajoutés dans une conversation, absents des autres) et sauvegardés avec elle.

Pas d'exécution de commande shell pour l'instant (`run_command`) — prévu pour une étape ultérieure.

Le chargement (ou changement) de modèle prend quelques secondes ; l'interface reste réactive pendant la
génération d'une réponse, à l'exception de la saisie et de la combo modèle qui sont désactivées jusqu'à
la fin de la réponse en cours. Le bouton "Envoyer" devient un bouton "Arrêter" pendant la génération,
pour interrompre une réponse en cours (y compris pendant l'attente d'une confirmation de modification de
fichier). Seule la réponse finale (sans la réflexion) est conservée dans l'historique de conversation.

L'historique de chaque conversation (et ses dossiers de contexte) est sauvegardé automatiquement dans
`sessions/`.

## Créer un exécutable Windows

L'application peut être empaquetée en exécutable autonome (dossier `cjp.exe` + fichiers de support) via
[PyInstaller](https://pyinstaller.org/), pour la lancer sans installer Python ni activer de venv.

```bash
venv\Scripts\activate
pip install -r requirements-build.txt
python -m PyInstaller build.spec --noconfirm
copy .env.example dist\cjp\.env.example
```

Résultat dans `dist/cjp/` (~2 Go, DLL CUDA/GPU incluses — c'est normal, `ggml-cuda.dll` seul fait
~1 Go). Copier `dist/cjp/.env.example` vers `dist/cjp/.env` et renseigner `MODEL_PATH` avant le premier
lancement, exactement comme en mode développement (voir "Installation" plus haut) — l'exécutable est
**portable** : toutes ses données (`.env`, `known_models.json`, `session_titles.json`, `sessions/`) sont
stockées à côté de `cjp.exe`, pas dans le dossier du projet ni dans `%APPDATA%`. Il suffit de garder tout
le dossier `dist/cjp/` ensemble pour le déplacer ou le partager.

Le fichier `build.spec` gère explicitement l'inclusion des DLL de `llama-cpp-python` et des runtimes
CUDA/cuBLAS (non détectées automatiquement par l'analyse statique de PyInstaller, chargées
dynamiquement via `ctypes`) — ne pas utiliser `pyinstaller main.py` directement, toujours passer par
`build.spec`.

## Désinstallation

Tout est contenu dans le dossier du projet, la désinstallation se limite donc à :

```bash
deactivate          # si le venv est actuellement activé
```

Puis supprimer :
- le dossier `venv/` (contient toutes les dépendances Python listées ci-dessus — rien n'a été installé hors de ce dossier)
- le dossier `sessions/` (historiques de conversation sauvegardés), si tu veux aussi effacer ton historique
- le fichier `.env` (contient ta configuration locale, notamment `MODEL_PATH`)
- le fichier `known_models.json` (liste des modèles ajoutés via "Parcourir...", propre à ta machine)
- le fichier `session_titles.json` (noms personnalisés donnés aux conversations)
- les dossiers `build/` et `dist/` si tu as construit l'exécutable (voir section précédente)

Les fichiers `.gguf` des modèles ne sont pas gérés par ce projet : pour les supprimer, il faut les
retirer directement depuis l'endroit où ils ont été téléchargés (ex: l'interface de LM Studio) ou
supprimer les fichiers correspondants sur le disque.

Le reste du dossier du projet (`main.py`, `gui.py`, `config.py`, etc.) peut ensuite être supprimé
normalement, comme n'importe quel dossier.
