import json
import struct
import unittest

from curiousj_framekit.frame import steam


def unframe(data: bytes) -> bytes:
    b1 = data[1]
    n = b1 & 0x7F
    pos = 2
    if n == 126:
        n = struct.unpack(">H", data[2:4])[0]
        pos = 4
    elif n == 127:
        n = struct.unpack(">Q", data[2:10])[0]
        pos = 10
    mask = data[pos:pos + 4]
    payload = data[pos + 4:pos + 4 + n]
    return bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class Frame(unittest.TestCase):
    def test_short_and_long_payloads_roundtrip(self):
        for size in (5, 125, 126, 300, 70000):
            payload = bytes(range(256)) * (size // 256 + 1)
            payload = payload[:size]
            framed = steam.frame(payload)
            self.assertEqual(framed[0], 0x81)
            self.assertTrue(framed[1] & 0x80)
            self.assertEqual(unframe(framed), payload)


class Script(unittest.TestCase):
    def test_read_only_and_set(self):
        js = steam.LAUNCH_OPTIONS_JS % (620980, json.dumps(None), "false")
        self.assertIn("const id = 620980, hook = null", js)
        js = steam.LAUNCH_OPTIONS_JS % (620980, json.dumps("a; %command%; b"), "false")
        self.assertIn('hook = "a; %command%; b"', js)
