"""Séparation à la volée d'un flux de texte en blocs réflexion/réponse (balises <think>...</think>)."""

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


class ThinkStreamSplitter:
    """Sépare à la volée un flux de texte en blocs 'réflexion' (<think>...</think>) et 'réponse finale'.

    Tolère que les balises soient coupées entre deux morceaux de flux, et fonctionne
    normalement si le modèle ne produit aucune balise <think>.
    """

    def __init__(self, on_reasoning, on_answer):
        self._pending = ""
        # Le template de chat du modèle insère "<think>\n" avant que la génération
        # ne commence : le flux ne contient donc jamais la balise d'ouverture, seulement "</think>".
        self._in_think = True
        self._on_reasoning = on_reasoning
        self._on_answer = on_answer

    def feed(self, piece: str) -> None:
        buffer = self._pending + piece
        while True:
            tag, tag_len = (THINK_CLOSE, len(THINK_CLOSE)) if self._in_think else (THINK_OPEN, len(THINK_OPEN))
            idx = buffer.find(tag)
            if idx != -1:
                emit = self._on_reasoning if self._in_think else self._on_answer
                emit(buffer[:idx])
                buffer = buffer[idx + tag_len :]
                self._in_think = not self._in_think
                continue

            safe_len = max(0, len(buffer) - (tag_len - 1))
            if safe_len:
                emit = self._on_reasoning if self._in_think else self._on_answer
                emit(buffer[:safe_len])
                buffer = buffer[safe_len:]
            break
        self._pending = buffer

    def flush(self) -> None:
        if self._pending:
            emit = self._on_reasoning if self._in_think else self._on_answer
            emit(self._pending)
            self._pending = ""
