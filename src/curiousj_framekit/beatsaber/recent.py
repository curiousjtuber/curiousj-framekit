"""beat-saber-recent -- the songs Beat Saber played in its recent
launches, in order, from Unity's Player.log and Player-prev.log in the
game's Proton prefix and from the songs recorded by the launch hook
below.

    beat-saber-recent [-n N | --all]
    beat-saber-recent --record
    beat-saber-recent --install-hook

Beat Saber writes a timestamped line when a level starts. Unity keeps
only two logs, the running launch's and the one before, so two launches
that played nothing push every song out of reach; PlayerData.dat has the
play counts for every song but no dates. --record copies the songs in
the two logs into ~/.local/state/curiousj-framekit/beat-saber-songs.tsv,
keeping what is there, and the plain run shows that file and the two
logs together, the last N launches that played a song (default 2). To
record every launch, set this in the game's Properties > Launch Options
in Steam, which runs the hook before and after the game, so a launch is
kept even when its own hook was missed:

  ~/.local/bin/beat-saber-recent --record; %command%; ~/.local/bin/beat-saber-recent --record

--install-hook sets that for you, with this command's full path (Steam's
own PATH has no ~/.local/bin), through the running Steam client: on the
Frame, Steam runs with its Chromium debug port open on 127.0.0.1:8080
for the VR shell, and the client's own API sets a game's launch options
and saves them. Launch options that are already set are left alone and
shown, since there is no telling what to keep.

A line means the song started, not that it was finished. Custom maps
are shown by their name, with (custom); Valve's and Beat Games' own by
their level id, which is the title without spaces.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import click

from .. import cmdline, config, where
from ..cmdline import Options, pass_options
from ..frame import steam

APPID = 620980
SONG_LINE = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\] (.*) \[BeatmapLevel:.*$")
CUSTOM = re.compile(r"^custom_level_[0-9a-f]+ \((.*)\)$")
OLD_HIST = Path.home() / ".local/state/steam-frame-utils/beat-saber-songs.tsv"


def data_dir(home: Path | None = None) -> Path:
    home = home or Path.home()
    return (home / ".local/share/Steam/steamapps/compatdata" / str(APPID)
            / "pfx/drive_c/users/steamuser/AppData/LocalLow/Hyperbolic Magnetism/Beat Saber")


def history_path() -> Path:
    return config.state_dir() / "beat-saber-songs.tsv"


def songs_in(log_text: str) -> list[str]:
    """One line per song start, tab-separated: the launch's key, which is
    its first song's time, so the same log gives the same lines whenever
    it is read; the song's time; the log's own words."""
    out = []
    launch = None
    for line in log_text.splitlines():
        m = SONG_LINE.match(line)
        if not m:
            continue
        at, name = m.group(1), m.group(2)
        if launch is None:
            launch = at
        out.append(f"{launch}\t{at}\t{name}")
    return out


def songs_from_logs(directory: Path) -> list[str]:
    out = []
    for name in ("Player-prev.log", "Player.log"):
        try:
            text = (directory / name).read_text(errors="replace")
        except OSError:
            continue
        out += songs_in(text)
    return out


def read_history(*paths: Path) -> list[str]:
    out = []
    for p in paths:
        try:
            out += [ln for ln in p.read_text().splitlines() if ln]
        except OSError:
            pass
    return out


def display(lines: list[str], n: int) -> str:
    """The last n launches (0 for all), grouped as sessions."""
    lines = sorted(set(lines))
    launches = []
    for line in lines:
        key = line.split("\t", 1)[0]
        if not launches or launches[-1] != key:
            launches.append(key)
    start = launches[-n] if n and n < len(launches) else launches[0]
    out = []
    prev = None
    showing = False
    for line in lines:
        key, at, name = (line.split("\t", 2) + ["", ""])[:3]
        if not showing and key != start:
            continue
        showing = True
        if key != prev:
            if prev is not None:
                out.append("")
            out.append(f"Session of {key[:10]}")
            prev = key
        m = CUSTOM.match(name)
        if m:
            name = f"{m.group(1)} (custom)"
        out.append(f"{at[:10]} {at[11:16]}  {name}")
    return "\n".join(out)


def own_path() -> str:
    """This command's absolute path, for the launch options."""
    argv0 = sys.argv[0] if sys.argv else ""
    if os.path.basename(argv0) == "beat-saber-recent" and "/" in argv0:
        return os.path.abspath(argv0)
    return shutil.which("beat-saber-recent") or str(Path.home() / ".local/bin/beat-saber-recent")


def hook_for(path: str) -> str:
    return f"{path} --record; %command%; {path} --record"


def install_hook(hook: str) -> int:
    def by_hand(why: str):
        raise cmdline.Error(f"{why}; set the game's Launch Options in Steam by hand to:\n  {hook}")
    try:
        result = steam.launch_options(APPID, hook)
    except cmdline.Error as e:
        by_hand(str(e))
    if "now" not in result:
        was = result["was"]
        if "beat-saber-recent" in was and "--record" in was:
            print(f"launch options already have the hook: {was}")
            return 0
        by_hand(f"launch options are set to '{was}', left as they are")
    if result["now"] != hook:
        by_hand(f"the client did not take the launch options (it has '{result['now']}')")
    print(f"launch options set to: {hook}")
    return 0


def record(directory: Path) -> None:
    hist = history_path()
    hist.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(set(read_history(hist, OLD_HIST) + songs_from_logs(directory)))
    fd, tmp = tempfile.mkstemp(prefix=hist.name + ".", dir=hist.parent)
    with os.fdopen(fd, "w") as f:
        f.write("".join(ln + "\n" for ln in lines))
    os.replace(tmp, hist)


@click.command(cls=cmdline.Command, help=__doc__)
@click.option("-n", "count", type=int, default=2, help="The last N launches (default 2).")
@click.option("--all", "all_", is_flag=True, help="Every launch recorded.")
@click.option("--record", "do_record", is_flag=True,
              help="Record the two logs' songs into the history.")
@click.option("--install-hook", "do_install", is_flag=True,
              help="Set the launch options through Steam.")
@pass_options
def cli(opts: Options, count: int, all_: bool, do_record: bool, do_install: bool) -> int:
    where.require_host("beat-saber-recent")
    if count < 1:
        raise click.UsageError("-n takes a number of launches")
    if do_install:
        return install_hook(hook_for(own_path()))
    directory = data_dir()
    if not directory.is_dir():
        raise cmdline.Error(f"no Beat Saber data at {directory}")
    if do_record:
        record(directory)
        return 0
    lines = read_history(history_path(), OLD_HIST) + songs_from_logs(directory)
    if not lines:
        print("no songs: none in the Unity logs, none recorded (see --help)")
        return 0
    print(display(lines, 0 if all_ else count))
    return 0


def main(argv: list[str] | None = None) -> int:
    return cmdline.run_main(cli, argv, "beat-saber-recent")


if __name__ == "__main__":
    sys.exit(main())
