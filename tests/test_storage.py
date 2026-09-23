import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from confissh.core import ConfigDocument, ConfigError
from confissh.storage import MetadataStore, atomic_write, encode, new_id


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = root / "config"
        self.original = "Host api\n  HostName localhost\n  User deploy\n  # keep this comment\n"
        self.config.write_text(self.original)
        self.documents = {self.config: ConfigDocument.load(self.config)}
        self.store = MetadataStore(root / "app" / "connections.json")
        self.store.synchronize(self.documents)
        self.id = self.documents[self.config].entries[0].connection_id

    def test_registration_only_inserts_key_and_is_idempotent(self):
        UUID(self.id)
        self.assertEqual(self.config.read_text(), f"# confissh-key: {self.id}\n" + self.original)
        snapshot = json.loads(next(self.store.backup_dir.glob("*.json")).read_text())
        self.assertEqual(snapshot["documents"][str(self.config)], self.original)
        before = self.config.read_bytes()
        backups = list(self.store.backup_dir.glob("*.json"))
        self.store.synchronize(self.documents)
        self.assertEqual(before, self.config.read_bytes())
        self.assertEqual(backups, list(self.store.backup_dir.glob("*.json")))
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)

    def test_delete_selected_and_all_backups_preserves_live_files(self):
        first = self.store.list_backups()[0]
        data = copy.deepcopy(self.store.data)
        data["connections"][self.id]["note"] = "new note"
        self.store.commit(data, self.documents)
        before = self.config.read_bytes(), self.store.path.read_bytes()
        self.assertEqual(self.store.delete_backups([first]), 1)
        self.assertFalse(first.exists())
        self.assertEqual(len(self.store.list_backups()), 1)
        self.assertEqual(self.store.delete_backups(self.store.list_backups()), 1)
        self.assertEqual(self.store.list_backups(), [])
        self.assertEqual(before, (self.config.read_bytes(), self.store.path.read_bytes()))
        data["connections"][self.id]["note"] = "another note"
        self.store.commit(data, self.documents)
        self.assertEqual(len(self.store.list_backups()), 1)

    def test_delete_backups_rejects_foreign_symlink_and_stale_paths(self):
        first = self.store.list_backups()[0]
        link = self.store.backup_dir / "link.json"
        link.symlink_to(self.store.path)
        for path in (self.store.path, self.config, link, self.store.backup_dir / "missing.json"):
            with self.assertRaises(ConfigError):
                self.store.delete_backups([first, path])
            self.assertTrue(first.exists())
        self.assertNotIn(link, self.store.list_backups())
        atomic_write(self.store.pending, encode({"files": []}))
        with self.assertRaises(ConfigError):
            self.store.delete_backups([first])
        self.assertTrue(first.exists())

    def test_delete_backup_failure_reports_partial_progress(self):
        first = self.store.list_backups()[0]
        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(ConfigError, "0 backups were deleted"):
                self.store.delete_backups([first])
        self.assertTrue(first.exists())

    def test_group_color_survives_rename_and_can_be_cleared(self):
        data = copy.deepcopy(self.store.data)
        key = self.store.save_group(data, None, "Colored", "#AA33CC")
        self.store.save_group(data, key, "Renamed")
        self.assertEqual(data["groups"][key]["color"], "#aa33cc")
        self.store.commit(data, self.documents)
        self.assertEqual(MetadataStore(self.store.path).data["groups"][key]["color"], "#aa33cc")
        with self.assertRaises(ConfigError):
            self.store.save_group(data, key, "Renamed", "not a color")
        self.store.save_group(data, key, "Renamed", "")
        self.assertNotIn("color", data["groups"][key])

    def test_first_run_seeds_environments_without_assigning_hosts(self):
        environments = self.store.data["environments"]
        self.assertEqual({item["name"] for item in environments.values()},
                         {"Production", "Sandbox", "Development"})
        self.assertEqual(len({item["color"] for item in environments.values()}), 3)
        for key in environments:
            UUID(key)
        self.assertIsNone(self.store.data["connections"][self.id]["environment_id"])
        self.assertEqual(MetadataStore(self.store.path).data["environments"], environments)

    def test_default_environment_edits_and_deletions_survive_reload(self):
        data = copy.deepcopy(self.store.data)
        key = next(iter(data["environments"]))
        data["environments"] = {key: {"name": "Custom", "color": "#123456"}}
        self.store.commit(data, self.documents)
        self.assertEqual(MetadataStore(self.store.path).data["environments"], data["environments"])
        data["environments"] = {}
        self.store.commit(data, self.documents)
        reloaded = MetadataStore(self.store.path)
        reloaded.synchronize(self.documents)
        self.assertEqual(reloaded.data["environments"], {})

    def test_restore_defaults_preserves_ids_assignments_and_custom_environments(self):
        data = copy.deepcopy(self.store.data)
        ids = {item["name"]: key for key, item in data["environments"].items()}
        production = ids["Production"]
        data["environments"][production] = {"name": "production", "color": "#123456"}
        del data["environments"][ids["Sandbox"]]
        data["environments"][ids["Development"]]["name"] = "Local"
        data["connections"][self.id]["environment_id"] = production
        records = copy.deepcopy(data["connections"])
        custom = copy.deepcopy(data["environments"][ids["Development"]])
        ssh_before = self.config.read_bytes()
        self.store.restore_default_environments(data)
        self.assertEqual(data["environments"][production], {"name": "Production", "color": "#dc5454"})
        self.assertEqual(data["environments"][ids["Development"]], custom)
        self.assertEqual({item["name"] for item in data["environments"].values()},
                         {"Production", "Sandbox", "Development", "Local"})
        self.assertEqual(data["connections"], records)
        restored = copy.deepcopy(data)
        self.store.restore_default_environments(data)
        self.assertEqual(data, restored)
        self.store.commit(data, self.documents)
        self.assertEqual(MetadataStore(self.store.path).data, restored)
        self.assertEqual(self.config.read_bytes(), ssh_before)

    def test_restore_defaults_into_empty_environments(self):
        data = copy.deepcopy(self.store.data)
        data["environments"] = {}
        self.store.restore_default_environments(data)
        self.assertEqual(len(data["environments"]), 3)
        self.store.validate(data)

    def test_empty_metadata_file_is_not_treated_as_first_run(self):
        self.store.path.write_bytes(b"")
        with self.assertRaises(ConfigError):
            MetadataStore(self.store.path)
        self.assertEqual(self.store.path.read_bytes(), b"")

    def test_group_rename_delete_and_empty_groups(self):
        data = copy.deepcopy(self.store.data)
        group = self.store.save_group(data, None, "Production")
        empty = self.store.save_group(data, None, "Empty")
        data["connections"][self.id]["group_id"] = group
        data["connections"][self.id]["favorite"] = True
        self.store.commit(data, self.documents)
        before = self.config.read_bytes()
        records = copy.deepcopy(data["connections"])
        self.store.save_group(data, group, "Operations")
        self.assertEqual(records, data["connections"])
        self.store.commit(data, self.documents)
        self.assertEqual(self.documents[self.config].entries[0].group, "Operations")
        self.assertEqual(before, self.config.read_bytes())
        self.assertIn(empty, MetadataStore(self.store.path).data["groups"])
        self.store.delete_group(data, group, empty)
        self.store.commit(data, self.documents)
        self.assertEqual(self.store.data["connections"][self.id]["group_id"], empty)
        self.store.delete_group(data, empty)
        self.store.commit(data, self.documents)
        self.assertIsNone(self.store.data["connections"][self.id]["group_id"])
        self.assertTrue(self.store.data["connections"][self.id]["favorite"])
        with self.assertRaises(ConfigError):
            self.store.save_group(data, None, "")

    def test_alias_change_and_source_move_keep_metadata(self):
        data = copy.deepcopy(self.store.data)
        data["connections"][self.id].update(tags=["redis"], note="database", favorite=True)
        self.store.commit(data, self.documents)
        self.config.write_text(self.config.read_text().replace("Host api", "Host renamed"))
        docs = {self.config: ConfigDocument.load(self.config)}
        self.store.synchronize(docs)
        self.assertEqual(docs[self.config].entries[0].tags, ["redis"])
        moved = self.config.with_name("included")
        self.config.rename(moved)
        docs = {moved: ConfigDocument.load(moved)}
        self.store.synchronize(docs)
        self.assertEqual(docs[moved].entries[0].connection_id, self.id)
        self.assertTrue(self.store.data["connections"][self.id]["favorite"])

    def test_duplicate_key_gets_distinct_id(self):
        text = self.config.read_text()
        self.config.write_text(text + "\n" + text.replace("Host api", "Host copy"))
        docs = {self.config: ConfigDocument.load(self.config)}
        self.store.synchronize(docs)
        ids = [e.connection_id for e in docs[self.config].entries]
        self.assertEqual(len(set(ids)), 2)
        self.assertIn(self.id, ids)
        self.assertEqual(ids[0], self.id)

    def test_metadata_edit_does_not_reformat_ssh_body(self):
        document = self.documents[self.config]
        before = document.as_text()
        entry = copy.deepcopy(document.entries[0])
        entry.tags = ["redis"]
        entry.note = "note"
        document.replace(document.entries[0], entry)
        self.assertEqual(before, document.as_text())
        data = copy.deepcopy(self.store.data)
        data["connections"][entry.connection_id] = self.store.record(entry)
        self.store.commit(data, self.documents)
        self.assertEqual(before, self.config.read_text())
        self.assertEqual(document.entries[0].tags, ["redis"])

    def test_recovery_refuses_foreign_changes(self):
        before = self.config.read_text()
        atomic_write(self.store.pending, encode({"files": [
            {"path": str(self.config), "before": before, "after": before + "# pending\n"}]}))
        self.config.write_text(before + "# external\n")
        with self.assertRaises(ConfigError):
            MetadataStore(self.store.path)
        self.assertTrue(self.store.pending.exists())
        self.assertTrue(self.config.read_text().endswith("# external\n"))

    def test_conflicts_do_not_overwrite(self):
        before = self.store.path.read_bytes()
        self.config.write_text("# external\n" + self.config.read_text())
        with self.assertRaises(ConfigError):
            self.store.commit(copy.deepcopy(self.store.data), self.documents)
        self.assertEqual(before, self.store.path.read_bytes())
        self.documents[self.config] = ConfigDocument.load(self.config)
        atomic_write(self.store.path, before + b" ")
        with self.assertRaises(ConfigError):
            self.store.commit(copy.deepcopy(self.store.data), self.documents)

    def test_failed_pair_write_rolls_back(self):
        before = self.config.read_bytes(), self.store.path.read_bytes()
        candidate = copy.deepcopy(self.documents[self.config])
        entry = copy.deepcopy(candidate.entries[0])
        entry.aliases = ["changed"]
        candidate.replace(candidate.entries[0], entry)
        data = copy.deepcopy(self.store.data)
        data["connections"][self.id]["tags"] = ["redis"]
        failed = False
        def fail_metadata_once(path, content):
            nonlocal failed
            if path == self.store.path and not failed:
                failed = True
                raise OSError("injected failure")
            atomic_write(path, content)
        with patch("confissh.storage.atomic_write", side_effect=fail_metadata_once):
            with self.assertRaises(ConfigError):
                self.store.commit(data, {self.config: candidate})
        self.assertEqual(before, (self.config.read_bytes(), self.store.path.read_bytes()))
        self.assertFalse(self.store.pending.exists())

    def test_recover_interrupted_write(self):
        before = self.config.read_text()
        after = before.replace("api", "partial")
        atomic_write(self.store.pending, encode({"files": [
            {"path": str(self.config), "before": before, "after": after}]}))
        self.config.write_text(after)
        MetadataStore(self.store.path)
        self.assertEqual(before, self.config.read_text())

    def test_corrupt_metadata_is_not_reset(self):
        self.store.path.write_text('{"version": 99}')
        with self.assertRaises(ConfigError):
            MetadataStore(self.store.path)
        self.assertEqual(self.store.path.read_text(), '{"version": 99}')
