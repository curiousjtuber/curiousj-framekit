"""The `system-service` kind: Tailscale as a native system service on
the Frame, where it lives on the one partition that survives updates:

  /home/.tailscale/bin      tailscale and tailscaled, root-owned
  /home/.tailscale/state    the login and node state
  /etc/systemd/system/tailscaled.service
                            kept across updates by the default
                            atomic-update keep list (*.service, *.wants)

    cjf install tailscale [--trust]    --trust also puts tailscale0 in
                                       firewalld's trusted zone and adds
                                       that zone file to the keep list;
                                       without it only SSH is reachable
                                       over the tailnet

The download and its sha256 check run as the user; one sudo then
installs the binaries, writes the unit and enables it, so the password
is asked once. A re-run with the binaries and unit in place fixes only
what is missing (enabled, running, trusted); one with them gone (a
SteamOS update can drop the unit) reinstalls, and the login state is
kept. Logging in is interactive, so it is only reported:

    sudo /home/.tailscale/bin/tailscale up --qr --operator=steamos --ssh
"""

from __future__ import annotations

import json
import os
import pwd
import shlex
import tarfile
from pathlib import Path

from ... import cmdline, where
from ...cmdline import Error, Options
from ..catalog import Check, Fresh, Item, State, Status
from .base import Base, TempDir, fetch, fetch_text, newer, require_commands, sha256_of

PREFIX = Path("/home/.tailscale")
BIN = PREFIX / "bin"
STATE = PREFIX / "state"
UNIT = Path("/etc/systemd/system/tailscaled.service")
SOCKET = "/run/tailscale/tailscaled.sock"
KEEP = Path("/etc/atomic-update.conf.d/tailscale-firewall.conf")
PKGS = "https://pkgs.tailscale.com/stable"

