import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from confissh.keys import discover_keys, identity_path, quote_identity_path, read_key, MAX_KEY_BYTES


class KeyTests(unittest.TestCase):
    def test_discovery_nested_keys_external_identity_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            ssh = home / '.ssh'
            nested = ssh / 'work'
            nested.mkdir(parents=True)
            private = nested / 'custom-name'
            private.write_text('-----BEGIN OPENSSH PRIVATE KEY-----\nfixture\n')
            public = Path(str(private) + '.pub')
            public.write_text('ssh-ed25519 AAAATEST user@example\n')
            (ssh / 'duplicate').symlink_to(private)
            (ssh / 'loop').symlink_to(ssh, target_is_directory=True)
            (ssh / 'broken').symlink_to(home / 'absent')
            for name in ('config', 'authorized_keys', 'known_hosts'):
                (ssh / name).write_text('ssh-ed25519 AAAATEST fixture\n')
            (ssh / 'not-a-key.pub').write_bytes(b'\xff\x00binary')
            outside = home / 'outside key.pem'
            outside.write_text('-----BEGIN ENCRYPTED PRIVATE KEY-----\nfixture\n')
            outside_pub = Path(str(outside) + '.pub')
            outside_pub.write_text('ssh-rsa AAAATEST fixture\n')
            keys, errors = discover_keys([ssh], [quote_identity_path(str(outside))])
            self.assertFalse(errors)
            self.assertEqual({key.path.resolve() for key in keys}, {private, public, outside, outside_pub})
            self.assertEqual(sorted(key.kind for key in keys), ['private', 'private', 'public', 'public'])
            self.assertEqual(discover_keys([home / 'missing']), ([], []))

    def test_quoted_paths_tokens_and_unresolved_values(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch('confissh.keys.Path.home', return_value=home):
                self.assertEqual(identity_path('%d/.ssh/key'), home / '.ssh/key')
            path = home / 'key with spaces "and quotes" 100%'
            self.assertEqual(identity_path(quote_identity_path(str(path))), path)
            for value in ('', 'none', '"unterminated', '%h/key', 'two paths'):
                self.assertIsNone(identity_path(value))

    def test_copy_rechecks_file_and_limits_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'key'
            content = '-----BEGIN RSA PRIVATE KEY-----\nfixture\n'
            path.write_text(content)
            self.assertEqual(read_key(path), content)
            path.write_text('no longer a key')
            with self.assertRaises(ValueError):
                read_key(path)
            path.write_text(content + 'A' * MAX_KEY_BYTES)
            with self.assertRaises(ValueError):
                read_key(path)
            path.unlink()
            with self.assertRaises(ValueError):
                read_key(path)

    def test_unreadable_file_does_not_hide_other_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'key'
            private.write_text('-----BEGIN EC PRIVATE KEY-----\nfixture\n')
            blocked = root / 'blocked'
            blocked.write_text('-----BEGIN PRIVATE KEY-----\nfixture\n')
            original_open = Path.open
            def open_file(path, *args, **kwargs):
                if path == blocked:
                    raise PermissionError(13, 'Permission denied')
                return original_open(path, *args, **kwargs)
            with patch.object(Path, 'open', open_file):
                keys, errors = discover_keys([root])
            self.assertEqual([key.path for key in keys], [private])
            self.assertEqual(len(errors), 1)
