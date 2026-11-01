"""cjf -- curiousj's kit for the Steam Frame.

    cjf [-v] [--yes] [--check] COMMAND [ARGS...]
    cjf                                 pick a command from a menu

    status      the versions of SteamOS, SteamVR and the Steam client

Run bare, on a terminal, it lists the commands and runs the one picked
(fzf when installed, else a numbered menu). The options go before the
command: -v logs each command run (-vv more), --yes answers yes to
every question, --check reports what a command would change and changes
nothing. curiousj-framekit is the same command under its full name.
"""

from __future__ import annotations

import sys

import click

from . import cmdline, pick
from .cmdline import Options
from .install import status

PROG = "cjf"


@click.group(cls=cmdline.Group, help=__doc__, invoke_without_command=True)
@click.option("-v", "--verbose", count=True, help="Log each command run; -vv for more.")
@click.option("--yes", is_flag=True, help="Answer yes to every question.")
@click.option("--check", is_flag=True, help="Report what would change; change nothing.")
@click.pass_context
def cli(ctx: click.Context, verbose: int, yes: bool, check: bool) -> int | None:
    ctx.obj = Options(yes=yes, check=check, verbose=verbose)
    if ctx.invoked_subcommand is not None:
        return None
    name = pick_command(ctx)
    if name is None:
        raise cmdline.Abort
    return ctx.invoke(cli.commands[name])


def command_lines(group: click.Group) -> list[str]:
    """`name  one-line help` for each command, as the picker shows them."""
    width = max(len(n) for n in group.commands)
    return [f"{name:<{width}}  {cmd.get_short_help_str(60)}"
            for name, cmd in sorted(group.commands.items())]


def pick_command(ctx: click.Context) -> str | None:
    """The name of the command picked from the menu, or None."""
    if not sys.stdin.isatty():
        raise click.UsageError("a command is needed when there is no terminal "
                               "to pick one on", ctx)
    line = pick.choose(command_lines(cli), f"{PROG}>", "ENTER runs the command")
    return line.split()[0] if line else None


cli.add_command(status.status)


def main(argv: list[str] | None = None) -> int:
    return cmdline.run_main(cli, argv, PROG)


if __name__ == "__main__":
    sys.exit(main())
