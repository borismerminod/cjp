"""Rendu Markdown léger (gras, italique, code inline, titres, puces) pour affichage Tkinter.

Volontairement limité : pas de citations, pas de listes imbriquées/multi-lignes.
"""

import re
from typing import Callable

_INLINE_RE = re.compile(
    r"(?P<bold>\*\*(?P<bold_text>[^\n]+?)\*\*)"
    r"|(?P<code>`(?P<code_text>[^`\n]+?)`)"
    r"|(?P<italic>\*(?P<italic_text>[^\n*]+?)\*)",
    re.DOTALL,
)
_HEADER_RE = re.compile(r"^(#{1,3})[ \t]+(.*)$")
_BULLET_RE = re.compile(r"^[ \t]*[-*][ \t]+(.*)$")

EmitFn = Callable[[str, tuple[str, ...]], None]


def render_markdown(text: str, emit: EmitFn) -> None:
    """Découpe `text` en segments stylés, appelant emit(segment, tags_supplementaires)
    pour chacun. Le texte concaténé de tous les segments émis reconstitue `text`
    à l'identique (aucune perte/duplication de caractères)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        newline = "\n" if i < len(lines) - 1 else ""
        header_match = _HEADER_RE.match(line)
        bullet_match = _BULLET_RE.match(line)
        if header_match:
            level = len(header_match.group(1))
            _emit_inline(header_match.group(2), emit, (f"md_h{level}",))
            emit(newline, ())
        elif bullet_match:
            emit("• ", ("md_bullet",))
            _emit_inline(bullet_match.group(1), emit, ("md_bullet",))
            emit(newline, ())
        else:
            _emit_inline(line, emit, ())
            emit(newline, ())


def _emit_inline(line: str, emit: EmitFn, extra: tuple[str, ...]) -> None:
    pos = 0
    for m in _INLINE_RE.finditer(line):
        if m.start() > pos:
            emit(line[pos : m.start()], extra)
        if m.group("bold"):
            emit(m.group("bold_text"), extra + ("md_bold",))
        elif m.group("code"):
            emit(m.group("code_text"), extra + ("md_inline_code",))
        elif m.group("italic"):
            emit(m.group("italic_text"), extra + ("md_italic",))
        pos = m.end()
    if pos < len(line):
        emit(line[pos:], extra)
