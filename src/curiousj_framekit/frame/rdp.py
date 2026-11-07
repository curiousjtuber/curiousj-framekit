"""cjf rdp -- serve a Plasma desktop running on the Frame over RDP, with
KDE's krdpserver: the one `cjf install krdpserver` builds for ~/.local
when that is installed (minutes, against the host's libraries), else
the flatpak `cjf install krdp` builds. For KRDC, Remmina or Windows
Remote Desktop: every screen of that desktop, side by side as KWin
arranges them, the cursor drawn by the viewer. Started by hand, never
automatically.

    cjf rdp start [--desktop frametop|stock|DIR] [--port N] [--user NAME] [--address ADDR] [--force] [--flatpak]
    cjf rdp stop | status [--keys] | log [LINES]
    cjf rdp password [NEW | --generate]
    cjf rdp gui

--desktop  which desktop to serve: frametop (Frametop's, runtime dir
           /run/user/UID/frametop), stock (SteamOS's Desktop,
           /run/user/UID/nested_plasma), or a runtime dir holding a
           wayland-0 socket. Default: frametop when it runs. stock
           needs --force: on SteamOS 0.4.5 the stock desktop's KWin
           (6.2.5 on its X11 backend inside gamescope) crashes in its
           screencast plugin as soon as a client connects, leaving a
           bare KWin that only logging out of it clears; Frametop's
           KWin (Wayland backend) streams fine.
--port     default 3391, or [rdp] port in the kit's config file. 3389
           is SteamOS's own xrdp (a separate X11 session), 3390
           Frametop Remote Access's krdp; this one runs beside either.
--user     the login name clients give; default the Frame's user. The
           password is the one in ~/.config/krdpd/password, made at the
           first start; `password` shows it, `password NEW` sets it,
           `--generate` makes a new random one (restart after).
--address  default 0.0.0.0, every address: the Frame's firewall already
           lets the LAN at every port above 1024, and RDP brings its
           own TLS and login (NLA). Give the tailnet address to keep it
           off the LAN.
--flatpak  the flatpak although the ~/.local build is installed.

status --keys prints key=value lines, for the GUI. gui opens the KRdp
Server window, a GTK program run by the system Python for its PyGObject.

Clients accept the Frame's self-signed certificate once (made here, in
~/.config/krdpd). KWin allows the capture through the server's desktop
file (the flatpak's exported one, or the one the package puts in
~/.local/share/applications), so neither desktop needs a permission
bypass.
One thing this doesn't do for Frametop: ask ft-screens for full frame
rate on screens you aren't looking at, so those draw slowly over RDP;
Frametop Remote Access does that for its own server. Log:
~/.local/state/krdpd.log.
"""

from __future__ import annotations

import base64
import os
import pwd
import signal
import socket
import subprocess
import sys
import time
from importlib import resources
from pathlib import Path

import click

from .. import cmdline, config, where
from ..cmdline import Options, pass_options
from . import desktops

APP = "io.github.curiousjtuber.Krdp"
GUI_ID = "io.github.curiousjtuber.Krdpd"
DEFAULT_PORT = 3391


# Fixed paths, not XDG_CONFIG_HOME and XDG_STATE_HOME: a terminal inside
# Frametop's desktop has those pointed at the nested session's folders,
# and the flatpak is granted ~/.config/krdpd.
def conf_dir() -> Path:
    return Path.home() / ".config/krdpd"


def log_path() -> Path:
    return Path.home() / ".local/state/krdpd.log"


def info_path() -> Path:
    return Path.home() / ".local/state/krdpd.info"


def flatpak_env() -> dict[str, str]:
    """flatpak keeps its instances under XDG_RUNTIME_DIR, and Frametop's
    desktop moves that to its own dir, from where `flatpak ps` would miss
    the server and `flatpak kill` couldn't reach it."""
    return dict(os.environ, XDG_RUNTIME_DIR=str(desktops.run_dir()))


