import copy
import tempfile
import unittest
from pathlib import Path

from confissh.core import ConfigDocument, ConfigError, included_paths, parse_tags
from confissh.storage import MetadataStore


class WorkflowTests(unittest.TestCase):
    def test_tags_round_trip_edit_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            path.write_text("# Host data\n# HostName localhost\n")
            documents = {path: ConfigDocument.load(path)}
            store = MetadataStore(Path(directory) / "connections.json")
            store.synchronize(documents)
            entry = documents[path].entries[0]
            data = copy.deepcopy(store.data)
            data["connections"][entry.connection_id]["tags"] = parse_tags("redis, PostgreSQL, izleme, REDIS")
            store.commit(data, documents)
            loaded = ConfigDocument.load(path)
            MetadataStore(store.path).hydrate(loaded)
            self.assertEqual(loaded.entries[0].tags, ["redis", "PostgreSQL", "izleme"])
            self.assertFalse(loaded.entries[0].enabled)
            data["connections"][entry.connection_id]["tags"] = []
            store.commit(data, documents)
            self.assertEqual(documents[path].entries[0].tags, [])
            self.assertNotIn("redis", path.read_text())

    def test_tags_reject_line_injection(self):
        with self.assertRaises(ConfigError):
            parse_tags("redis\nHost injected")

    def test_external_edit_blocks_stale_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            path.write_text("Host api\n  HostName old\n")
            document = ConfigDocument.load(path)
            candidate = copy.deepcopy(document)
            candidate.entries[0].environment = "Production"
            candidate.replace(candidate.entries[0], copy.deepcopy(candidate.entries[0]))
            path.write_text("Host api\n  HostName external\n")
            self.assertTrue(document.changed_on_disk())
            with self.assertRaises(ConfigError):
                candidate.save()
            self.assertIn("external", path.read_text())

    def test_ssh_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            original = "Host api\n  HostName old\n"
            path.write_text(original)
            document = ConfigDocument.load(path)
            entry = copy.deepcopy(document.entries[0])
            entry.aliases = ["updated"]
            document.replace(document.entries[0], entry)
            document.save()
            self.assertEqual(ConfigDocument.load(path).entries[0].alias, "updated")
            backup = document.backups()[0]
            candidate = ConfigDocument(backup.read_text(), path)
            candidate.save()
            self.assertEqual(path.read_text(), original)
            self.assertEqual(len(document.backups()), 2)

    def test_include_glob_and_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "config"
            child = Path(directory) / "prod.conf"
            root.write_text(f'Include "{directory}/*.conf"\nHost local\n HostName localhost\n')
            child.write_text(f'Include "{root}"\nHost prod\n HostName example.com\n')
            self.assertEqual(included_paths(root), [root, child])

    def test_match_and_blank_lines_preserved(self):
        text = "Host api\n HostName=example.com\n\n User deploy\nMatch host other\n User root\n"
        doc = ConfigDocument(text)
        old = doc.entries[0]
        self.assertEqual(old.get("user"), "deploy")
        entry = copy.deepcopy(old)
        entry.environment = "Development"
        doc.replace(old, entry)
        self.assertIn("Match host other\n User root", doc.as_text())
        self.assertEqual(doc.entries[0].get("hostname"), "example.com")
