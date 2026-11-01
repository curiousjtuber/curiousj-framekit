"""What every command here shares: click with the help laid out as the
module docstring has it, the exit statuses, the global options, and the
few things the old shell scripts each had a copy of -- die, say, a
question with a default, a file written with a diff shown first and a
timestamped backup, and a subprocess run that is logged under -v."""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import click

EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_ABORT = 130


class Error(Exception):
    """A failure the user is told about in one line, as `die` did: run()
    prints it with the program's name and exits 1 (or `code`)."""

    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


class Abort(Exception):
    """The user left a prompt or picker without choosing; exit 130."""


def die(message: str) -> None:
    raise Error(message)


@dataclass
class Options:
    """The global options, in click's ctx.obj for every subcommand.

    yes      answer yes to every question
    check    report what would change and change nothing
    verbose  log each command run, and more with -vv
    """

    yes: bool = False
    check: bool = False
    verbose: int = 0


pass_options = click.make_pass_decorator(Options, ensure=True)


class _HandLaidHelp:
    """Help as written -- the usage lines in the docstring are laid out by
    hand -- with the option summary after it. -h works like --help."""

    context_settings = {"help_option_names": ["-h", "--help"]}

    def __init__(self, *args, **kw):
        settings = dict(self.context_settings, **(kw.pop("context_settings", None) or {}))
        super().__init__(*args, context_settings=settings, **kw)

    def format_help(self, ctx, formatter):
        formatter.write((self.help or "").rstrip() + "\n")
        self.format_options(ctx, formatter)


class Command(_HandLaidHelp, click.Command):
    """A command whose help is its module docstring as written."""


class Group(_HandLaidHelp, click.Group):
    """The same for a command with subcommands; the docstring lists them."""

    def format_options(self, ctx, formatter):
        # click.Group appends its own command list here; the docstring has one.
        click.Command.format_options(self, ctx, formatter)


def run_main(command: click.Command, argv: list[str] | None, prog: str) -> int:
    """command as a main(): its return value as the exit status, a usage
    error printed and 2, an Error printed with the program's name and its
    code, an Abort 130, --help printed and 0."""
    try:
        rv = command.main(args=argv, prog_name=prog, standalone_mode=False)
    except click.UsageError as e:
        e.show()
        return EXIT_USAGE
    except click.ClickException as e:
        e.show()
        return e.exit_code
    except Error as e:
        print(f"{prog}: {e}", file=sys.stderr)
        return e.code
    except Abort:
        return EXIT_ABORT
    return rv if isinstance(rv, int) else 0


# --- messages -----------------------------------------------------------

def tilde(path: str | os.PathLike) -> str:
    """str(path) with the home directory shown as ~, as the scripts did."""
    s = str(path)
    home = str(Path.home())
    return "~" + s[len(home):] if s == home or s.startswith(home + "/") else s


def say(what: str, detail: str = "", out=None) -> None:
    """A two-column progress line: `ok  ~/.config/x`, `copy  ...`."""
    print(f"{what:<14} {detail}".rstrip(), file=out or sys.stdout)


def note(message: str) -> None:
    print(f"note: {message}", file=sys.stderr)


def log(opts: Options, message: str, level: int = 1) -> None:
    """Printed to stderr when -v is given `level` times or more."""
    if opts.verbose >= level:
        print(message, file=sys.stderr)


# --- questions ------------------------------------------------------------

def confirm(opts: Options, question: str, default: bool = True,
            ask=None) -> bool:
    """Whether to go ahead. --check says no to everything (and nothing is
    changed); --yes says yes; without a terminal the default stands; else
    the question is asked, Enter taking the default."""
    if opts.check:
        return False
    if opts.yes:
        return True
    ask = ask or _tty_input
    if ask is _tty_input and not (sys.stdin.isatty() and sys.stdout.isatty()):
        return default
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            reply = ask(f"{question} {hint} ").strip().lower()
        except EOFError:
            raise Abort from None
        if reply == "":
            return default
        if reply in ("y", "yes"):
            return True
        if reply in ("n", "no"):
            return False
        print("  y or n", file=sys.stderr)


def _tty_input(prompt: str) -> str:
    return input(prompt)


# --- files --------------------------------------------------------------

def stamp(now: float | None = None) -> str:
    """The suffix of a backup, `20261031-201500`."""
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now))


def backup(path: Path, when: str | None = None) -> Path:
    """Copy path to <path>.bak-<stamp>, and return the copy's path."""
    dest = path.with_name(f"{path.name}.bak-{when or stamp()}")
    shutil.copy2(path, dest)
    return dest


def diff(old: str, new: str, name: str) -> str:
    """A unified diff of two texts, labelled with the file's name."""
    lines = difflib.unified_diff(old.splitlines(keepends=True),
                                 new.splitlines(keepends=True),
                                 fromfile=name, tofile=name)
    return "".join(lines)


def write_file(opts: Options, path: str | os.PathLike, content: str, *,
               mode: int | None = None, ask=None, out=None) -> bool:
    """Write content to path if it differs from what is there, the way
    setup.sh changed a file: the diff shown, the question asked (see
    confirm), the old file copied to <path>.bak-<stamp> first. True when
    the file was written. Under --check it says what would change and
    writes nothing."""
    path = Path(path)
    name = tilde(path)
    old = path.read_text() if path.exists() else None
    if old == content:
        say("ok", name, out)
        return False
    if old is None:
        say("would create" if opts.check else "create", name, out)
    else:
        say("would change" if opts.check else "change", name, out)
        print(diff(old, content, name), end="", file=out or sys.stdout)
    if not confirm(opts, f"write {name}?", True, ask):
        return False
    if old is not None:
        say("backup", tilde(backup(path)), out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if mode is not None:
        path.chmod(mode)
    return True


# --- commands -----------------------------------------------------------

def run(opts: Options, argv: list[str], *, check: bool = True,
        capture: bool = False, timeout: float | None = None,
        **kw) -> subprocess.CompletedProcess:
    """subprocess.run with the command logged under -v. `check` raises
    Error naming the command on a non-zero exit, unlike subprocess's
    CalledProcessError; `capture` returns its output as text."""
    log(opts, "+ " + " ".join(argv))
    try:
        proc = subprocess.run(argv, text=True, timeout=timeout,
                              capture_output=capture, **kw)
    except FileNotFoundError:
        raise Error(f"missing required command: {argv[0]}") from None
    except subprocess.TimeoutExpired:
        raise Error(f"timed out: {' '.join(argv)}") from None
    if check and proc.returncode != 0:
        detail = f": {proc.stderr.strip()}" if capture and proc.stderr.strip() else ""
        raise Error(f"{argv[0]} failed (exit {proc.returncode}){detail}")
    return proc


def output(opts: Options, argv: list[str], timeout: float | None = 5,
           default: str | None = None) -> str | None:
    """A command's stdout, stripped, or `default` when it is missing, fails
    or times out: for the probes status makes, where a missing tool is a
    `?` in a column, not an error."""
    log(opts, "+ " + " ".join(argv))
    try:
        proc = subprocess.run(argv, text=True, capture_output=True,
                              timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return default
    if proc.returncode != 0:
        return default
    return proc.stdout.strip()
