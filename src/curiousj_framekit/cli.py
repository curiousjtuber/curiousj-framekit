"""cjf -- curiousj's kit for the Steam Frame.

    cjf [-v] [--yes] [--check] COMMAND [ARGS...]
    cjf                                 pick a command from a menu

    status        the versions of SteamOS, SteamVR and the Steam client, the live state
    install       install or update an optional item: apps, packages, services, fonts
    installed     every catalog item's state
    outdated      every installed item against its upstream: current, outdated, behind
    update        install the newer versions outdated finds
    uninstall     remove one catalog item
    init          the base: PATH, init.sh, the shims, the rc blocks
    cursor        the mouse cursor in Desktop Mode and Frametop's desktop
    wifi          the saved Wi-Fi networks in range
    vr            the headset and VR controllers: battery, or turn off
    controllers   the Steam Controllers paired over Bluetooth
    rdp           serve a Plasma desktop on the Frame over RDP
    pkg           build or relocate a package under ~/.local (pacman-home is its pacman)
    after-update  what to re-check after a SteamOS update, as one command
    migrate       move a Frame set up by steam-frame-utils to this kit

Run bare, on a terminal, it lists the commands and runs the one picked
(fzf when installed, else a numbered menu). A command with actions of
its own (vr, controllers, cursor, rdp, pkg) opens a second menu of
them, a required argument (uninstall NAME) is asked for, and `help` on
any menu is that command's --help. The command line it ran is printed
at the end, to type next time. The options go before the command: -v
logs each command run (-vv more), --yes answers yes to every question,
--check reports what a command would change and changes nothing.
curiousj-framekit is the same command under its full name. Beat
Saber's two tools are commands of their own: beat-saber-recent and
bsmanager.
"""

from __future__ import annotations

import shlex
import sys

import click

from . import cmdline, pick
from .cmdline import Entry, Options
from .frame import after_update, controllers, cursor, pkg, rdp, vr, wifi
from .install import commands, init, migrate, status, update

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
    argv = pick_argv(ctx)
    try:
        return run_argv(ctx, argv)
    finally:
        # fzf leaves no trace of the pick: say what ran, to type next
        # time.
        print(f"ran: {PROG} {shlex.join(argv)}", file=sys.stderr)


# --- the menus --------------------------------------------------------

def required(cmd: click.Command) -> tuple[str, ...]:
    """The metavars of cmd's required arguments, NAME for uninstall."""
    return tuple(p.human_readable_name for p in cmd.params
                 if isinstance(p, click.Argument) and p.required)


def entries(cmd: click.Command) -> list[Entry] | None:
    """What the menu offers under cmd: a group's commands, each with its
    required arguments in the label, or a command's own actions (vr,
    controllers); None for a command that runs as it is."""
    if isinstance(cmd, click.Group):
        return [Entry(" ".join([name, *required(sub)]), (name,), sub.get_short_help_str(60))
                for name, sub in sorted(cmd.commands.items())]
    return getattr(cmd, "menu", None)


def menu_lines(menu: list[Entry]) -> list[str]:
    """`label  one-line help` for each entry, as the picker shows
    them."""
    width = max(len(e.label) for e in menu)
    return [f"{e.label:<{width}}  {e.help}" for e in menu]


def header(cmd: click.Command, argv: list[str]) -> str:
    """The menu's header: what is being picked for, then how."""
    if argv:
        headline = f"{PROG} {' '.join(argv)} -- {cmd.get_short_help_str(70)}"
    else:
        headline = (cmd.help or "").strip().splitlines()[0]
    return f"{headline}\nENTER runs the command"


def ask_value(name: str) -> str:
    """One required argument, asked for on the terminal; leaving it
    empty leaves the command."""
    try:
        value = input(f"{name}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        raise cmdline.Abort from None
    if not value:
        raise cmdline.Abort
    return value


def pick_argv(ctx: click.Context, ask=ask_value) -> list[str]:
    """The command line picked from the menus, after the program's name:
    a command, then for a group one of its commands, for vr and
    controllers one of their actions, with each required argument asked
    for; [..., "--help"] for the help entry. Raises Abort when the user
    leaves a menu without choosing."""
    if not sys.stdin.isatty():
        raise click.UsageError("a command is needed when there is no terminal "
                               "to pick one on", ctx)
    argv: list[str] = []
    cmd: click.Command = cli
    while (menu := entries(cmd)) is not None:
        help_entry = Entry("help", ("--help",),
                           f"the full help ({' '.join([PROG, *argv, '--help'])})")
        menu = menu + [help_entry]
        lines = menu_lines(menu)
        line = pick.choose(lines, " ".join([PROG, *argv]) + ">", header(cmd, argv))
        if line is None:
            raise cmdline.Abort
        entry = menu[lines.index(line)]
        argv += entry.args
        if entry is help_entry:
            return argv
        argv += [ask(name) for name in entry.ask]
        if not isinstance(cmd, click.Group):
            return argv
        cmd = cmd.commands[entry.args[0]]
    return argv + [ask(name) for name in required(cmd)]


def run_argv(ctx: click.Context, argv: list[str]) -> int:
    """Run argv as `cjf ARGV` would, under the options already
    parsed."""
    if argv == ["--help"]:
        click.echo(ctx.get_help())
        return 0
    cmd = cli.commands[argv[0]]
    with cmd.make_context(argv[0], argv[1:], parent=ctx) as sub:
        rv = cmd.invoke(sub)
    return rv if isinstance(rv, int) else 0


cli.add_command(status.status)
cli.add_command(commands.install)
cli.add_command(commands.installed)
cli.add_command(update.outdated)
cli.add_command(update.update)
cli.add_command(commands.uninstall)
cli.add_command(init.init)
cli.add_command(migrate.migrate)
cli.add_command(cursor.cursor)
cli.add_command(wifi.wifi)
cli.add_command(vr.vr_cmd, "vr")
cli.add_command(controllers.controllers_cmd, "controllers")
cli.add_command(rdp.rdp)
cli.add_command(pkg.pkg)
cli.add_command(after_update.after_update)


def main(argv: list[str] | None = None) -> int:
    return cmdline.run_main(cli, argv, PROG)


if __name__ == "__main__":
    sys.exit(main())
