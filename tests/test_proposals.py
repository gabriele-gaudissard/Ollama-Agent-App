import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from veyq.desktop import DesktopAPI
from veyq.engine import ModelClient
from veyq.proposals import prepare, changes, ALLOWED
from veyq.storage import Store
from veyq.tools import ToolRunner
from veyq.verification import Verification


def tool(name, **arguments):
    return {'role':'assistant', 'content':'', 'tool_calls':[{'id':str(time.monotonic_ns()), 'function':{'name':name, 'arguments':arguments}}]}


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'project'
        self.workspace.mkdir()
        (self.workspace / 'a.py').write_text('original')
        self.store = Store(self.root / 'profile')
        self.store.vault.get = lambda n: ''
        self.store.data['settings'].update(workspace=str(self.workspace), permission='full', network=True)
        self.api = DesktopAPI(self.store)
        self.sid = self.api.create_session()
        self.session = self.store.data['sessions'][0]
        self.runner = ToolRunner(self.store, self.store.snapshot()['settings'], 'test', threading.Event(), lambda *a:None, lambda *a:True, self.root / 'app', self.session)
        self.addCleanup(self.runner.close)

    def seed(self, content='changed'):
        record = prepare(self.runner, 'Implement the task')
        record['state'] = 'completed'
        (self.store.root / 'proposals' / record['id'] / 'source' / 'a.py').write_text(content)
        self.store.save()
        return record['id']

    def test_copy_excludes_credentials_links_and_dependencies(self):
        (self.workspace / '.env').write_text('secret')
        (self.workspace / 'node_modules').mkdir()
        (self.workspace / 'node_modules' / 'heavy.js').write_text('dependency')
        key = self.seed()
        source = self.store.root / 'proposals' / key / 'source'
        self.assertEqual({p.name for p in source.iterdir()}, {'a.py'})
        self.assertEqual((self.workspace / 'a.py').read_text(), 'original')

    def test_parallel_coding_writes_separate_copies_and_verifies(self):
        barrier = threading.Barrier(2)
        seen = {}
        def chat(client, messages):
            workspace = client.settings['workspace']
            turn = seen.get(workspace, 0)
            seen[workspace] = turn + 1
            if turn == 0:
                barrier.wait(timeout=5)
                return tool('write_file', path='a.py', content=workspace)
            if turn == 1: return tool('read_file', path='a.py')
            return {'role':'assistant','content':'Verified my isolated changes.'}
        with patch.object(ModelClient, 'chat', chat):
            result = self.runner.execute('delegate_coding', {'tasks':['Implement first change','Implement second change']})
        self.assertTrue(result['ok'], result)
        rows = result['result']
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(r['state'] == 'completed' and r['host_project_unchanged'] for r in rows))
        self.assertEqual((self.workspace / 'a.py').read_text(), 'original')
        self.assertTrue(all(r['changes'][0]['path'] == 'a.py' for r in rows))
        self.assertFalse(self.runner.child_agents)

    def test_apply_creates_backup_and_survives_restart(self):
        key = self.seed()
        self.assertIn('changed', changes(self.runner, key)[0]['diff'])
        self.assertEqual(changes(self.runner, key, True)['applied'], 1)
        self.assertEqual((self.workspace / 'a.py').read_text(), 'changed')
        restored = Store(self.store.root)
        self.assertEqual(restored.data['sessions'][0]['proposals'][0]['state'], 'applied')
        self.assertTrue(list((self.store.root / 'backups').glob('*.json')))
        self.assertEqual(changes(self.runner, key), [])

    def test_competing_proposals_refuse_lost_update(self):
        first, second = self.seed('first'), self.seed('second')
        changes(self.runner, first, True)
        with self.assertRaisesRegex(ValueError, 'Host file changed'): changes(self.runner, second, True)
        self.assertEqual((self.workspace / 'a.py').read_text(), 'first')

    def test_wrong_chat_or_project_cannot_review_proposal(self):
        key = self.seed()
        self.session['proposals'][0]['workspace'] = str(self.root / 'other')
        with self.assertRaises(PermissionError): changes(self.runner, key)
        with self.assertRaises(ValueError): changes(self.runner, '../profile')

    def test_proposal_baseline_traversal_is_rejected(self):
        key = self.seed()
        (self.store.root / 'proposals' / key / 'baseline.json').write_text(json.dumps({'../outside':'a'*64}))
        with self.assertRaises(ValueError): changes(self.runner, key, True)

    def test_changes_during_approval_do_not_apply(self):
        key = self.seed()
        self.runner.settings['permission'] = 'auto'
        def approve(preview):
            (self.store.root / 'proposals' / key / 'source' / 'a.py').write_text('different')
            return True
        self.runner.approve = approve
        result = self.runner.execute('proposal_changes', {'action':'apply','proposal_id':key})
        self.assertFalse(result['ok'])
        self.assertEqual((self.workspace / 'a.py').read_text(), 'original')

    def test_child_tools_and_paths_are_enforced_independently_of_model(self):
        self.runner.settings['_worker_tools'] = sorted(ALLOWED)
        for name, args in [('delegate_coding', {'tasks':['escape']}), ('browser_open', {'url':'https://example.com'}), ('keyboard_layout', {'action':'set','layout':'us'}), ('write_file', {'path':str(self.root / 'outside'), 'content':'escape'})]:
            self.assertFalse(self.runner.execute(name, args)['ok'])
        self.assertFalse((self.root / 'outside').exists())

    def test_child_command_cannot_fall_back_to_host(self):
        self.runner.settings.update(_worker_tools=sorted(ALLOWED), execution_environment='sandbox')
        with patch('veyq.sandbox.shutil.which', return_value=None):
            result = self.runner.execute('exec_cmd', {'command':'echo test'})
        self.assertFalse(result['ok'])
        self.assertIn('no host command', result['error'])

    def test_running_copy_becomes_reviewable_after_recovery(self):
        record = prepare(self.runner, 'Implement a task')
        restored = Store(self.store.root)
        self.assertEqual(restored.data['sessions'][0]['proposals'][0]['state'], 'interrupted')

    def test_stop_reaches_coding_children(self):
        from unittest.mock import Mock
        child = Mock()
        self.runner.child_agents.append(child)
        self.runner.close()
        child.stop.assert_called_once()
        self.runner.child_agents.clear()

    def test_each_changed_file_requires_its_own_observation(self):
        ledger = Verification(self.runner)
        for path in ['a.py','b.py']:
            ledger.observe('write_file', {'path':path}, {'ok':True})
        ledger.observe('read_file', {'path':'a.py'}, {'ok':True})
        self.assertEqual(ledger.pending, [{'kind':'file', 'target':str(self.workspace / 'b.py')}])
        ledger.observe('read_file', {'path':'unrelated.py'}, {'ok':True})
        self.assertTrue(ledger.pending)
        ledger.observe('read_file', {'path':'b.py'}, {'ok':True})
        self.assertFalse(ledger.pending)

    def test_applied_proposal_tracks_every_file_and_deletion(self):
        key = self.seed()
        source = self.store.root / 'proposals' / key / 'source'
        (source / 'a.py').unlink()
        (source / 'b.py').write_text('new')
        result = self.runner.execute('proposal_changes', {'action':'apply', 'proposal_id':key})
        self.assertTrue(result['ok'], result)
        ledger = Verification(self.runner)
        ledger.observe('proposal_changes', {'action':'apply'}, result)
        ledger.observe('read_file', {'path':'b.py'}, {'ok':True})
        self.assertEqual(ledger.pending, [{'kind':'missing', 'target':str(self.workspace / 'a.py')}])
        ledger.observe('list_dir', {'path':'.'}, {'ok':True,'result':[{'name':'b.py'}]})
        self.assertFalse(ledger.pending)

    def test_review_refuses_changed_host_link(self):
        key = self.seed()
        resolve = Path.resolve
        def redirected(path, *args, **kwargs):
            if path == self.workspace / 'a.py': return self.root / 'outside.py'
            return resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', redirected):
            with self.assertRaises(PermissionError): changes(self.runner, key)

    def test_verification_persists_and_matches_the_actual_window(self):
        ledger = Verification(self.runner)
        ledger.observe('computer_action', {'snapshot_id':'used'}, {'ok':True,'result':{'window_id':123}})
        ledger.observe('computer_inspect', {'window_id':456}, {'ok':True})
        ledger.observe('read_file', {'path':'a.py'}, {'ok':True})
        self.assertEqual(Verification(self.runner).pending, [{'kind':'window','target':123}])
        ledger.observe('computer_inspect', {'window_id':123}, {'ok':True})
        self.assertFalse(ledger.pending)

    def test_verified_memory_or_image_does_not_erase_pending_file(self):
        ledger = Verification(self.runner)
        ledger.observe('write_file', {'path':'a.py'}, {'ok':True})
        ledger.observe('generate_image', {'path':'generated.png'}, {'ok':True})
        ledger.observe('save_memory', {}, {'ok':True})
        self.assertTrue(ledger.pending)

    def test_missing_file_requires_confirmed_absence(self):
        ledger = Verification(self.runner)
        ledger.observe('delete_file', {'path':'a.py'}, {'ok':True})
        ledger.observe('list_dir', {'path':'.'}, {'ok':True,'result':[{'name':'a.py'}]})
        self.assertTrue(ledger.pending)
        ledger.observe('list_dir', {'path':'.'}, {'ok':True,'result':[]})
        self.assertFalse(ledger.pending)

    def test_directory_observation_does_not_verify_file_contents(self):
        ledger = Verification(self.runner)
        ledger.observe('write_file', {'path':'a.py'}, {'ok':True})
        ledger.observe('list_dir', {'path':'.'}, {'ok':True,'result':[{'name':'a.py'}]})
        self.assertTrue(ledger.pending)

    def test_overview_and_review_scope_and_safe_text(self):
        key = self.seed('<script>unsafe</script>')
        self.assertEqual(self.api.get_task_overview(self.sid)['proposals'][0]['id'], key)
        self.assertIn('<script>', self.api.review_proposal(self.sid, key)['diff'])