def flatpak_installed(opts: Options) -> bool:
    env = flatpak_env()
    for args in (["flatpak", "--user", "info", APP], ["flatpak", "info", APP]):
        if cmdline.run(opts, args, check=False, capture=True, env=env).returncode == 0:
            return True
    return False


def home_binary() -> Path:
    """The krdpserver the pacman-home package builds for ~/.local
    (data/pkgbuilds/krdpserver), run directly: KWin matches the
    connecting process to the package's desktop file by this path."""
    return Path.home() / ".local/lib/krdpserver/bin/krdpserver"


def home_installed() -> bool:
    return os.access(home_binary(), os.X_OK)


def installed(opts: Options) -> bool:
    return home_installed() or flatpak_installed(opts)


def menu_entry_path() -> Path:
    return Path.home() / ".local/share/applications" / f"{GUI_ID}.desktop"


def menu_entry_text() -> str:
    """The KRdp Server menu entry, cjf rdp gui, which both server
    installs write: it runs cjf rdp, whichever server that starts."""
    return ("[Desktop Entry]\nType=Application\nName=KRdp Server\n"
            "GenericName=Remote Desktop Server\n"
            "Comment=Serve this Plasma desktop over RDP: start, stop, where to connect, the password\n"
            f"Exec={cmdline.cjf_path()} rdp gui\nIcon=krfb\nTerminal=false\n"
            "Categories=Network;RemoteAccess;\nKeywords=rdp;remote;krdp;krdpd;\n")


def parse_ps(text: str, app: str = APP) -> str | None:
    """The running instance's krdpserver pid from `flatpak ps
    --columns=application,child-pid`: child-pid is the app's own process
    (pid is the sandbox's)."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == app:
            return parts[1]
    return None


def instance_pid(opts: Options) -> str | None:
    out = cmdline.run(opts, ["flatpak", "ps", "--columns=application,child-pid"],
                      check=False, capture=True, env=flatpak_env()).stdout
    return parse_ps(out)


def home_pid(info: dict[str, str], proc: Path = Path("/proc"),
             binary: Path | None = None) -> str | None:
    """The pid start recorded for the ~/.local server, while that
    process is still it: its command line starts with the binary."""
    if info.get("server") != "home" or not info.get("pid"):
        return None
    try:
        argv0 = (proc / info["pid"] / "cmdline").read_bytes().split(b"\0")[0]
    except OSError:
        return None
    return info["pid"] if argv0 == os.fsencode(str(binary or home_binary())) else None


def running(opts: Options) -> tuple[str, str] | None:
    """(pid, "home" or "flatpak") of the server that runs, else None."""
    pid = home_pid(read_info())
    if pid:
        return pid, "home"
    pid = instance_pid(opts)
    if pid:
        return pid, "flatpak"
    return None


def server_label(server: str) -> str:
    return "the ~/.local build" if server == "home" else "the flatpak"


def resolve_desktop(desktop: str | None) -> Path:
    """The runtime dir to serve, from --desktop; without it the one that
    runs, Frametop's first."""
    all_desktops = desktops.desktops()
    if desktop in all_desktops:
        return all_desktops[desktop].runtime
    if desktop:
        return Path(desktop)
    for name in desktops.NAMES:
        if all_desktops[name].running():
            return all_desktops[name].runtime
    f, s = all_desktops["frametop"].runtime, all_desktops["stock"].runtime
    raise cmdline.Error(f"no desktop is running (Frametop: {f}, stock: {s}): "
                        "start one from the launcher first")


def make_password() -> str:
    return base64.b64encode(os.urandom(24)).decode().translate(str.maketrans("", "", "/+="))[:20]


