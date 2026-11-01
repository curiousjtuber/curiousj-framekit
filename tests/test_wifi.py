import unittest

from curiousj_framekit.frame import wifi


class Parsing(unittest.TestCase):
    def test_wireless_uuids(self):
        text = ("1111:802-11-wireless\n2222:802-3-ethernet\n"
                "3333:802-11-wireless\n4444:bridge\n")
        self.assertEqual(wifi.wireless_uuids(text), ["1111", "3333"])

    def test_sightings_strongest_and_in_use(self):
        text = ("*:84:home-5g\n :61:home\n :40:neighbour-guest\n :70:home\n"
                " :50:odd\\:name\n :: \n")
        signal, inuse = wifi.sightings(text)
        self.assertEqual(signal, {"home-5g": 84, "home": 70, "neighbour-guest": 40, "odd:name": 50})
        self.assertEqual(inuse, {"home-5g"})

    def test_unescape(self):
        self.assertEqual(wifi.unescape(r"a\:b\\c"), r"a:b\c")


class Rows(unittest.TestCase):
    saved = {"home-5g": "home-5g", "home": "Home 2.4", "office": "office"}
    signal = {"home-5g": 84, "home": 61}
    inuse = {"home-5g"}

    def test_in_range_strongest_first(self):
        self.assertEqual(wifi.rows(self.saved, self.signal, self.inuse, False),
                         [" 84 * home-5g", " 61   home  (Home 2.4)"])

    def test_all_puts_out_of_range_last(self):
        self.assertEqual(wifi.rows(self.saved, self.signal, self.inuse, True)[-1],
                         "      office")
