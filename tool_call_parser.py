"""Extraction des appels d'outils au format <tool_call><function=X><parameter=Y>...</parameter></function></tool_call>
généré par le template de chat du modèle (llama-cpp-python ne le parse pas nativement pour ce modèle)."""

import re

TOOL_CALL_RE = re.compile(r"<tool_call>\s*<function=([\w-]+)>(.*?)</function>\s*</tool_call>", re.DOTALL)
PARAM_RE = re.compile(r"<parameter=([\w-]+)>\s*(.*?)\s*</parameter>", re.DOTALL)


def extract_tool_calls(text: str) -> list[dict]:
    """Retourne [{"name": str, "arguments": dict}, ...] pour chaque appel détecté dans `text`."""
    calls = []
    for m in TOOL_CALL_RE.finditer(text):
        name = m.group(1)
        arguments = {pname: pval.strip() for pname, pval in PARAM_RE.findall(m.group(2))}
        calls.append({"name": name, "arguments": arguments})
    return calls