def ensure_creds(opts: Options) -> None:
    conf = conf_dir()
    conf.mkdir(mode=0o700, parents=True, exist_ok=True)
    pw = conf / "password"
    if not pw.exists() or pw.stat().st_size == 0:
        fd = os.open(pw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(make_password() + "\n")
        print("made a password: cjf rdp password shows it")
    cert, key = conf / "cert.pem", conf / "key.pem"
    if not cert.exists() or cert.stat().st_size == 0:
        old = os.umask(0o077)
        try:
            cmdline.run(opts, ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                               "-days", "3650", "-subj", f"/CN={socket.gethostname()}",
                               "-keyout", str(key), "-out", str(cert)], capture=True)
        finally:
            os.umask(old)


def lan_ip(opts: Options) -> str:
    out = cmdline.output(opts, ["ip", "-4", "route", "get", "1.1.1.1"], default="") or ""
    parts = out.split()
    return parts[parts.index("src") + 1] if "src" in parts and parts.index("src") + 1 < len(parts) else ""


def tailnet_ip(opts: Options) -> str:
    out = cmdline.output(opts, ["ip", "-4", "-o", "addr", "show", "tailscale0"], default="") or ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].split("/")[0]
    return ""


def addresses(port: str, address: str, hostname: str, lan: str, tail: str) -> str:
    """`host.local:PORT  LAN:PORT  TAILNET:PORT (tailnet)`, or ADDR:PORT
    for one address."""
    if address not in ("0.0.0.0", "::", ""):
        return f"{address}:{port}"
    out = f"{hostname}.local:{port}"
    if lan:
        out += f"  {lan}:{port}"
    if tail:
        out += f"  {tail}:{port} (tailnet)"
    return out


def listening(opts: Options, port: int) -> bool:
    out = cmdline.output(opts, ["ss", "-ltn"], default="") or ""
    return any(f":{port} " in line + " " for line in out.splitlines())


