import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from veyq.desktop import DesktopAPI
from veyq.durability import compact, recover
from veyq.sandbox import digest
from veyq.storage import Store
from veyq.tools import ToolRunner


class Advanced(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='veynuq-controlled-')
        self.root = Path(self.temp.name)
        self.workspace = self.root/'project';self.workspace.mkdir()
        self.store = Store(self.root/'profile')
        if os.name != 'nt': self.store.vault.get=lambda name:''
        self.store.data['settings'].update(workspace=str(self.workspace), network=True, permission='full')
        self.api = DesktopAPI(self.store);self.sid=self.api.create_session()
        self.session=self.store.data['sessions'][0]
        self.runner=ToolRunner(self.store, self.store.data['settings'], 'qa',threading.Event(),lambda *a:None,lambda *a:True,self.root/'app',self.session)

    def tearDown(self):
        self.runner.close();self.temp.cleanup()

    def seed_sandbox(self):
        (self.workspace/'a.txt').write_text('before',encoding='utf-8')
        self.runner.sandbox.root=self.store.root/'sandboxes'/('a'*32)
        self.runner.sandbox.root.mkdir(parents=True)
        (self.runner.sandbox.root/'a.txt').write_text('after',encoding='utf-8')
        self.runner.sandbox.baseline={'a.txt':digest(self.workspace/'a.txt')}
        self.runner.sandbox.save()

    def test_context_compaction_preserves_goal_and_tool_protocol(self):
        history=[]
        for n in range(12):
            history += [{'role':'user','content':f'goal {n} '+ 'x'*5000},
                {'role':'assistant','content':'','tool_calls':[{'id':str(n),'function':{'name':'read_file','arguments':{}}}]},
                {'role':'tool','tool_call_id':str(n),'name':'read_file','content':'evidence '+str(n)}, {'role':'assistant','content':'done'}]
        session={'history':history};result=compact(session,18000)
        self.assertEqual(result[-4]['content'],history[-4]['content'])
        self.assertIn('User request: goal',session['context_summary'])
        summary=session['context_summary'];compact(session,18000);self.assertEqual(summary,session['context_summary'])
        calls={c['id'] for m in result for c in m.get('tool_calls',[])}
        self.assertEqual(calls,{m['tool_call_id'] for m in result if m['role']=='tool'})
        self.assertEqual(len(history),48)

    def test_long_single_task_is_bounded_without_losing_current_request(self):
        history=[{'role':'user','content':'Keep the original requirements'}]
        for n in range(60):
            history += [{'role':'assistant','content':'','tool_calls':[{'id':str(n),'function':{'name':'read_file'}}]},
                        {'role':'tool','name':'read_file','tool_call_id':str(n),'content':'x'*8000}]
        result=compact({'history':history},30000)
        self.assertLess(len(json.dumps(result)),30001)
        self.assertEqual(result[0],history[0]);self.assertEqual(result[-1]['tool_call_id'],'59')

    def test_recovery_marks_uncertain_write_without_replay(self):
        call={'id':'write','function':{'name':'write_file','arguments':{'path':'a.txt','content':'new'}}}
        self.session.update(task={'state':'running','pending_tool':call},history=[{'role':'assistant','tool_calls':[call],'content':''}])
        self.store.save();restored=Store(self.store.root).data['sessions'][0]
        self.assertEqual(restored['task']['state'],'interrupted')
        self.assertTrue(json.loads(restored['history'][1]['content'])['outcome_unknown'])
        self.assertFalse((self.workspace/'a.txt').exists())
        recover(restored);self.assertEqual(len(restored['history']),2)

    def test_read_only_cannot_be_bypassed_by_full_permission(self):
        self.runner.settings['_read_only']=True
        for name,args in [('write_file',{'path':'a.txt','content':'bad'}),('exec_cmd',{'command':'echo bad'}),('computer_windows',{}),('delegate_tasks',{'tasks':['a']})]:
            self.assertFalse(self.runner.execute(name,args)['ok'])
        self.assertFalse((self.workspace/'a.txt').exists())
        outside=self.root/'outside.txt';outside.write_text('private')
        self.assertFalse(self.runner.execute('read_file',{'path':str(outside)})['ok'])
        self.assertTrue(self.runner.execute('checkpoint_task',{'progress':'Read only verified','next_steps':'Inspect again'})['ok'])
        self.assertTrue(self.runner.execute('load_procedure',{'name':'review'})['ok'])

    def test_schedule_runs_once_and_pauses_after_failed_run(self):
        job=self.api.save_automation(self.sid,'Read the project',1);job['next_run']=10
        agent=self.api._agent
        with patch.object(agent,'start',return_value={'ok':True}) as start:
            self.api._scheduler.tick(11)
            start.assert_called_once_with(self.sid,'Scheduled read-only task: Read the project',policy='read_only')
            self.api._scheduler.tick(12);start.assert_called_once()
        self.assertFalse(job['enabled']);self.assertEqual(job['last_state'],'idle')

    def test_read_only_resume_preserves_policy_and_restart_pauses_schedule(self):
        self.session['task']={'state':'interrupted','goal':'Review','policy':'read_only'}
        with patch.object(self.api._agent,'start') as start:
            self.api.resume_task(self.sid);self.assertEqual(start.call_args.kwargs['policy'],'read_only')
        job=self.api.save_automation(self.sid,'Review',1);job['last_state']='running';self.store.save()
        restored=Store(self.store.root).data['automations'][0]
        self.assertFalse(restored['enabled']);self.assertEqual(restored['last_state'],'interrupted')
        self.api.delete_session(self.sid);self.assertEqual(self.store.data['automations'],[])

    def test_sandbox_absent_never_falls_back_to_host(self):
        self.runner.settings['execution_environment']='sandbox'
        with patch('veyq.sandbox.shutil.which',return_value=None),patch.object(self.runner,'run_process') as execute:
            result=self.runner.execute('exec_cmd',{'command':'echo should-not-run'})
            self.assertFalse(result['ok']);execute.assert_not_called()

    def test_sandbox_remote_engine_is_denied(self):
        results=[SimpleNamespace(returncode=0,stdout='remote\n'),SimpleNamespace(returncode=0,stdout=json.dumps([{'Endpoints':{'docker':{'Host':'ssh://remote'}}}]))]
        with patch('veyq.sandbox.subprocess.run',side_effect=results):
            with self.assertRaises(PermissionError):self.runner.sandbox.local_context()

    def test_sandbox_stale_host_file_is_not_overwritten(self):
        self.seed_sandbox();(self.workspace/'a.txt').write_text('external change')
        with self.assertRaises(ValueError):self.runner.sandbox.apply()
        self.assertEqual((self.workspace/'a.txt').read_text(),'external change')

    def test_sandbox_review_restart_and_apply_with_backup(self):
        self.seed_sandbox();self.assertIn('+after',self.runner.sandbox.changes()[0]['diff'])
        restored=ToolRunner(self.store,self.runner.settings,'resume',threading.Event(),lambda *a:None,lambda *a:True,self.root/'app',self.session)
        try:
            self.assertEqual(restored.sandbox.apply()['applied'],1)
            self.assertEqual((self.workspace/'a.txt').read_text(),'after')
            self.assertEqual(len(list((self.store.root/'backups').glob('*.json'))),1)
        finally:restored.close()

    def test_sandbox_partial_apply_failure_rolls_back(self):
        self.seed_sandbox();(self.runner.sandbox.root/'b.txt').write_text('new')
        from veyq.storage import atomic_bytes
        def fail_second(path,data):
            if path.name=='b.txt':raise OSError('Controlled failure')
            atomic_bytes(path,data)
        with patch('veyq.storage.atomic_bytes',side_effect=fail_second):
            with self.assertRaises(OSError):self.runner.sandbox.apply()
        self.assertEqual((self.workspace/'a.txt').read_text(),'before');self.assertFalse((self.workspace/'b.txt').exists())

    def test_sandbox_copy_excludes_credentials_and_profile(self):
        (self.workspace/'.env').write_text('SECRET')
        (self.workspace/'a.py').write_text('print(1)')
        profile=Store(self.workspace/'profile')
        other=ToolRunner(profile,{**self.runner.settings,'workspace':str(self.workspace)},'copy',threading.Event(),lambda *a:None,lambda *a:True,self.root/'app',{})
        with patch('veyq.sandbox.shutil.which',return_value='docker'),patch.object(other.sandbox,'local_context'):
            other.sandbox.prepare()
        self.assertEqual(set(other.sandbox.baseline),{'a.py'})
        other.close()

    def test_parallel_workers_are_concurrent_and_cannot_mutate_or_escape(self):
        (self.workspace/'a.txt').write_text('evidence')
        barrier=threading.Barrier(2)
        class Client:
            def __init__(self,*a):self.response=None;self.turn=0;self.session=None
            def close(self):pass
            def chat(self,messages):
                self.turn+=1
                if self.turn==1:
                    barrier.wait(timeout=3)
                    return {'role':'assistant','content':'','tool_calls':[
                        {'id':'read','function':{'name':'read_file','arguments':{'path':'a.txt'}}},
                        {'id':'write','function':{'name':'write_file','arguments':{'path':'bad','content':'bad'}}},
                        {'id':'outside','function':{'name':'read_file','arguments':{'path':str(self_outer.root/'outside')}}}]}
                self_outer.assertTrue(any('Read-only tool required' in m.get('content','') for m in messages))
                self_outer.assertTrue(any('cannot leave' in m.get('content','') for m in messages))
                return {'role':'assistant','content':'a.txt contains evidence'}
        self_outer=self
        with patch('veyq.engine.ModelClient',Client):result=self.runner.tool_delegate_tasks(['First analysis','Second analysis'])
        self.assertEqual([r['reads'] for r in result],[1,1]);self.assertFalse((self.workspace/'bad').exists())

    def test_worktree_uses_separate_branch_and_disables_hooks(self):
        subprocess.run(['git','init',str(self.workspace)],check=True,capture_output=True)
        (self.workspace/'a.txt').write_text('original')
        subprocess.run(['git','-C',str(self.workspace),'add','a.txt'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.workspace),'-c','user.name=QA','-c','user.email=qa@example.invalid','commit','-m','fixture'],check=True,capture_output=True)
        hook=self.workspace/'.git/hooks/post-checkout';hook.write_text('#!/bin/sh\necho bad > hook-ran\n');hook.chmod(0o755)
        result=self.runner.tool_git_worktree('create');destination=Path(result['path'])
        (destination/'a.txt').write_text('isolated')
        self.assertEqual((self.workspace/'a.txt').read_text(),'original');self.assertFalse((destination/'hook-ran').exists())
        self.assertIn(result['branch'],self.runner.tool_git_worktree('list')['output'])
        subprocess.run(['git','-C',str(self.workspace),'worktree','remove','--force',str(destination)],check=True,capture_output=True)

    def test_review_includes_staged_untracked_and_excludes_secrets(self):
        subprocess.run(['git','init',str(self.workspace)],check=True,capture_output=True)
        (self.workspace/'staged.txt').write_text('STAGED EVIDENCE');(self.workspace/'new.txt').write_text('NEW EVIDENCE')
        (self.workspace/'.env').write_text('SECRET-SENTINEL')
        subprocess.run(['git','-C',str(self.workspace),'add','staged.txt'],check=True,capture_output=True)
        review=self.api.review_changes(self.sid)['diff']
        self.assertIn('STAGED EVIDENCE',review);self.assertIn('NEW EVIDENCE',review);self.assertNotIn('SECRET-SENTINEL',review)


