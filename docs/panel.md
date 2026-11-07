# A SteamVR panel of any size: `cjf panel` and the gamescope-panel package

`cjf panel start --size 3840x1080 -- COMMAND` runs an app in a SteamVR
panel of its own, with a screen of exactly that size. Written for KRDC
showing a PC's two 1920x1080 monitors side by side, pixel for pixel; it
runs any app. It needs `cjf install gamescope-panel` first (about ten
minutes on the Frame) and SteamVR up, which Game Mode is.

## Why Game Mode's own gamescope can't

Game Mode is one gamescope (`/usr/lib/steamos/gamescope-session`) on
its OpenVR backend, drawing every app into one 1920x1080 overlay:
`--output-width 1920 --output-height 1080`, in the read-only image,
with no override. An app's own screen size is a separate matter: the
default is 1280x720 (`--nested-width`), Steam's per-game Game
Resolution changes it, and `--virtual-connector-strategy PerAppId`
gives each app ID its own, so a non-Steam shortcut can have a
3840x1080 screen. But whatever its size, the result is scaled to fit
the 1080p overlay: 3840x1080 arrives as 1920x540 with black bars.

Frametop sidesteps this with its own compositor, ft-screens, which
gives each Plasma screen any size as its own overlay. A panel does the
same with much less: a second gamescope on the OpenVR backend, one app
inside, at the size asked for. Frametop's first version did exactly
that (its gamescope backend, still in its session script) and found
the one thing in the way.

## The one thing in the way, and the patch

Checked on 2026-11-07 (SteamOS 0.5.8, gamescope 3.16.30), with a second
gamescope started through the user manager beside Game Mode:

| `gamescope --backend openvr -W ... -H ...` | result |
|---|---|
| 1920x1080 | starts and runs |
| 2560x1440 | aborts at start |
| 3840x1080 | aborts at start |

The abort is an assertion in gamescope's Vulkan code: `uploadBufferData`
in `src/rendervulkan.hpp`, whose scratch buffer is `1920 * 1080 * 4`
bytes, a constant. When the OpenVR backend starts it makes a flat
black texture the size of its output as the backing behind the app
(`m_pBlackTexture` in `src/Backends/OpenVRBackend.cpp`), and
`vulkan_create_flat_texture` fills it through that buffer, so any output
over 1080p's worth of pixels overflows it. Nothing else in gamescope
sizes an upload by the output; frames reach SteamVR as Vulkan
textures, with no size limit.

`flat-texture-clear.patch` makes `vulkan_create_flat_texture` clear the
texture on the GPU (`vkCmdClearColorImage`, which gamescope already
loads for its ReShade path) instead of filling it from the buffer. A
new `CVulkanCmdBuffer::clearImage` does the clear with the same
barrier and dirty bookkeeping as `copyBufferToImage`. Twenty-six
lines, no behaviour change for sizes that fit.

## The package

`cjf install gamescope-panel` builds gamescope 3.16.30 from the kit's
PKGBUILD (`src/curiousj_framekit/data/pkgbuilds/gamescope-panel/`), the
same release as the host's package and, by its option set, the same
source: the tag's commit from GitHub, the seven submodules it records
(wlroots, libliftoff, vkroots, openvr, libdisplay-info, reshade,
SPIRV-Headers) as git sources pinned to those commits, glm and stb
fetched by meson at the revisions gamescope's wrap files pin. Every
other library is the host's, which has them all with headers; so are
meson, ninja, glslang and cmake. The Vulkan layer isn't built (the
host's serves this gamescope too), nor the tests and the benchmark.

It installs under `~/.local/lib/gamescope-panel` as a `pacman-home`
package, with `~/.local/bin/gamescope-panel` to run the binary from a
shell. `gamescope` on PATH stays the host's. `cjf installed` reports it
and `cjf update` rebuilds it after a SteamOS update that breaks a
library it links, as with the other home packages
([home-packages.md](home-packages.md)).

## How a panel runs

`cjf panel start` runs the kit's gamescope with `--backend openvr`, the
output and nested sizes both set to `--size`, an overlay key and name
from `--name` (default the command's name), the physical width from
`--width` (default a panel 1.5 m tall, so 2.67 m for 16:9, which is the
session's own, and 5.33 m for 3840x1080), SteamVR's control bar with
its keyboard and close buttons, and the host's cursor image. The app is
the child, as in Game Mode.

It starts as a transient user service, `cjf-panel-NAME`, through
`systemd-run --user`, for two reasons: the user manager's environment
has what the OpenVR runtime needs to find SteamVR (a shell over SSH
does not, and the session gamescope's environment isn't readable), and
the panel then outlives the terminal that started it. `status` lists
the panels, `log` reads a panel's journal. The command is resolved on
the calling shell's PATH, since the service's is the system's;
`~/.local/bin/krdc` is found that way.

Ending a panel took a workaround. gamescope on the OpenVR backend
keeps running after its child exits (it logs "Primary child shut
down!" and stays, with the host's binary as with the kit's) and
ignores SIGTERM and SIGINT, before and after. So the app runs under a
shell that stops the unit when the app exits, and the unit has a stop
timeout of three seconds: a stop, from that shell or from `cjf panel
stop`, sends SIGTERM, which ends the app, and SIGKILL three seconds
later, which is what ends gamescope. Nothing in a compositor overlay
needs a graceful exit.

The app sees X11 through gamescope's Xwayland. Qt apps get
`QT_QPA_PLATFORM=xcb`, the path gamescope is built around; `--wayland`
offers xdg-shell instead (`--expose-wayland`) and leaves Qt alone.
`XCURSOR_SIZE=32` replaces the session's 256, which would cover a good
part of the panel; `--env` adds or overrides variables.

## Limits

- One size for every window in a panel: a second app wants a second
  panel. `--fullscreen` makes every window that size, dialogs included,
  so it is for apps that open none.
- SteamVR's dashboard owns the panel's placement: grab its bar to move
  it. No curving, pinning or saved layout as in Frametop.
- A wide panel is a wide object: 3840x1080 at 1.5 m tall is 5.33 m
  wide. Frametop's notes put a 5120x1440 remote display at about 51
  pixels per degree when it spans 100 degrees, which read as too small;
  sit a wide panel close, or give `--width` less and accept the pixels
  go unseen.

## KRDC at a PC's two monitors

```sh
cjf panel start --size 3840x1080 --fullscreen -- krdc --fullscreen rdp://HOST
```

With Resolution set to "Match screen" in KRDC's settings for that host,
it asks the server for 3840x1080, which KRdp on the PC serves as its
two monitors side by side ([apps.md](apps.md#apps)); each remote pixel
is one panel pixel. KRDC's `--fullscreen` wants exactly one URL.
