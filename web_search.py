"""Recherche web via plusieurs moteurs (paquet ddgs), sans clé API."""

# Moteurs texte supportés par ddgs (Ecosia n'en fait pas partie, non géré par cette bibliothèque).
SEARCH_ENGINES = ["duckduckgo", "bing", "brave", "google", "mojeek", "startpage", "yahoo", "yandex"]
DEFAULT_SEARCH_ENGINE = "duckduckgo"

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Recherche des informations actuelles sur internet.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "La requête de recherche"}},
            "required": ["query"],
        },
    },
}


def web_search(query: str, engine: str = DEFAULT_SEARCH_ENGINE, max_results: int = 5) -> str:
    """Effectue une recherche et retourne un texte formaté (titre, extrait, URL par résultat).

    Ne lève jamais d'exception : retourne un message d'erreur textuel en cas de problème
    (réseau, blocage, moteur invalide, etc.), pour que le modèle puisse s'adapter.
    """
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, backend=engine, max_results=max_results))
        if not results:
            return "Aucun résultat trouvé."
        return "\n".join(f"- {r['title']}\n  {r['body']}\n  {r['href']}" for r in results)
    except Exception as e:
        return f"Erreur lors de la recherche web : {e}"
