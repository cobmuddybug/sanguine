import unittest

from sanguine.ui import voice


class Voice(unittest.TestCase):
    def test_labels_rename_from_level_two(self):
        self.assertEqual(voice.label("BLOOD", 1), "BLOOD")
        self.assertEqual(voice.label("BLOOD", 2), "OFFERING")
        self.assertEqual(voice.label("UNKNOWN", 5), "UNKNOWN")

    def test_line_progression(self):
        t = "You made your quota."
        self.assertEqual(voice.line(t, 0), t)
        self.assertTrue(voice.line(t, 1).startswith("[it] "))
        self.assertEqual(voice.line(t, 3), "the vessel made its quota")

    def test_tabs_lowercase_late(self):
        self.assertEqual(voice.tab("Ventures", 3), "Ventures")
        self.assertEqual(voice.tab("Ventures", 4), "ventures")


if __name__ == "__main__":
    unittest.main()