def parse_info(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def read_info() -> dict[str, str]:
    try:
        return parse_info(info_path().read_text())
    except OSError:
        return {}


def desktop_label(runtime: str) -> str:
    base = os.path.basename(runtime.rstrip("/"))
    return {"nested_plasma": "the stock desktop", "frametop": "Frametop"}.get(base, base)


def default_port() -> int:
    return int(config.get("rdp", "port", DEFAULT_PORT))


# --- the commands ---------------------------------------------------------

@click.group(cls=cmdline.Group, help=__doc__,
             short_help="serve a Plasma desktop on the Frame over RDP")
def rdp() -> None:
    pass


@rdp.command(cls=cmdline.Command, help="Start krdpserver on a running desktop.")
@click.option("--desktop", help="frametop, stock, or a runtime dir with a wayland-0 socket.")
@click.option("--port", type=int, default=None, help="Default 3391, or [rdp] port in the config.")
@click.option("--user", default=None, help="The login name clients give; default this user.")
@click.option("--address", default="0.0.0.0", help="Listen address; default every address.")
@click.option("--force", is_flag=True, help="Serve the stock desktop despite its KWin crash.")
@click.option("--flatpak", is_flag=True, help="The flatpak, although the ~/.local build is installed.")
@pass_options
def start(opts: Options, desktop: str | None, port: int | None, user: str | None,
          address: str, force: bool, flatpak: bool) -> int:
    where.require_host("rdp")
    port = port or default_port()
    user = user or pwd.getpwuid(os.getuid()).pw_name
    use_home = home_installed() and not flatpak
    if not use_home and not flatpak_installed(opts):
        if flatpak:
            raise cmdline.Error("the flatpak isn't installed: cjf install krdp")
        raise cmdline.Error("rdp needs a server: cjf install krdpserver (built for ~/.local in "
                            "minutes), or cjf install krdp (the Flatpak)")
    if running(opts):
        raise cmdline.Error("already running (cjf rdp status); stop it first")
    if listening(opts, port):
        raise cmdline.Error(f"port {port} is in use (3389 is SteamOS's xrdp, 3390 Frametop Remote "
                            "Access): pick another with --port")
    runtime = resolve_desktop(desktop)
    sock = runtime / "wayland-0"
    if not sock.is_socket():
        raise cmdline.Error(f"no Wayland socket at {sock}: is that desktop running?")
    if runtime == desktops.desktops()["stock"].runtime and not force:
        raise cmdline.Error("the stock desktop's KWin crashes when captured on this SteamOS "
                            "(see --help); --force tries anyway")
    ensure_creds(opts)
    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    conf = conf_dir()
    # flatpak resolves the sandbox's xdg grants against the XDG dirs, so
    # give it the user's real ones, whatever this shell inherited from a
    # nested session; the ~/.local build gets the same, so that both
    # keep their files in the same places. WAYLAND_DISPLAY, as an
    # absolute path, is the socket flatpak connects the sandbox to (with
    # a security context, which is what KWin trusts), and the one
    # libwayland opens for the ~/.local build (trusted by its desktop
    # file).
    env = flatpak_env()
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        env.pop(var, None)
    env["WAYLAND_DISPLAY"] = str(sock)
    password = (conf / "password").read_text().strip()
    server_args = ["--plasma", "--address", address, "--port", str(port), "-u", user, "-p", password,
                   "--certificate", str(conf / "cert.pem"), "--certificate-key", str(conf / "key.pem")]
    if use_home:
        # The user's bus for its tray item, when this shell has none (ssh).
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={desktops.run_dir()}/bus")
        env["LANG"] = "C.UTF-8"
        # Qt picks its platform from XDG_SESSION_TYPE, which ssh doesn't
        # set, and once stderr isn't a terminal it logs to the journal
        # instead: the server is told both, so that it opens the Wayland
        # socket above and `cjf rdp log` holds what it said.
        env["QT_QPA_PLATFORM"] = "wayland"
        env["QT_FORCE_STDERR_LOGGING"] = "1"
        argv = [str(home_binary()), *server_args]
        cmdline.log(opts, f"+ {home_binary()} --plasma ... (the password is not logged)")
    else:
        argv = ["flatpak", "run", "--env=LANG=C.UTF-8", APP, *server_args]
        cmdline.log(opts, "+ flatpak run " + APP + " --plasma ... (the password is not logged)")
    with log.open("w") as out:
        proc = subprocess.Popen(argv, env=env, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    server = "home" if use_home else "flatpak"
    info_path().write_text(f"desktop={runtime}\nport={port}\nuser={user}\naddress={address}\n"
                           f"server={server}\npid={proc.pid}\n")
    for _ in range(20):
        if listening(opts, port):
            break
        time.sleep(0.5)
    if not listening(opts, port):
        tail = "".join(log.read_text().splitlines(keepends=True)[-5:])
        raise cmdline.Error(f"didn't come up; the log says:\n{tail.rstrip()}")
    print(f"serving {desktop_label(str(runtime))} over RDP, {server_label(server)}")
    print(f"connect to: {addresses(str(port), address, socket.gethostname(), lan_ip(opts), tailnet_ip(opts))}"
          f"   user {user}   password: cjf rdp password")
    return 0


@rdp.command(cls=cmdline.Command, help="Stop the server.")
@pass_options
def stop(opts: Options) -> int:
    where.require_host("rdp")
    run = running(opts)
    if not run:
        print("not running")
        return 0
    pid, server = run
    if server == "home":
        cmdline.log(opts, f"+ kill -TERM {pid}")
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        cmdline.run(opts, ["flatpak", "kill", APP], check=False, capture=True, env=flatpak_env())
    for _ in range(20):
        if not running(opts):
            break
        time.sleep(0.5)
    if running(opts):
        raise cmdline.Error(f"still running: {pid}")
    print("stopped")
    return 0


def keys(opts: Options) -> list[str]:
    """yes/no flags, what start served (while running), and what start can
    choose from, for the GUI."""
    run = running(opts)
    yn = lambda b: "yes" if b else "no"  # noqa: E731
    out = [f"installed={yn(installed(opts))}", f"home={yn(home_installed())}",
           f"flatpak={yn(flatpak_installed(opts))}", f"running={yn(run)}"]
    if run:
        out += [f"pid={run[0]}", f"server={run[1]}"]
        for k, v in read_info().items():
            if k in ("desktop", "port", "user", "address"):
                out.append(f"{k}={v}")
    all_desktops = desktops.desktops()
    out += [f"hostname={socket.gethostname()}", f"lan_ip={lan_ip(opts)}",
            f"tailnet_ip={tailnet_ip(opts)}",
            f"frametop={yn(all_desktops['frametop'].running())}",
            f"stock={yn(all_desktops['stock'].running())}",
            f"password={yn((conf_dir() / 'password').exists() and (conf_dir() / 'password').stat().st_size)}"]
    return out


@rdp.command(cls=cmdline.Command, help="Whether the server runs, and where to connect.")
@click.option("--keys", "as_keys", is_flag=True, help="key=value lines, for the GUI.")
@pass_options
def status(opts: Options, as_keys: bool) -> int:
    where.require_host("rdp")
    if as_keys:
        print("\n".join(keys(opts)))
        return 0
    if home_installed():
        print(f"installed: krdpserver under {cmdline.tilde(home_binary().parent.parent)} (pacman-home)")
    if flatpak_installed(opts):
        used = ", run only with start --flatpak" if home_installed() else ""
        print(f"installed: {APP} (flatpak{used})")
    if not installed(opts):
        print("not installed: cjf install krdpserver (minutes), or cjf install krdp (the Flatpak)")
    run = running(opts)
    if not run:
        print("not running")
        return 0
    pid, server = run
    info = read_info()
    print(f"running (pid {pid}, {server_label(server)}), port {info.get('port', '?')}, "
          f"serving {info.get('desktop', '?')}")
    print(f"connect to: {addresses(info.get('port', str(DEFAULT_PORT)), info.get('address', ''), socket.gethostname(), lan_ip(opts), tailnet_ip(opts))}"
          f"   user {info.get('user', '?')}")
    return 0


@rdp.command(cls=cmdline.Command, help="The last LINES lines of the server's log (default 30).")
@click.argument("lines", required=False, type=int, default=30)
def log(lines: int) -> int:
    try:
        text = log_path().read_text(errors="replace")
    except OSError:
        print("no log yet")
        return 0
    sys.stdout.write("".join(text.splitlines(keepends=True)[-lines:]))
    return 0


@rdp.command(cls=cmdline.Command,
             help="Show the password; NEW sets it; --generate makes a new random one.")
@click.argument("new", required=False)
@click.option("--generate", is_flag=True, help="A new random password.")
@pass_options
def password(opts: Options, new: str | None, generate: bool) -> int:
    where.require_host("rdp")
    conf = conf_dir()
    conf.mkdir(mode=0o700, parents=True, exist_ok=True)
    pw = conf / "password"
    if generate:
        pw.unlink(missing_ok=True)
        ensure_creds(opts)
        print(pw.read_text().strip())
    elif new:
        fd = os.open(pw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(new + "\n")
        print("set")
    elif pw.exists() and pw.stat().st_size:
        print(pw.read_text().strip())
    else:
        print("none yet: made at the first start")
    if running(opts):
        print("(restart the server for a changed password to apply)")
    return 0


def gui_script() -> Path:
    return Path(str(resources.files("curiousj_framekit") / "data" / "krdp-gui.py"))


@rdp.command(cls=cmdline.Command,
             help="Open the KRdp Server window (the system Python, for PyGObject).")
def gui() -> int:
    where.require_host("rdp gui")
    env = dict(os.environ, CJF=cmdline.cjf_path())
    os.execve("/usr/bin/python3", ["python3", str(gui_script())], env)