class LiveDocker(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('VEYNUQ_DOCKER_QA')=='1','Real Docker check runs in the isolated Linux CI job')
    def test_actual_offline_container_copy_apply_and_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='veynuq-docker-') as folder:
            root=Path(folder);workspace=root/'project';workspace.mkdir();(workspace/'a.txt').write_text('original')
            store=Store(root/'profile');settings={**store.data['settings'],'workspace':str(workspace),'permission':'full','execution_environment':'sandbox'}
            # Linux CI has no login session/keyring; this fixture contains no credentials.
            store.vault.get=lambda name:''
            runner=ToolRunner(store,settings,'docker',threading.Event(),lambda *a:None,lambda *a:True,root/'app',{})
            try:
                command="python - <<'PY'\nimport socket, pathlib\nassert not pathlib.Path('/host').exists()\ns=socket.socket();s.settimeout(1)\ntry:s.connect(('1.1.1.1',443))\nexcept OSError:pass\nelse:raise RuntimeError('Unexpected network access')\npathlib.Path('a.txt').write_text('container verified')\nprint('isolated and offline')\nPY"
                result=runner.execute('exec_cmd',{'command':command,'timeout':30})
                self.assertTrue(result['ok'],result);self.assertIn('isolated and offline',result['result']['output'])
                self.assertEqual((workspace/'a.txt').read_text(),'original')
                self.assertTrue(runner.execute('sandbox_changes',{'action':'apply'})['ok'])
                self.assertEqual((workspace/'a.txt').read_text(),'container verified')
                containers=subprocess.run(['docker','ps','-aq','--filter','name=veynuq-'],capture_output=True,text=True,check=True)
                self.assertEqual(containers.stdout.strip(),'')
            finally:runner.close()
