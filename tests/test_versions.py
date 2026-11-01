import tempfile
import time
import unittest
from pathlib import Path

from curiousj_framekit.frame import versions

# As read on the Frame, 2026-10-31 (SteamOS 0.5.6, beta channel).
OS_RELEASE = {"VERSION_ID": "0.5.6", "BUILD_ID": "20261022.6153909"}
VERSION_TXT = "1791331621\r\n"
BETA = "linux_arm64_beta_861407927dc8efb407da7cf"
MANIFEST = ('"linuxarm64"\n{\n\t"version"\t\t"1792099137"\n\t"tenfoot_images_all"\n\t{\n'
            '\t\t"file"\t\t"tenfoot_images_all.zip.86419c7a56c12dd107b5e0d46f50c8a9b121f3cc"\n'
            "\t}\n}\n")
VRSERVER_LOG = ("Fri Oct 10 2026 ... - vrserver 2.18.1 startup with PID=100, config=x\n"
                "more lines\n"
                "Fri Oct 31 2026 ... - vrserver 2.18.2 startup with PID=2281, config=y\n")

# What bin/frame-versions printed on the Frame the same day.
EXPECTED = """\
SteamOS       0.5.6       build 20261022.6153909, beta channel
SteamVR       2.18.2      build 1791331621 (2026-10-07 00:07 UTC)
Steam client  1792099137  built 2026-10-15 21:18 UTC, beta channel"""


class When(unittest.TestCase):
    def test_utc_date(self):
        self.assertEqual(versions.when("1791331621"), "2026-10-07 00:07 UTC")
        self.assertEqual(versions.when(0), "1970-01-01 00:00 UTC")

    def test_junk_is_question_mark(self):
        self.assertEqual(versions.when("abc"), "?")
        self.assertEqual(versions.when(""), "?")


class Rows(unittest.TestCase):
    def test_same_output_as_the_script(self):
        rows = [versions.steamos_row(OS_RELEASE, "beta"),
                versions.steamvr_row("2.18.2", VERSION_TXT),
                versions.Row("Steam client", "1792099137",
                             f"built {versions.when('1792099137')}, {versions.channel_of(BETA)} channel")]
        self.assertEqual(versions.format_rows(rows), EXPECTED)

    def test_missing_pieces_are_question_marks(self):
        self.assertEqual(versions.steamos_row({}, None),
                         versions.Row("SteamOS", "?", "build ?, ? channel"))
        self.assertEqual(versions.steamvr_row(None, None, Path("/opt/steamvr")),
                         versions.Row("SteamVR", "?", "no /opt/steamvr/bin/version.txt"))


class SteamVR(unittest.TestCase):
    def test_log_fallback_takes_the_last_startup(self):
        self.assertEqual(versions.vrserver_log_version(VRSERVER_LOG), "2.18.2")
        self.assertIsNone(versions.vrserver_log_version("nothing here"))

    def test_crlf_does_not_leak_into_the_row(self):
        row = versions.steamvr_row("2.18.2", VERSION_TXT)
        self.assertNotIn("\r", row.detail)
        self.assertEqual(row.detail, "build 1791331621 (2026-10-07 00:07 UTC)")


class SteamClient(unittest.TestCase):
    def test_channel_names(self):
        self.assertEqual(versions.channel_of(BETA), "beta")
        self.assertEqual(versions.channel_of(""), "stable")
        self.assertEqual(versions.channel_of("linux_arm64_publicbeta_0123456789abcdef0\n"), "publicbeta")

    def test_manifest_version(self):
        self.assertEqual(versions.manifest_version(MANIFEST), "1792099137")
        self.assertIsNone(versions.manifest_version('\t"file"\t\t"x"\n'))

    def test_manifest_named_after_the_channel(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            (pkg / "beta").write_text(BETA + "\n")
            named = pkg / f"steam_client_{BETA}_linuxarm64.manifest"
            named.write_text(MANIFEST)
            (pkg / "steam_client_linuxarm64.manifest").write_text(MANIFEST.replace("1792099137", "1"))
            manifest, beta = versions.client_manifest(pkg)
            self.assertEqual(manifest, named)
            self.assertEqual(beta, BETA)
            self.assertEqual(versions.steam_client_row(pkg).version, "1792099137")

    def test_stable_and_newest_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            old = pkg / "steam_client_old_linuxarm64.manifest"
            new = pkg / "steam_client_new_linuxarm64.manifest"
            old.write_text(MANIFEST.replace("1792099137", "1"))
            new.write_text(MANIFEST)
            now = time.time()
            import os
            os.utime(old, (now - 100, now - 100))
            os.utime(new, (now, now))
            manifest, beta = versions.client_manifest(pkg)
            self.assertEqual(manifest, new)
            self.assertEqual(beta, "")
            row = versions.steam_client_row(pkg)
            self.assertEqual(row.detail, "built 2026-10-15 21:18 UTC, stable channel")

    def test_no_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            row = versions.steam_client_row(Path(d))
            self.assertEqual(row.version, "?")
            self.assertTrue(row.detail.startswith("no client manifest under "))
