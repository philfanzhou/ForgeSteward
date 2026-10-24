"""Complete run package retention, cache removal, and explicit recovery fixtures."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'plugins/work-cycle/skills/forge-steward-work-cycle/scripts'
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location('retention_fixture', SCRIPTS / 'rule_snapshot.py')
SNAPSHOT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SNAPSHOT)
sys.path.pop(0)


class RuleSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='forgesteward-implement-214-1-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.command('git', 'init', str(self.repo))
        self.run = '20261024T102544Z-eeee'
        self.directory = SNAPSHOT.runs_root(self.repo) / self.run
        self.directory.mkdir(parents=True)
        (self.directory / 'run.json').write_text(json.dumps({
            'created_by': SNAPSHOT.MARKER, 'run_id': self.run}), encoding='utf-8')
        (self.directory / 'events.jsonl').touch()
        self.cache = self.root / 'cache'
        self.packages = {}
        for name in SNAPSHOT.PACKAGES:
            path = self.cache / name
            shutil.copytree(REPO / 'plugins' / name / 'skills' / ('forge-steward-' + name), path,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            self.packages[name] = path
        self.version = (SCRIPTS / 'VERSION').read_text().strip()
        self.saved = json.dumps({'attempt': 3, 'review_rounds': 2, 'head': 'abc123',
                                 'external_write': 'already-created',
                                 'ci_started': '2026-10-24T10:25:44Z',
                                 'ci_deadline': '2026-10-24T10:36:47Z'}).encode()
        (self.directory / 'handoff.json').write_bytes(self.saved)

    def command(self, *args):
        result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True,
                                timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def create(self):
        result = SNAPSHOT.create(self.repo, self.run, self.packages, self.version)
        self.manifest = self.directory / 'rules/manifest.json'
        return result

    def unchanged_state(self):
        self.assertEqual((self.directory / 'handoff.json').read_bytes(), self.saved)

    def test_cache_removal_between_dispatch_and_wait_end_preserves_state(self):
        source = SNAPSHOT.resolve(self.packages, self.version)
        retained = self.create()
        self.assertEqual(retained['identity'], source['identity'])
        scripts = Path(retained['packages']['work-cycle']) / 'scripts'
        stage = retained['packages']['execute-work']
        event = [sys.executable, scripts / 'run_record.py', '--repo', self.repo, 'event',
                 '--run', self.run, '--task', 'implement-214', '--attempt', '3',
                 '--stage', 'implement']
        self.command(*event, '--status', 'started', '--at', '2026-10-24T10:25:44Z')
        self.command(*event, '--status', 'wait-start', '--wait', 'ci',
                     '--at', '2026-10-24T10:26:00Z')
        original_events = (self.directory / 'events.jsonl').read_bytes()
        shutil.rmtree(self.cache)
        self.command(sys.executable, scripts / 'preflight_versions.py', '--expected', self.version,
                     '--skill-dir', stage, '--rules-manifest', self.manifest,
                     '--rules-identity', source['identity'])
        self.command(*event, '--status', 'wait-end', '--wait', 'ci',
                     '--at', '2026-10-24T10:30:00Z')
        events = (self.directory / 'events.jsonl').read_bytes()
        self.assertTrue(events.startswith(original_events))
        end = json.loads(events.splitlines()[-1])
        self.assertEqual((end['status'], end['attempt'], end['wait']), ('wait-end', 3, 'ci'))
        self.unchanged_state()
        # The retained report reader still resolves its package-relative rule dependency.
        spec = importlib.util.spec_from_file_location('retained_reader', scripts / 'run_record.py')
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        self.assertTrue(reader.load_report_spec())
        self.assertEqual(SNAPSHOT.validate(self.manifest, source['identity']), retained)

    def test_every_retained_dependency_is_checked_with_precise_path(self):
        retained = self.create()
        root = Path(retained['packages']['work-cycle'])
        for name in ('scripts/agents.json', 'references/report.md', 'scripts/resource_lock.py',
                     'agents/openai.yaml', 'scripts/VERSION'):
            path = root / name
            raw = path.read_bytes()
            for damage in ('missing', 'tampered'):
                with self.subTest(name=name, damage=damage):
                    if damage == 'missing':
                        path.unlink()
                    else:
                        path.write_bytes(raw + b'changed')
                    with self.assertRaisesRegex(ValueError, name.replace('/', r'[/\\]')):
                        SNAPSHOT.validate(self.manifest, retained['identity'])
                    self.unchanged_state()
                    path.write_bytes(raw)

    def test_same_version_different_roots_and_hashes_do_not_share_identity(self):
        original = SNAPSHOT.resolve(self.packages, self.version)
        moved = dict(self.packages)
        alternate = self.root / 'other-execute'
        shutil.copytree(moved['execute-work'], alternate)
        moved['execute-work'] = alternate
        self.assertNotEqual(original['identity'], SNAPSHOT.resolve(moved, self.version)['identity'])
        (alternate / 'references/queue.md').write_text('changed rules\n')
        self.assertNotEqual(original['packages']['execute-work']['identity'],
                            SNAPSHOT.resolve(moved, self.version)['packages']['execute-work']['identity'])
        retained = self.create()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            SNAPSHOT.validate(self.manifest, '0' * 64)
        data = json.loads(self.manifest.read_text())
        data['packages']['execute-work']['source'] = str(alternate)
        self.manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            SNAPSHOT.validate(self.manifest, retained['identity'])

    def test_retained_preflight_rejects_source_paths_changed_set_and_dependencies(self):
        retained = self.create()
        scripts = Path(retained['packages']['work-cycle']) / 'scripts'
        args = [sys.executable, scripts / 'preflight_versions.py', '--expected', self.version,
                '--rules-manifest', self.manifest, '--rules-identity', retained['identity']]
        for stage in (self.packages['execute-work'], Path(retained['packages']['execute-work']) / '..' / 'execute-work'):
            result = subprocess.run([str(a) for a in (*args, '--skill-dir', stage)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertIn('verified retained directory', result.stderr)
        path = Path(retained['packages']['prepare-work']) / 'references/handoff.md'
        path.write_text('changed')
        result = subprocess.run([str(a) for a in (*args, '--skill-dir', retained['packages']['execute-work'])],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Stop writes', result.stderr)
        self.unchanged_state()

    def test_incomplete_mixed_or_missing_source_dependency_never_publishes(self):
        with self.assertRaisesRegex(ValueError, 'all six'):
            SNAPSHOT.create(self.repo, self.run, {'execute-work': self.packages['execute-work']}, self.version)
        marker = self.packages['execute-work'] / 'VERSION'
        marker.write_text('0.0.1')
        with self.assertRaisesRegex(ValueError, 'version mismatch'):
            self.create()
        marker.write_text(self.version)
        missing = self.packages['work-cycle'] / 'scripts/agents.json'
        missing.unlink()
        with self.assertRaisesRegex(ValueError, 'agents.json'):
            self.create()
        self.assertFalse((self.directory / 'rules').exists())
        self.assertFalse((self.directory / '.rules.lock').exists())
        self.unchanged_state()

    def test_escaped_link_symlink_and_nonregular_resources_fail_closed(self):
        path = self.packages['execute-work'] / 'SKILL.md'
        raw = path.read_bytes()
        path.write_bytes(raw + b'\n[escape](../outside.md)\n')
        with self.assertRaisesRegex(ValueError, 'escapes package'):
            self.create()
        path.write_bytes(raw)
        link = self.packages['execute-work'] / 'link'
        try:
            link.symlink_to(self.directory, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.create()
        self.assertFalse((self.directory / 'rules').exists())

    def test_unreadable_and_nonregular_resource_names_are_reported(self):
        extra = self.packages['execute-work'] / 'payload.bin'
        extra.write_bytes(b'package resource')
        read_bytes = Path.read_bytes
        def unreadable(path):
            if path == extra:
                raise PermissionError('fixture permission denied')
            return read_bytes(path)
        with mock.patch.object(Path, 'read_bytes', unreadable):
            with self.assertRaisesRegex(ValueError, 'payload.bin.*permission denied'):
                self.create()
        extra.unlink()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(extra)
            with self.assertRaisesRegex(ValueError, 'payload.bin.*not a regular file'):
                self.create()
        self.assertFalse((self.directory / 'rules').exists())
        self.unchanged_state()

    def test_public_resolve_create_and_validate_commands(self):
        args = ['--expected', self.version]
        for name, path in self.packages.items():
            args += ['--package', name + '=' + str(path)]
        resolved = json.loads(self.command(sys.executable, SCRIPTS / 'rule_snapshot.py',
                                           'resolve', *args).stdout)
        retained = json.loads(self.command(sys.executable, SCRIPTS / 'rule_snapshot.py',
                                           'create', '--repo', self.repo, '--run', self.run,
                                           *args).stdout)
        self.assertEqual(resolved['identity'], retained['identity'])
        manifest = self.directory / 'rules/manifest.json'
        checked = json.loads(self.command(sys.executable,
                                          Path(retained['packages']['work-cycle']) / 'scripts/rule_snapshot.py',
                                          'validate', '--manifest', manifest,
                                          '--identity', retained['identity']).stdout)
        self.assertEqual(checked, retained)
        self.unchanged_state()

    def test_cancellation_or_source_change_leaves_no_partial_published_tree(self):
        describe = SNAPSHOT.describe
        def changed(name, package, expected):
            row = describe(name, package, expected)
            if name == 'work-cycle' and Path(package) == self.packages[name] and calls[0] > 0:
                row['rule_hash'] = 'changed'
            if name == 'work-cycle':
                calls[0] += 1
            return row
        calls = [0]
        with mock.patch.object(SNAPSHOT, 'describe', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                self.create()
        package_file = SNAPSHOT.package_file
        def interrupted(root, relative):
            if list(self.directory.glob('.rules-*')):
                raise KeyboardInterrupt()
            return package_file(root, relative)
        with mock.patch.object(SNAPSHOT, 'package_file', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.create()
        self.assertFalse((self.directory / 'rules').exists())
        self.assertEqual(list(self.directory.glob('.rules-*')), [])
        self.assertFalse((self.directory / '.rules.lock').exists())
        self.unchanged_state()

    def test_duplicate_creation_and_concurrent_writer_preserve_evidence(self):
        guard = self.directory / '.rules.lock'
        guard.mkdir()
        (guard / 'owner').write_text('another writer')
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual((guard / 'owner').read_text(), 'another writer')
        (guard / 'owner').unlink()
        guard.rmdir()
        retained = self.create()
        saved = self.manifest.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.create()
        self.assertEqual(self.manifest.read_bytes(), saved)
        self.assertEqual(SNAPSHOT.validate(self.manifest, retained['identity']), retained)
        self.unchanged_state()

    def test_explicit_complete_transition_keeps_prior_identities_and_deadlines(self):
        old = SNAPSHOT.resolve(self.packages, self.version)
        old_bytes = json.dumps(old).encode()
        (self.directory / 'rules-source.json').write_bytes(old_bytes)
        for name, path in self.packages.items():
            marker = path / ('scripts/VERSION' if name == 'work-cycle' else 'VERSION')
            marker.write_text('0.2.999')
        new = SNAPSHOT.resolve(self.packages, '0.2.999')
        self.assertNotEqual(old['identity'], new['identity'])
        self.assertEqual(new['version'], '0.2.999')
        self.assertEqual((self.directory / 'rules-source.json').read_bytes(), old_bytes)
        self.unchanged_state()
        # Resolving alone grants no compatibility or continuation, and mutates no run files.
        self.assertFalse((self.directory / 'rules').exists())

    def test_unapproved_location_and_added_resource_are_rejected(self):
        run = json.loads((self.directory / 'run.json').read_text())
        (self.directory / 'run.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'not a script-created run'):
            self.create()
        (self.directory / 'run.json').write_text(json.dumps(run))
        retained = self.create()
        (Path(retained['packages']['prepare-work']) / 'unexpected').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            SNAPSHOT.validate(self.manifest, retained['identity'])


if __name__ == '__main__':
    unittest.main()
