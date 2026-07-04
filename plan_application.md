# Plan de fonctionnalités — Agent de code en Python (CLI)

Outil terminal en Python permettant de dialoguer avec un agent LLM et de lui faire éditer des fichiers, exécuter des commandes, et gérer du contexte projet — sur le modèle d'Aider / Claude Code.

---

## Phase 0 — Socle technique

- [ ] Structure du projet (`main.py`, `tools/`, `context_manager.py`, `llm_client.py`, `config.py`)
- [ ] Gestion de la configuration (clé API, modèle choisi, chemins) via fichier `.env` ou `config.yaml`
- [ ] Boucle principale : lecture input utilisateur (`input()` ou `prompt_toolkit` pour l'historique/autocomplétion)
- [ ] Rendu terminal avec `rich` (markdown, coloration syntaxique, spinners de chargement)

---

## Phase 1 — Chat de base

- [ ] Appel à l'API LLM (SDK `anthropic`) avec streaming de la réponse token par token
- [ ] Historique de conversation en mémoire pendant la session
- [ ] Persistance de l'historique entre sessions (fichier JSON ou SQLite)
- [ ] Commande de reset (`/reset`) et de reprise de session (`/resume`)
- [ ] Gestion basique du dépassement de contexte (troncature ou résumé des messages les plus anciens)

---

## Phase 2 — Outils de base (tool use)

- [ ] Framework générique de déclaration d'outils (schéma JSON + fonction Python associée)
- [ ] Outil `read_file` : lire le contenu d'un fichier
- [ ] Outil `list_directory` : lister l'arborescence d'un dossier (avec respect du `.gitignore`)
- [ ] Outil `search_code` : recherche textuelle dans le repo (type grep, via `ripgrep` en subprocess si dispo, sinon `re`)
- [ ] Outil `write_file` : créer un nouveau fichier
- [ ] Outil `edit_file` : appliquer une modification ciblée (pas une réécriture complète) — via diff/patch
- [ ] Outil `run_command` : exécuter une commande shell (`subprocess.run`) avec capture stdout/stderr/code retour

---

## Phase 3 — Boucle agentique

- [ ] Enchaînement automatique de plusieurs appels d'outils sans repasser par l'utilisateur à chaque étape
- [ ] Limite de nombre d'itérations pour éviter les boucles infinies
- [ ] Affichage en direct de ce que fait l'agent (quel outil, sur quel fichier, quelle commande)
- [ ] Gestion des erreurs d'outil (fichier inexistant, commande qui échoue) et retour de l'erreur au modèle pour qu'il s'adapte

---

## Phase 4 — Validation humaine et sécurité

- [ ] Affichage du diff avant application d'une modification de fichier (via `difflib` ou en déléguant à `git diff`)
- [ ] Confirmation interactive (`y/n`) avant d'appliquer un edit ou d'exécuter une commande sensible
- [ ] Mode `--yolo` optionnel pour désactiver les confirmations (usage avancé)
- [ ] Liste noire de commandes dangereuses (`rm -rf`, `sudo`, etc.) nécessitant une confirmation renforcée
- [ ] Timeout sur les commandes longues

---

## Phase 5 — Gestion du contexte projet

- [ ] Ajout manuel de fichiers au contexte via commande (`/add chemin/fichier.py`)
- [ ] Retrait de fichiers du contexte (`/drop`)
- [ ] Chargement automatique de la structure du projet (arborescence + fichiers de config type `package.json`, `pyproject.toml`)
- [ ] Fichier de règles persistant (type `AGENT.md`) lu automatiquement au démarrage pour orienter le style de code / conventions du projet
- [ ] Affichage de ce qui est actuellement dans le contexte (`/context`)

---

## Phase 6 — Intégration Git (au lieu d'un système d'undo maison)

- [ ] Vérification que le projet est bien un repo git au démarrage (avertissement sinon)
- [ ] Commit automatique après chaque modification acceptée (avec message généré ou préfixé par l'agent)
- [ ] Commande d'annulation (`/undo`) qui s'appuie sur `git revert`/`git reset`
- [ ] Affichage du statut git courant (`/status`)

---

## Phase 7 — Contexte avancé (repo volumineux)

- [ ] Indexation sémantique du repo (embeddings) pour ne charger que les fichiers pertinents à une requête
- [ ] Base vectorielle légère locale (`sqlite-vec` ou fichier `.pkl` + `numpy` pour petits repos)
- [ ] Sélection automatique des fichiers pertinents selon la requête utilisateur (RAG basique)

---

## Phase 8 — Extensibilité (MCP)

- [ ] Support du protocole MCP pour brancher des outils externes standardisés (au lieu du framework maison uniquement)
- [ ] Configuration des serveurs MCP à connecter (fichier de config dédié)

---

## Phase 9 — Confort d'usage

- [ ] Autocomplétion des chemins de fichiers et des commandes (`prompt_toolkit`)
- [ ] Mode "chat" vs mode "code" distincts via préfixes de commande (`/chat`, `/code`)
- [ ] Support multi-modèle (Anthropic, OpenAI, modèle local via Ollama) via une couche d'abstraction
- [ ] Coloration du diff façon `delta`/`difftastic` (en subprocess si l'outil est installé)
- [ ] Documentation d'installation et d'usage (README)

---

## Bibliothèques Python à prévoir

| Besoin | Librairie |
|---|---|
| Appels LLM | `anthropic` (ou `openai`) |
| Interface terminal | `rich` |
| Input avancé (historique, autocomplétion) | `prompt_toolkit` |
| Exécution de commandes | `subprocess` (natif) |
| Diff / patch | `difflib` (natif) ou `git apply` en subprocess |
| Respect du `.gitignore` | `gitignore_parser` |
| Persistance légère | `sqlite3` (natif) ou fichiers JSON |
| Embeddings (optionnel) | `sentence-transformers` |
| Base vectorielle (optionnel) | `sqlite-vec` |
| Config | `pyyaml` ou `python-dotenv` |

---

## Ordre de priorité conseillé

1. Phase 0 + 1 (chat fonctionnel)
2. Phase 2 + 3 (agent capable d'agir sur des fichiers)
3. Phase 4 (sécurité minimale avant de laisser l'agent exécuter des commandes sans surveillance)
4. Phase 6 (s'appuyer sur git plutôt que réinventer l'undo)
5. Phase 5 (confort de contexte)
6. Phases 7, 8, 9 (améliorations une fois le cœur solide)