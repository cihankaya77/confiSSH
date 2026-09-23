import os
import stat
import tempfile
import unittest
from pathlib import Path

from confissh.core import ConfigDocument, ConfigError, HostEntry, merge_options, parse_extra_options
from confissh.i18n import _, get_language, set_language


SAMPLE = """######################################################
# GENERAL
######################################################

Host github-job
   HostName github.com
   User git
   IdentityFile ~/.ssh/id_work

######################################################
# PRODUCTION
######################################################

# Host legacy-api
#    HostName 10.0.0.4
#    Port 2202
#    User root

# confissh-key: 24e6b5d6-99c2-43dd-abcc-ad7eeef59a32
Host internal-api api-alt
  HostName 10.0.0.5
  User deploy
  ProxyJump bastion
  ### TUNNELS
  # LocalForward 5432 localhost:5432 # POSTGRES
  ServerAliveInterval 30
"""


class ConfigDocumentTests(unittest.TestCase):
    def test_parses_active_disabled_groups_and_unknown_options(self):
        doc = ConfigDocument(SAMPLE)
        self.assertEqual(len(doc.entries), 3)
        github, legacy, internal = doc.entries
        self.assertEqual(github.group, "")
        self.assertTrue(github.enabled)
        self.assertEqual(legacy.group, "")
        self.assertFalse(legacy.enabled)
        self.assertEqual(internal.aliases, ["internal-api", "api-alt"])
        self.assertEqual(internal.connection_id, "24e6b5d6-99c2-43dd-abcc-ad7eeef59a32")
        self.assertEqual(internal.get("proxyjump"), "bastion")
        rendered_extras = [option.line("") for option in internal.extra_options]
        self.assertIn("### TUNNELS", rendered_extras)
        self.assertIn("# LocalForward 5432 localhost:5432 # POSTGRES", rendered_extras)
        self.assertIn("ServerAliveInterval 30", rendered_extras)

    def test_replaces_only_selected_block(self):
        doc = ConfigDocument(SAMPLE)
        old = doc.entries[1]
        new = HostEntry(
            aliases=["legacy-api"],
            group="PRODUCTION",
            enabled=True,
            options=merge_options(
                {"hostname": "10.0.0.44", "user": "admin", "port": "22", "identityfile": "", "proxyjump": ""},
                [],
            ),
        )
        doc.replace(old, new)
        text = doc.as_text()
        self.assertIn("Host legacy-api\n  HostName 10.0.0.44", text)
        self.assertIn("Host github-job\n   HostName github.com", text)
        self.assertIn("### TUNNELS", text)

    def test_add_rejects_duplicate_and_bad_port(self):
        doc = ConfigDocument(SAMPLE)
        duplicate = HostEntry(["github-job"], merge_options({"port": "99999"}, []))
        with self.assertRaises(ConfigError) as caught:
            doc.add(duplicate)
        self.assertIn("already exists", str(caught.exception))
        self.assertIn("Port", str(caught.exception))

    def test_atomic_save_creates_private_file_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".ssh" / "config"
            doc = ConfigDocument(SAMPLE, path)
            self.assertIsNone(doc.save())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            doc.add(HostEntry(["new-host"], merge_options({"hostname": "example.com"}, []), group="TEST"))
            backup = doc.save()
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)

    def test_extra_option_validation(self):
        parsed = parse_extra_options("IdentitiesOnly yes\n# RequestTTY force\n### LABEL")
        self.assertEqual(parsed[0].key, "IdentitiesOnly")
        self.assertFalse(parsed[1].enabled)
        self.assertEqual(parsed[2].key, "")
        with self.assertRaises(ConfigError):
            parse_extra_options("broken")
        with self.assertRaises(ConfigError):
            parse_extra_options("Host nested")


class LocalizationTests(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_english_is_source_and_turkish_uses_catalog(self):
        self.assertEqual(set_language("en"), "en")
        self.assertEqual(_("Settings"), "Settings")
        self.assertEqual(set_language("tr"), "tr")
        self.assertEqual(_("Settings"), "Ayarlar")
        self.assertEqual(_("Unknown source message"), "Unknown source message")
        self.assertEqual(get_language(), "tr")


if __name__ == "__main__":
    unittest.main()
