"""Lê tabelas MediaWiki ({| ... |}) direto do wikitext, no mesmo formato de célula do parser de HTML:
{"text", "h" (cabeçalho), "rs" (rowspan), "cs" (colspan)}, com o último título de seção antes da tabela."""
import re

def split_top(s, sep):
    """Divide s em sep, ignorando ocorrências dentro de [[...]], {{...}} e <tags>."""
    out, depth, i, start = [], 0, 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("[[", "{{"): depth += 1; i += 2; continue
        if two in ("]]", "}}"): depth = max(0, depth - 1); i += 2; continue
        if depth == 0 and s.startswith(sep, i):
            out.append(s[start:i]); i += len(sep); start = i; continue
        i += 1
    out.append(s[start:])
    return out

ATTR = re.compile(r"""^\s*(?:[\w-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s|]+)\s*)+$""")

def cell(raw, header):
    parts = split_top(raw, "|")
    attrs, content = "", raw
    if len(parts) > 1 and ATTR.match(parts[0]):
        attrs, content = parts[0], "|".join(parts[1:])
    num = lambda k: int((re.search(k + r"""\s*=\s*["']?\s*(\d+)""", attrs) or [0, 1])[1] or 1)
    return {"text": content, "h": header, "rs": max(1, num("rowspan")), "cs": max(1, num("colspan"))}

def tables(wt):
    """Todas as tabelas (inclusive aninhadas) com seu título de seção."""
    found, stack, heading = [], [], ""
    for line in wt.splitlines():
        s = line.strip()
        h = re.match(r"^(=+)\s*(.*?)\s*\1$", s)
        if h and not stack:
            heading = h.group(2); continue
        if s.startswith("{|"):
            stack.append({"heading": heading, "rows": [], "last": None}); continue
        if not stack: continue
        t = stack[-1]
        if s.startswith("|}"):
            found.append(stack.pop())
            if stack and stack[-1]["last"] is not None:
                stack[-1]["last"]["text"] += " "  # tabela aninhada vira espaço na célula externa
            continue
        if s.startswith("|-"):
            t["rows"].append([]); t["last"] = None; continue
        if s.startswith("|+"): continue
        if s.startswith("!") or s.startswith("|"):
            header = s.startswith("!")
            body = s[1:]
            pieces = split_top(body, "!!") if header else [body]
            pieces = [q for p in pieces for q in split_top(p, "||")]
            if not t["rows"]: t["rows"].append([])
            for p in pieces:
                c = cell(p, header); t["rows"][-1].append(c); t["last"] = c
            continue
        if t["last"] is not None:
            t["last"]["text"] += "\n" + line  # célula continua na linha seguinte
    found += stack  # tabelas sem |} no fim da página
    for t in found:
        t["rows"] = [r for r in t["rows"] if r]
    return found
