"""Settings, and what happens to a settings file somebody has edited by hand."""

import pathlib
import tempfile
import unittest
from unittest import mock

from kota import config, i18n, paths


class Isolated(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.TemporaryDirectory()
        self.file = pathlib.Path(self.room.name) / "settings.json"
        self.patch = mock.patch.object(paths, "SETTINGS_FILE", self.file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.room.cleanup()


class Defaults(Isolated):
    def test_no_file_at_all(self):
        settings = config.load()
        self.assertEqual(settings.interval_minutes, 15)
        self.assertEqual(settings.appearance, "system")
        self.assertTrue(settings.close_to_tray)

    def test_a_round_trip(self):
        config.save(config.Settings(interval_minutes=30, warn_at=90,
                                    appearance="dark", language="tr"))
        settings = config.load()
        self.assertEqual(settings.interval_minutes, 30)
        self.assertEqual(settings.warn_at, 90)
        self.assertEqual(settings.appearance, "dark")
        self.assertEqual(settings.language, "tr")


class EditedByHand(Isolated):
    def test_a_broken_file_falls_back_rather_than_stopping(self):
        self.file.write_text("{ not json", encoding="utf-8")
        self.assertEqual(config.load().interval_minutes, 15)

    def test_a_value_of_the_wrong_type_is_ignored(self):
        paths.write_json(self.file, {"interval_minutes": "soon", "warn_at": 90})
        settings = config.load()
        self.assertEqual(settings.interval_minutes, 15)
        self.assertEqual(settings.warn_at, 90)

    def test_a_true_is_not_a_number(self):
        """bool is an int in Python, and 'interval: true' is not 1 minute."""
        paths.write_json(self.file, {"interval_minutes": True})
        self.assertEqual(config.load().interval_minutes, 15)

    def test_an_interval_nobody_offers(self):
        paths.write_json(self.file, {"interval_minutes": 7})
        self.assertEqual(config.load().interval_minutes, 15)

    def test_a_threshold_out_of_range_is_pulled_back_in(self):
        paths.write_json(self.file, {"warn_at": 400})
        self.assertEqual(config.load().warn_at, 100)
        paths.write_json(self.file, {"warn_at": -3})
        self.assertEqual(config.load().warn_at, 10)

    def test_an_appearance_that_does_not_exist(self):
        paths.write_json(self.file, {"appearance": "neon"})
        self.assertEqual(config.load().appearance, "system")

    def test_a_key_from_a_later_version(self):
        paths.write_json(self.file, {"something_new": 1, "warn_at": 70})
        self.assertEqual(config.load().warn_at, 70)


class Language(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_an_empty_setting_follows_the_desktop(self):
        with mock.patch.object(i18n, "system_language", return_value="tr"):
            self.assertEqual(config.Settings().resolved_language(), "tr")

    def test_a_chosen_language_wins(self):
        with mock.patch.object(i18n, "system_language", return_value="tr"):
            self.assertEqual(config.Settings(language="en").resolved_language(), "en")

    def test_translation_falls_back_to_the_english(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.t("Session"), "Oturum")
        self.assertEqual(i18n.t("nothing has translated this"),
                         "nothing has translated this")
        i18n.set_language("en")
        self.assertEqual(i18n.t("Session"), "Session")

    def test_a_language_nobody_speaks_here(self):
        i18n.set_language("fi")
        self.assertEqual(i18n.language(), "en")

    def test_every_turkish_format_string_takes_the_same_arguments(self):
        """A %s lost in translation is a crash at the moment it is shown."""
        for english, turkish in i18n.TURKISH.items():
            self.assertEqual(english.count("%s"), turkish.count("%s"), english)
            self.assertEqual(english.count("%d"), turkish.count("%d"), english)
            self.assertEqual(english.count("%.0f"), turkish.count("%.0f"), english)


if __name__ == "__main__":
    unittest.main()
