"""Marked blocks in rc files: a few lines between `# >>> NAME: PART >>>`
and `# <<< NAME: PART <<<`, which a later run finds and replaces in
place. The kit's own blocks are named curiousj-framekit; setup.sh's
were steam-frame-utils, and `cjf migrate` removes those. Pure text
functions; the files are read and written by the callers."""

from __future__ import annotations

PREFIX = "curiousj-framekit"
OLD_PREFIX = "steam-frame-utils"


def begin(part: str, prefix: str = PREFIX) -> str:
    return f"# >>> {prefix}: {part} >>>"


def end(part: str, prefix: str = PREFIX) -> str:
    return f"# <<< {prefix}: {part} <<<"


def names(text: str, prefix: str) -> list[str]:
    """The parts of every block with that prefix, in order."""
    lead = f"# >>> {prefix}: "
    found = []
    for line in text.splitlines():
        if line.startswith(lead) and line.endswith(" >>>"):
            found.append(line[len(lead):-4])
    return found


def block(text: str, part: str, prefix: str = PREFIX) -> str | None:
    """The block's full text, markers included, or None."""
    lines = text.splitlines()
    b, e = begin(part, prefix), end(part, prefix)
    if b not in lines:
        return None
    start = lines.index(b)
    try:
        stop = lines.index(e, start)
    except ValueError:
        stop = len(lines) - 1
    return "\n".join(lines[start:stop + 1]) + "\n"


def remove(text: str, part: str, prefix: str = PREFIX) -> str:
    """text without that block; unchanged when there is none. A blank
    line left where the block was, with blank neighbours, goes too."""
    lines = text.splitlines()
    b, e = begin(part, prefix), end(part, prefix)
    if b not in lines:
        return text
    start = lines.index(b)
    try:
        stop = lines.index(e, start)
    except ValueError:
        stop = len(lines) - 1
    del lines[start:stop + 1]
    if 0 < start < len(lines) and lines[start] == "" and lines[start - 1] == "":
        del lines[start]
    while lines and lines[0] == "":
        del lines[0]
    while lines and lines[-1] == "":
        del lines[-1]
    return ("\n".join(lines) + "\n") if lines else ""


def ensure(text: str, part: str, content: str, where: str = "end",
           prefix: str = PREFIX) -> str:
    """text with the block holding exactly content (lines without the
    markers). A new block goes at the end, or with `where="top"` at the
    start; an existing one stays where it is."""
    want = begin(part, prefix) + "\n" + content.rstrip("\n") + "\n" + end(part, prefix) + "\n"
    have = block(text, part, prefix)
    if have == want:
        return text
    if have is not None:
        return text.replace(have, want, 1)
    if where == "top":
        return want + ("\n" if text and not text.startswith("\n") else "") + text
    if text and not text.endswith("\n"):
        text += "\n"
    return text + want


def outside(text: str, prefix: str = PREFIX) -> str:
    """text's lines outside every block with that prefix."""
    out = []
    inside = False
    lead_b, lead_e = f"# >>> {prefix}: ", f"# <<< {prefix}: "
    for line in text.splitlines():
        if line.startswith(lead_b) and line.endswith(" >>>"):
            inside = True
            continue
        if line.startswith(lead_e) and line.endswith(" <<<"):
            inside = False
            continue
        if not inside:
            out.append(line)
    return "\n".join(out) + ("\n" if out else "")
