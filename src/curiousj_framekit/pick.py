"""The picker behind a bare `cjf` and `cjf install`: fzf when it is
installed and there is a terminal to draw on, else a numbered menu on
the tty. Taken from curiousj-tools' pick-lines, so the two kits behave
the same; choose() takes one item, choose_many() marks several (TAB in
fzf, numbers in the menu)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable

from .cmdline import Abort


def fzf_usable() -> bool:
    """Whether fzf is installed and has a terminal to draw on."""
    return bool(shutil.which("fzf")) and sys.stdin.isatty()


def fzf_argv(prompt: str, header: str = "") -> list[str]:
    """fzf as every picker here runs it, under the cursor rather than full
    screen."""
    return (["fzf", "--prompt", prompt, "--height", "60%", "--reverse"]
            + (["--header", header] if header else []))


def print_menu(items: list[str], out) -> None:
    for i, item in enumerate(items, 1):
        print(f"  {i:2d}) {item}", file=out)


def parse_menu_reply(reply: str, count: int) -> list[int] | None:
    """1-based indexes a menu answer names, [] for "all", None for an
    abort. Raises ValueError naming the first token that is not a
    choice."""
    reply = reply.replace(",", " ").strip()
    if reply in ("", "q", "Q"):
        return None
    if reply in ("a", "A"):
        return []
    picked = []
    for tok in reply.split():
        if not tok.isdigit() or not 1 <= int(tok) <= count:
            raise ValueError(tok)
        picked.append(int(tok))
    return picked


def menu_pick(items: list[str], noun: str, ask: Callable[[str], str],
              out=None) -> list[str]:
    """Numbered menu: print items to out, ask until an answer names some."""
    out = out or sys.stderr
    print_menu(items, out)
    while True:
        try:
            reply = ask(f"{noun} [1-{len(items)}, e.g. 1 3, a=all, q]: ")
        except EOFError:
            raise Abort from None
        try:
            picked = parse_menu_reply(reply, len(items))
        except ValueError as e:
            print(f"  not a choice: {e}", file=out)
            continue
        if picked is None:
            raise Abort
        if not picked:
            return list(items)
        return [items[n - 1] for n in picked]


def tty_ask(prompt: str) -> str:
    """Prompt on the controlling terminal, so stdin can stay a pipe."""
    with open("/dev/tty", "w") as out, open("/dev/tty") as inp:
        out.write(prompt)
        out.flush()
        line = inp.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n")


def fzf_pick(items: list[str], noun: str) -> list[str]:
    """Run fzf over items; its UI goes to the tty, the marked lines come
    back."""
    proc = subprocess.run(
        fzf_argv(f"{noun}> ", f"TAB marks {noun}, ENTER confirms") + ["--multi"],
        input="".join(f"{i}\n" for i in items), stdout=subprocess.PIPE, text=True,
    )
    sel = proc.stdout.splitlines()
    if proc.returncode != 0 or not sel:
        raise Abort
    return sel


def choose_many(items: Iterable[str], noun: str) -> list[str]:
    """Marked subset of items; fzf on a tty when installed, else the menu.
    Raises Abort when the user leaves without choosing."""
    items = list(items)
    if fzf_usable():
        return fzf_pick(items, noun)
    return menu_pick(items, noun, tty_ask)


MENU_LIMIT = 40


def choose(items: list[str], prompt: str, header: str = "") -> str | None:
    """One of items; None when the user leaves."""
    if not items:
        return None
    if fzf_usable():
        proc = subprocess.run(fzf_argv(prompt + " ", header), input="\n".join(items),
                              text=True, stdout=subprocess.PIPE)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        if proc.returncode != 0 or not lines:
            return None
        return lines[-1]
    return choose_numbered(items, prompt, header)


def choose_numbered(items: list[str], prompt: str, header: str = "",
                    ask: Callable[[str], str] = input, out=None) -> str | None:
    """choose() without fzf: a numbered menu of the first MENU_LIMIT items."""
    out = out or sys.stderr
    if header:
        print(header, file=out)
    shown = items[:MENU_LIMIT]
    print_menu(shown, out)
    if len(items) > len(shown):
        print(f"  ... {len(items) - len(shown)} more (install fzf to filter)", file=out)
    while True:
        try:
            reply = ask(f"{prompt} [1-{len(shown)}, or q]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=out)
            return None
        if reply in ("q", "Q", ""):
            return None
        if reply.isdigit() and 1 <= int(reply) <= len(shown):
            return shown[int(reply) - 1]
        if reply in items:
            return reply
        print(f"  not a choice: {reply}", file=out)
