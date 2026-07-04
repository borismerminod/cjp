"""Coloration syntaxique des blocs de code via pygments (best-effort, jamais bloquant)."""

from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

_STYLE = get_style_by_name("friendly")  # lisible sur fond gris clair (#eeeeee)


def highlight_code(code: str, language: str | None) -> list[tuple[str, str | None]]:
    """Retourne une liste de (fragment_texte, couleur_hex_ou_None).

    Ne lève jamais d'exception : en cas d'échec de résolution du lexer ou de tout
    autre problème, retourne [(code, None)] — pas de coloration, le fond gris/police
    monospace du tag "code" restent le rendu de secours.
    """
    try:
        lexer = get_lexer_by_name(language) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()

    try:
        fragments = []
        for token_type, value in lex(code, lexer):
            if not value:
                continue
            color = _STYLE.style_for_token(token_type)["color"]
            fragments.append((value, f"#{color}" if color else None))
        return fragments
    except Exception:
        return [(code, None)]
