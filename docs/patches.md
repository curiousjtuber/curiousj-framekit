# The kit's patches and their upstreams

Every patch the kit applies to someone else's source, what applies it,
and where it stands with the project it changes. Each patch file opens
with its own account of the bug or the feature and how it was measured;
this page is the index and the state, as of 2026-11-14. A line here
that disagrees with upstream is out of date: check upstream, then fix
the line.

The patches are of three kinds, and the kind says what happens to one
at the next version bump:

- **ours, not upstream**: written here, upstream lacks it. It stays
  until upstream takes it, and is worth sending.
- **ours, upstream since**: written here, and upstream has the change
  now, merged from here or made there on its own. It goes when the
  version built has it.
- **backport**: upstream's own commit, carried because the version
  built here is older than the fix. It goes when the version built
  has it.

## Being sent upstream

In the order they depend on each other. One has been through already:
KPipeWire's cursor bitmap size, sent as
[!285](https://invent.kde.org/plasma/kpipewire/-/merge_requests/285)
and merged 2026-10-13 as `d5dbf359`: in 6.8.1, 6.7.6 and 6.6.7, the
last being what the `krdpserver` package builds, so the kit no longer
carries the patch.

| Patch | To | State |
|---|---|---|
| `krdp-pointer-cache-check.patch` | KRdp, `plasma/krdp` on invent.kde.org | [!292](https://invent.kde.org/plasma/krdp/-/merge_requests/292), opened 2026-11-14 from branch `pointer-cache-check` of the fork `curiousj/krdp`, against master `8d8e084`; CI passed, no review yet |
| `krdp-embed-cursor.patch` | KRdp | not sent; waits for the one above, which it applies on top of. Made against 6.8.2, so it needs a rebase to master. Open merge requests that touch the same ground: !184 (cursor position updates, a draft) and !290 (drops `PlasmaScreencastV1Session`, a file this patch edits) |
| `krdc-embed-cursor.patch` | KRDC, `network/krdc` | not sent; pointless until a KRdp with the feature exists, since stock KRdp refuses or crashes on the client it makes. Made against 26.08.2 |
| `freerdp-h264-v4l2m2m.patch` | FreeRDP, on GitHub | [#14183](https://github.com/FreeRDP/FreeRDP/pull/14183), opened 2026-11-14 from branch `h264-v4l2m2m` of the fork `curiousjtuber/FreeRDP`; independent of the others. Reworked 2026-11-15 at the maintainer's request, and its fallback hardened 2026-11-17 after a review of our own; the branch is at `a4886d674`, on master `4f4bd4c75`, awaiting review. That version is not the kit's, which is for 3.33.1 and decodes on a path of its own: upstream's tries the decoder where the codec is chosen, at the context's size, converts the frame with the swscale code already there, and is compiled under `WITH_FFMPEG_HWACCEL` with `useHwDecoder` as its switch. Under that option FreeRDP asks for hardware decoding only from a client that turns `FreeRDP_SoftwareGdi` off, which KRDC does not, so the kit taking upstream's version means a change to KRDC as well |

## Every patch

Paths are under `src/curiousj_framekit/data/` unless they start with
`pc/`. A patch named twice is one file and a symlink to it. The `krdp`
Flatpak and its two patches left the kit on 2026-11-14.

### KRdp (the RDP server)

| Patch | Applied by | Kind | Upstream |
|---|---|---|---|
| `pc/krdpserver-embed-cursor/krdp-pointer-cache-check.patch` | the PC's `krdp-embed-cursor.sh`, on the host's Plasma release | ours, not upstream | being sent, see above |
| `pc/krdpserver-embed-cursor/krdp-embed-cursor.patch` | the same script, after the check | ours, not upstream | to send next |
| `pkgbuilds/krdpserver/krdp-ext-security.patch` | `krdpserver` package, krdp 6.6.7 | backport | one line of `f868133` (Plasma/6.8 as `31824f9`); in 6.8 |
| `pkgbuilds/krdpserver/krdp-plasma-stream.patch` | `krdpserver` package | backport, rebased | `429f584c`, not in the 6.6 releases, with the server side upstream changed separately |

### KRDC (the RDP and VNC client)

All in `pkgbuilds/krdc/`, applied by the `krdc` package to KRDC
26.08.3. The three that upstream has are all in `v26.11.80`, the 26.12
pre-release, so the bump to 26.12 drops them together.

| Patch | Kind | Upstream |
|---|---|---|
| `krdc-embed-cursor.patch` (a link to `krdc-embed-cursor/`'s, which the PC's `krdc-embed-cursor.sh` applies too) | ours, not upstream | to send after KRdp's |
| `krdc-bgrx-buffer.patch` | ours, upstream since | `69d12dc5` (2026-08-21), in 26.12 |
| `krdc-fullscreen-toolbar.patch` | ours, upstream since | `1c398732` (2026-09-23), in 26.12 |
| `krdc-clipboard-thread.patch` | backport, the thread check alone | part of `b9b97695` (2026-09-15), in 26.12 |

### FreeRDP

| Patch | Applied by | Kind | Upstream |
|---|---|---|---|
| `pkgbuilds/krdc/freerdp-h264-v4l2m2m.patch` | `krdc` package, to its own FreeRDP 3.33.1 | ours, not upstream | being sent, see above |

### gamescope

| Patch | Applied by | Kind | Upstream |
|---|---|---|---|
| `pkgbuilds/gamescope-panel/flat-texture-clear.patch` | `gamescope-panel` package, gamescope 3.16.30 | ours, upstream since | `2fbaae9b` (2026-10-23), in 3.17.0; 3.16.31 lacks it |

The package follows the host's gamescope release, so the patch goes
when SteamOS ships 3.17.

### libfuse 2

| Patch | Applied by | Kind | Upstream |
|---|---|---|---|
| `pkgbuilds/fuse2/clean-includes.patch` | `fuse2` package, 2.9.9 | backport | Arch's patch; libfuse 2 has no further releases |
| `pkgbuilds/fuse2/conditionally-define-closefrom.patch` | `fuse2` package | backport | Arch's patch, from Gentoo |

These two stay for as long as the package does.

### WayVR

| Patch | Applied by | Kind | Upstream |
|---|---|---|---|
| `pkgbuilds/wayvr/wvr-screen-res.patch` | `wayvr` package, main at `cc8843a` | ours, not upstream | not sent. Upstream asks that bug reports not be written with AI, so sending it is the user's to do |
| `pkgbuilds/wayvr/wayvr-bundled-beside-exe.patch` | `wayvr` package | ours, not upstream | not sent, as above |
| `pkgbuilds/wayvr/wayvr-anchor-before-spawn.patch` | `wayvr` package | ours, not upstream | not sent, as above; a bug fix, so the first worth reporting |

The package pins a commit of `main`, which moves daily; the patches
are small and are refreshed at each bump. A third change the kit once
carried in a hand build, for a panic opening Settings on OpenVR,
upstream fixed itself (`3e7b27f`, `75f8d4e`, 2026-11-19 and -20).

## When a version is bumped

For each patch of the package: look it up here, and if the new version
has the change, remove the file, its `source` and b2sum lines, its
`patch` line in `prepare()`, its assertion in `tests/test_kinds.py`,
and its row here. A patch that is still needed and no longer applies
is refreshed against the new source and keeps its row.

A patch left in by mistake shows itself: `patch --forward` exits
non-zero on a change that is already there, as it does on one that no
longer applies, so the build stops in `prepare()`.

## Sending one to KDE

KRdp, KPipeWire and KRDC are on invent.kde.org, where a change goes in
as a merge request from a fork.

- The work is done in a clone of upstream outside this repository
  (`~/src/krdp` for KRdp), with the fork as a second remote. The kit's
  patch file is then that commit, exported, so the two are one change.
- KDE's server refuses a commit whose author is not a full name
  ("Non-full name"). The name is set with `git config user.name` in
  that clone alone; the kit's own commits are not affected.
- The commit message is written to stand as the merge request's
  description: the cause, the fix, and how it was reproduced.
- A fix goes on its own, ahead of a feature that builds on it, which
  is why KRdp's patch is two files.
- A stable branch gets a fix by a maintainer's cherry-pick; asking for
  it in the merge request is enough.

A KRdp build is tried without touching the PC's own servers on 3389
and 3390: run from its build directory on `127.0.0.1` and another
port, with `--plasma` and a throwaway `-u`/`-p`, against FreeRDP's
sample client (`client/Sample` in its source), which has no window.
For a client without a pointer cache, both pointer cache sizes are set
to zero in the sample's `PreConnect`. Stock KRdp's crash on such a
client needs a frame that carries a cursor image, so one quiet run
proves nothing.