UNIT_TEXT = f"""[Unit]
Description=Tailscale node agent
Documentation=https://tailscale.com/kb/
Wants=network-pre.target
After=network-pre.target NetworkManager.service systemd-resolved.service
RequiresMountsFor={PREFIX}

[Service]
# /usr/bin/iptables is the legacy backend, but the Frame kernel has no
# ip_tables module; use nftables.
Environment=TS_DEBUG_FIREWALL_MODE=nftables
ExecStart={BIN}/tailscaled --statedir={STATE} --socket={SOCKET}
RuntimeDirectory=tailscale
RuntimeDirectoryMode=0755
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""


def systemctl(opts: Options, *args: str) -> bool:
    return cmdline.run(opts, ["systemctl", *args], check=False, capture=True).returncode == 0


def backend_state(opts: Options) -> str:
    out = cmdline.output(opts, [str(BIN / "tailscale"), "status", "--json"], default="") or ""
    try:
        return json.loads(out).get("BackendState", "unknown")
    except ValueError:
        return "unknown"


def trusted(opts: Options) -> bool:
    zone = cmdline.output(opts, ["firewall-cmd", "--get-zone-of-interface=tailscale0"], default="") or ""
    return zone.strip() == "trusted" and KEEP.exists()


def missing_parts(opts: Options, want_trust: bool) -> list[str]:
    parts = []
    if not (os.access(BIN / "tailscale", os.X_OK) and os.access(BIN / "tailscaled", os.X_OK)):
        parts.append("binaries")
    if not UNIT.exists():
        parts.append("unit")
    if not systemctl(opts, "is-enabled", "--quiet", "tailscaled"):
        parts.append("enabled")
    if not systemctl(opts, "is-active", "--quiet", "tailscaled"):
        parts.append("running")
    if want_trust and not trusted(opts):
        parts.append("trusted")
    return parts


def stable_info() -> dict:
    return json.loads(fetch_text(f"{PKGS}/?mode=json"))


def installed_version(opts: Options) -> str:
    out = cmdline.output(opts, [str(BIN / "tailscale"), "version"], default="") or ""
    return out.splitlines()[0].strip() if out else ""


def tailnet_ip(opts: Options) -> str:
    out = cmdline.output(opts, ["ip", "-4", "-o", "addr", "show", "tailscale0"], default="") or ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].split("/")[0]
    return ""


class Kind(Base):
    options = "[--trust]  (tailscale0 in firewalld's trusted zone)"

    def status(self, item: Item, opts: Options) -> Status:
        if where.in_container():
            return Status(State.UNKNOWN, "a distrobox can't see it; check from the host")
        parts = missing_parts(opts, False)
        if "binaries" in parts and "unit" in parts:
            return Status(State.MISSING)
        if parts:
            return Status(State.OUTDATED, "missing " + " ".join(parts))
        backend = backend_state(opts)
        ip = tailnet_ip(opts)
        if backend == "Running":
            return Status(State.OK, f"running{', ' + ip if ip else ''}{', trusted zone' if trusted(opts) else ''}")
        return Status(State.OK, f"{backend}; log in: sudo {BIN}/tailscale up --qr --operator={pwd.getpwuid(os.getuid()).pw_name} --ssh")

    def check(self, item: Item, opts: Options, status: Status) -> Check:
        if where.in_container():
            return Check(Fresh.UNKNOWN, note=status.detail)
        have = installed_version(opts)
        found = str(stable_info().get("Version", ""))
        if not found:
            raise Error(f"no version in {PKGS}/?mode=json")
        if newer(found, have):
            return Check(Fresh.OUTDATED, have, found, "pkgs.tailscale.com stable")
        return Check(Fresh.CURRENT, have, source="pkgs.tailscale.com stable")

    def update(self, item: Item, opts: Options) -> bool:
        """The newer build over the installed one, with sudo; the login
        state stays. Missing parts are the install's job, run after."""
        where.require_host(item.name)
        check = self.check(item, opts, self.status(item, opts))
        if check.fresh != Fresh.OUTDATED:
            return self.install(item, opts, [])
        keep_trust = trusted(opts)
        cmdline.say("would upgrade" if opts.check else "upgrade",
                    f"tailscale {check.installed} -> {check.available} (with sudo; the login state is kept)")
        if opts.check:
            return True
        if not cmdline.confirm(opts, "go ahead (sudo asks for your password once)?"):
            return False
        self.reinstall(opts, keep_trust)
        self.report_login(opts)
        return True

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        where.require_host(item.name)
        want_trust = "--trust" in args or "--trust-tailnet" in args
        extra = [a for a in args if a not in ("--trust", "--trust-tailnet")]
        if extra:
            raise Error(f"tailscale takes --trust only; got {' '.join(extra)}")
        parts = missing_parts(opts, want_trust)
        if not parts:
            cmdline.say("ok", "tailscaled" + (", trusted zone" if want_trust else ""))
            self.report_login(opts)
            return False
        reinstall = "binaries" in parts or "unit" in parts
        if reinstall:
            cmdline.say("would install" if opts.check else "install",
                        f"tailscaled: {' '.join(parts)} (the latest stable arm64 build, with sudo)")
        else:
            for part in parts:
                cmdline.say(f"would {part.replace('enabled', 'enable').replace('running', 'start').replace('trusted', 'trust')}"
                            if opts.check else part.replace("enabled", "enable").replace("running", "start").replace("trusted", "trust"),
                            "tailscaled" if part != "trusted" else "tailscale0 in firewalld's trusted zone, kept across updates")
        if opts.check:
            return True
        if not cmdline.confirm(opts, "go ahead (sudo asks for your password once)?"):
            return False
        if reinstall:
            self.reinstall(opts, want_trust)
        else:
            steps = []
            if "enabled" in parts:
                steps.append("systemctl enable tailscaled")
            if "running" in parts:
                steps.append("systemctl start tailscaled")
            if "trusted" in parts:
                steps += self.trust_steps()
            cmdline.run(opts, ["sudo", "sh", "-euc", "\n".join(steps)], capture=False)
        self.report_login(opts)
        return True

    def trust_steps(self) -> list[str]:
        return ["firewall-cmd --permanent --zone=trusted --add-interface=tailscale0",
                "firewall-cmd --reload",
                f"install -d -m 755 {KEEP.parent}",
                f"echo /etc/firewalld/zones/trusted.xml > {KEEP}"]

    def reinstall(self, opts: Options, want_trust: bool) -> None:
        require_commands("curl", "sudo")
        info = json.loads(fetch_text(f"{PKGS}/?mode=json"))
        tarball = info.get("Tarballs", {}).get("arm64")
        if not tarball:
            raise Error(f"could not determine the arm64 tarball from {PKGS}/?mode=json")
        cmdline.say("download", tarball)
        with TempDir() as tmp:
            path = tmp / tarball
            fetch(opts, f"{PKGS}/{tarball}", path)
            expected = fetch_text(f"{PKGS}/{tarball}.sha256").split()[0]
            actual = sha256_of(path)
            if actual != expected:
                raise Error(f"SHA-256 mismatch (expected {expected}, got {actual})")
            cmdline.say("verify", f"sha256 OK: {actual}")
            with tarfile.open(path) as tar:
                tar.extractall(tmp, filter="data")
            src = next((p for p in tmp.iterdir() if p.is_dir() and p.name.startswith("tailscale_")), None)
            if not src or not (src / "tailscale").exists() or not (src / "tailscaled").exists():
                raise Error("unexpected tarball layout")
            unit = tmp / "tailscaled.service"
            unit.write_text(UNIT_TEXT)
            steps = [
                f"install -d -o root -g root -m 755 {PREFIX} {BIN}",
                f"install -d -o root -g root -m 700 {STATE}",
                f"install -o root -g root -m 755 {shlex.quote(str(src / 'tailscale'))} "
                f"{shlex.quote(str(src / 'tailscaled'))} {BIN}/",
                f"install -o root -g root -m 644 {shlex.quote(str(unit))} {UNIT}",
                "systemctl daemon-reload",
                "systemctl enable tailscaled",
                "systemctl restart tailscaled",
            ]
            if want_trust:
                steps += self.trust_steps()
            cmdline.say("install", f"{BIN}/tailscale, {BIN}/tailscaled, {UNIT} (sudo)")
            cmdline.run(opts, ["sudo", "sh", "-euc", "\n".join(steps)], capture=False)
        version = cmdline.output(opts, [str(BIN / "tailscale"), "version"], default="?") or "?"
        cmdline.say("installed", f"tailscale {version.splitlines()[0]}")

    def report_login(self, opts: Options) -> None:
        if not os.access(BIN / "tailscale", os.X_OK) or not systemctl(opts, "is-active", "--quiet", "tailscaled"):
            return
        backend = backend_state(opts)
        if backend == "Running":
            cmdline.say("ok", f"tailscale login ({tailnet_ip(opts)})")
        else:
            user = pwd.getpwuid(os.getuid()).pw_name
            cmdline.say("missing", f"tailscale login ({backend}): sudo {BIN}/tailscale up --qr --operator={user} --ssh")

    def uninstall(self, item: Item, opts: Options) -> bool:
        steps = ["systemctl disable --now tailscaled || true", f"rm -f {UNIT}", "systemctl daemon-reload",
                 f"rm -rf {PREFIX}"]
        if KEEP.exists():
            steps += ["firewall-cmd --permanent --zone=trusted --remove-interface=tailscale0 || true",
                      "firewall-cmd --reload || true", f"rm -f {KEEP}"]
        cmdline.say("would remove" if opts.check else "remove",
                    f"tailscaled, {PREFIX} (the login state too) and the unit, with sudo")
        if opts.check or not cmdline.confirm(opts, "remove Tailscale?", False):
            return opts.check
        cmdline.run(opts, ["sudo", "sh", "-euc", "\n".join(steps)], capture=False)
        return True
