## Tailscale

`cjf install tailscale [--trust]` installs or updates Tailscale as a
native system service, using kernel TUN rather than userspace or proxy
mode; the download and its check run as you, one sudo installs. The
`tailscale` alias comes with the shell init. Then:

```bash
sudo /home/.tailscale/bin/tailscale up --qr --operator=steamos --ssh
```

`--qr` prints a login QR code to scan with a phone. `--operator=steamos`
lets that user run `tailscale` without sudo. Re-running the script
updates to the latest stable build and keeps the login.

### Why it installs under `/home/.tailscale`

The home partition is the only storage that persists across updates:

| Mount | Partition | Survives an update? |
|---|---|---|
| `/` | `rootfs-A`/`rootfs-B`, btrfs | No: it's read-only (`btrfs property get / ro` gives `ro=true`) and replaced from the image. `findmnt` still says `rw`. |
| `/var` | `var-A`/`var-B`, 256 MB ext4 | No: each slot has its own copy. It's also too small for the roughly 70 MB of binaries. |
| `/etc` | overlay, with its upper layer in `/var/lib/overlays/etc/upper` | Only the paths in the update keep list (below) |
| `/home` | `home`, ext4 | Yes. SteamOS keeps its own persistent data there too (`/home/.steamos/offload`) |

The directory is `/home/.tailscale`, owned by root, and not somewhere
under `~`. `tailscaled` runs as root, and any process running as your
user can rename things inside `~` (which you own), so it could swap the
binary out. `/home` itself is owned by root.

The deck-tailscale script from Tailscale's team, and forks of it,
install to `/opt`, which is on the read-only root. On the Frame they
fail with `Read-only file system` (tailscale-dev/deck-tailscale#71).

### What survives an update

`/usr/lib/rauc/atomic-update-keep.conf` already keeps
`/etc/systemd/system/*.service`, `*.wants/**`, `*.service.d/**` and
`/etc/atomic-update.conf.d/*.conf`. That covers the unit and its enable
symlink, so they need no drop-in of their own. `/etc/firewalld/` is
**not** on the list, which is why `--trust-tailnet` adds one.

`/etc/profile.d` isn't on the keep list either, so the `tailscale`
command comes from the shell init instead (see [Shell
init](shell-init.md#shell-init)).

### Firewall

- **firewalld is running,** and its default `public` zone allows only
  `ssh` and `dhcpv6-client`. Without `--trust-tailnet`, only SSH is
  reachable over the tailnet. `--trust-tailnet` puts `tailscale0` in the
  `trusted` zone and leaves access control to the Tailscale ACLs.
- **`/usr/bin/iptables` is the legacy backend,** but the kernel has no
  `ip_tables` module. Left to auto-detect, tailscaled fails to install
  its `ts-*` rules; the health check reports `modprobe: FATAL: Module
  ip_tables not found`. The unit sets `TS_DEBUG_FIREWALL_MODE=nftables`,
  and `CONFIG_NF_TABLES=y` supports it (firewalld already uses
  nftables).

### Checking it

Run these on the Frame; none needs sudo:

```bash
systemctl is-enabled tailscaled && tailscale status
```

```bash
tailscale status --json | jq -c '{BackendState, Health}'
```

```bash
tailscale ping <peer>
```

- **`tailscale status --json`** should report `Running` and an empty
  `Health` list.
- **`tailscale ping`** should answer from a LAN address, not through a
  DERP relay.
- **After the first SteamOS update, re-run the first command.** If the
  unit is gone, re-running the script restores it, and the login in
  `/home/.tailscale/state` is kept.

Disable key expiry for the Frame in the admin console. Otherwise it
drops off the tailnet when the key expires, after about 180 days.

### Uninstall

The steps are in the script's header comment.
