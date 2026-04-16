"""Recupera UTF-8 mal interpretado (mojibake) em ficheiro .py com conteúdo misto."""
from __future__ import annotations

from pathlib import Path

# Inclui Latin Extended (ex.: Ÿ em lixo de emoji) até U+02FF; acima disso separa (CJK, etc.).
_MAX_MOJIBAKE_RUN = 0x02FF

# Tríades típicas: UTF-8 de — e … lido como Latin-1/cp1252 e gravado como Unicode errado.
_MOJIBAKE_TRIPLES = (
    ("\u00e2\u20ac\u201d", "\u2014"),  # â€" -> —
    ("\u00e2\u20ac\u00a6", "\u2026"),  # â€¦ -> …
    ("\u00e2\u20ac\u00a2", "\u2022"),  # â€¢ -> •
)


def _fix_latin1_buffer(s: str) -> str:
    if not s:
        return s
    s2 = "".join(ch for ch in s if not (0x80 <= ord(ch) <= 0x9F))
    s2 = "".join(ch for ch in s2 if ord(ch) < 256)
    if not s2:
        return s
    try:
        return s2.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def fix_mixed_line(line: str) -> str:
    out: list[str] = []
    buf: list[str] = []
    for ch in line:
        if ord(ch) <= _MAX_MOJIBAKE_RUN:
            buf.append(ch)
        else:
            if buf:
                out.append(_fix_latin1_buffer("".join(buf)))
                buf = []
            out.append(ch)
    if buf:
        out.append(_fix_latin1_buffer("".join(buf)))
    return "".join(out)


def apply_triple_replacements(text: str) -> str:
    for a, b in _MOJIBAKE_TRIPLES:
        text = text.replace(a, b)
    return text


def main() -> None:
    p = Path(__file__).resolve().parent / "app.py"
    orig = p.read_text(encoding="utf-8")
    raw = orig
    n_pass = 0
    while True:
        lines = raw.splitlines(keepends=True)
        new_raw = "".join(fix_mixed_line(L) for L in lines)
        new_raw = apply_triple_replacements(new_raw)
        if new_raw == raw:
            break
        raw = new_raw
        n_pass += 1
        if n_pass > 15:
            raise SystemExit("demasiadas passagens")
    if raw == orig:
        print("Nada alterado.")
        return
    p.write_text(raw, encoding="utf-8", newline="")
    print(f"app.py corrigido em {n_pass} passagem(ns).")


if __name__ == "__main__":
    main()
