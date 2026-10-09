import copy
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from veyq.storage import Store
from veyq.desktop import DesktopAPI
from veyq.engine import ModelClient, Cancelled
from veyq.tools import ToolRunner
from veyq.computer import Computer
from veyq.models import catalog, estimate


class FeatureTests(unittest.TestCase):
    def test_window_close_handlers_are_hashable_and_cancel_all_work(self):
        import types
        from veyq.desktop import main
        class Event:
            def __init__(self): self.handlers = []
            def __iadd__(self, handler):
                self.handlers.append(handler)
                return self
        events = types.SimpleNamespace(loaded=Event(), closing=Event(), closed=Event())
        window = types.SimpleNamespace(events=events)
        def start(**kwargs):
            for event in (events.closing, events.closed):
                self.assertEqual({handler() for handler in event.handlers}, {None})
        webview = types.SimpleNamespace(create_window=Mock(return_value=window), start=start)
        with patch.dict('sys.modules', {'webview': webview}), patch('sys.argv', ['app.py']), patch('veyq.ui.document',return_value='<html></html>'), patch('veyq.runtime.profile_root',return_value=self.store.root), patch('veyq.desktop.ROOT', self.root), patch('veyq.desktop.Store', return_value=self.store), patch('veyq.desktop.DesktopAPI', return_value=self.api), patch.object(self.agent, 'stop', return_value={'ok': True}) as stop, patch.object(self.api, 'cancel_model_action', return_value={'ok': True}) as cancel:
            main()
            self.assertEqual(stop.call_count, 2)
            self.assertEqual(cancel.call_count, 2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'data')
        self.workspace = self.root / 'project'
        self.workspace.mkdir()
        self.store.data['settings'].update(workspace=str(self.workspace), network=True, permission='full')
        self.api = DesktopAPI(self.store)
        self.sid = self.api.create_session()
        self.session = next(s for s in self.store.data['sessions'] if s['id'] == self.sid)
        self.agent = self.api._agent
        self.runner = ToolRunner(self.store, self.store.data['settings'], 'features', threading.Event(), lambda *a: None, lambda *a: False, self.root/'app', self.session)

    def tearDown(self):
        self.agent.stop()
        self.temp.cleanup()

    def wait_idle(self):
        end=time.monotonic()+5
        while self.agent.busy and time.monotonic()<end: time.sleep(.01)
        self.assertFalse(self.agent.busy)

    def test_language_default_and_immediate_persistence(self):
        self.assertEqual(self.store.data['settings']['lang'], 'en')
        for lang in ['it','es','fr','en']:
            self.api.set_language(lang)
            self.assertEqual(Store(self.store.root).data['settings']['lang'], lang)
        with self.assertRaises(ValueError): self.api.set_language('xx')

    def test_corrupt_json_restores_previous_and_preserves_damage(self):
        self.store.data['memory']='keep me';self.store.save();self.store.save()
        self.store.path.write_text('{broken',encoding='utf-8')
        recovered=Store(self.store.root)
        self.assertEqual(recovered.data['memory'],'keep me')
        self.assertTrue(recovered.recovery_notice)
        self.assertEqual(next(self.store.root.glob('state.corrupt-*.json')).read_text(),'{broken')

    def test_corrupt_json_without_backup_starts_empty(self):
        folder=self.root/'broken';folder.mkdir();(folder/'state.json').write_text('[]')
        recovered=Store(folder)
        self.assertEqual(recovered.data['sessions'],[])
        self.assertTrue(recovered.recovery_notice)

    def test_projects_scope_history_and_full_text_search(self):
        project=self.api.create_project('Sample')
        self.api.assign_project(self.sid,project['id'])
        self.session['history']=[{'role':'user','content':'hidden needle in message'}]
        other=self.api.create_session();self.api.assign_project(other,project['id'])
        self.runner.session=next(s for s in self.store.data['sessions'] if s['id']==other)
        third=self.api.create_session()
        next(s for s in self.store.data['sessions'] if s['id']==third)['history']=[{'role':'user','content':'unrelated confidential'}]
        self.assertEqual([s['id'] for s in self.api.get_sessions('needle')],[self.sid])
        result=self.runner.tool_read_project_context()
        self.assertIn('needle',json.dumps(result));self.assertNotIn('confidential',json.dumps(result))

    def test_memory_edit_rejects_credentials(self):
        self.api.save_memory('Prefer Python');self.assertEqual(self.api.get_memory(),'Prefer Python')
        with self.assertRaises(ValueError):self.api.save_memory('ghp_1234567890abcdef')
        self.api.clear_memory();self.assertEqual(self.api.get_memory(),'')

    def test_followup_waits_until_all_tool_results(self):
        entered=threading.Event();release=threading.Event();calls=[]
        first={'role':'assistant','content':'','tool_calls':[{'id':'first','type':'function','function':{'name':'make_dir','arguments':{'path':'first'}}},{'id':'second','type':'function','function':{'name':'make_dir','arguments':{'path':'second'}}}]}
        def chat(client,messages):
            calls.append(copy.deepcopy(messages))
            if len(calls)==1:
                entered.set();release.wait(3);return first
            return {'role':'assistant','content':'Finished with follow-up'}
        with patch.object(ModelClient,'chat',chat):
            self.agent.start(self.sid,'Create folders')
            self.assertTrue(entered.wait(2));self.agent.follow_up(self.sid,'Add a note');release.set();self.wait_idle()
        history=self.session['history'];idx=next(i for i,m in enumerate(history) if m.get('content')=='Add a note')
        self.assertEqual([m['role'] for m in history[idx-3:idx]],['assistant','tool','tool'])
        self.assertEqual(calls[-1][-1]['content'],'Add a note')

    def test_question_exact_id_and_cancel(self):
        result=[]
        t=threading.Thread(target=lambda:result.append(self.agent.ask('Which folder?', ['A','B'])))
        t.start()
        while not self.agent.pending_question:time.sleep(.01)
        with self.assertRaises(ValueError):self.agent.resolve_question('wrong','A')
        self.agent.resolve_question(self.agent.pending_question['id'],'B');t.join(2)
        self.assertEqual(result,[{'answer':'B'}])
        with self.assertRaises(ValueError):self.agent.resolve_question('old','A')

    def test_stop_saves_partial_response_without_tool_calls(self):
        with patch.object(ModelClient,'chat',side_effect=Cancelled('Partial response')):
            self.agent.start(self.sid,'Long answer');self.wait_idle()
        self.assertEqual(self.session['history'][-1],{'role':'assistant','content':'Partial response'})
        self.assertEqual(self.agent.state,'cancelled')

    def test_regenerate_keeps_completed_side_effects(self):
        (self.workspace/'already.txt').write_text('done')
        self.session['history']=[{'role':'user','content':'Do it'},{'role':'assistant','content':'Done'},{'role':'user','content':'Later'}]
        with patch.object(ModelClient,'chat',return_value={'role':'assistant','content':'Regenerated'}):
            self.api.regenerate(self.sid,1,True);self.wait_idle()
        self.assertNotIn('Later',json.dumps(self.session['history']))
        self.assertEqual((self.workspace/'already.txt').read_text(),'done')

    def test_cd_persists_across_shells_and_restart(self):
        (self.workspace/'sub').mkdir()
        self.assertTrue(self.runner.execute('exec_cmd',{'command':'cd sub'})['ok'])
        self.assertEqual(self.runner.cwd,(self.workspace/'sub').resolve())
        result=self.runner.execute('exec_cmd',{'command':'pwd'})
        self.assertIn('sub',result['result']['output'])
        self.assertEqual(Path(Store(self.store.root).data['sessions'][0]['cwd']).resolve(),(self.workspace/'sub').resolve())

    def test_clone_uses_fixed_arguments_and_disallows_existing_destination(self):
        with patch.object(self.runner,'run_process',return_value={'exit_code':0}) as run:
            self.runner.tool_clone_repository('octocat/Hello-World','new')
            argv=run.call_args.args[0]
            self.assertIn('https://github.com/octocat/Hello-World.git',argv)
            self.assertIn('--',argv)
            self.assertTrue(any('core.hooksPath=' in a for a in argv))
        for repo in ['../evil','x/y;bad','https://github.com/x/y']:
            with self.assertRaises(ValueError):self.runner.tool_clone_repository(repo,'new')
        with self.assertRaises(ValueError):self.runner.tool_clone_repository('x/y','.')

    def test_missing_branch_retries_default_branch(self):
        with patch.object(self.runner,'run_process',side_effect=[{'exit_code':128,'output':'fatal: Remote branch main not found in upstream origin'}, {'exit_code':0,'output':'cloned'}]) as run:
            result=self.runner.tool_clone_repository('octocat/Hello-World','new','main')
            self.assertEqual(result['exit_code'],0)
            self.assertNotIn('--branch',run.call_args_list[-1].args[0])
            self.assertIn('default branch',result['branch_note'])

    def test_failed_command_is_not_reported_successful(self):
        result=self.runner.execute('exec_cmd',{'command':'exit 7'})
        self.assertFalse(result['ok']);self.assertEqual(result['result']['exit_code'],7)

    def test_stop_interrupts_stalled_http_and_keeps_partial(self):
        from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path=='/api/show':
                    body=b'{"capabilities":["tools"]}'
                    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers()
                self.wfile.write(b'{"message":{"content":"Partial from HTTP"},"done":false}\n');self.wfile.flush()
                time.sleep(3)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.store.data['settings']['url']='http://127.0.0.1:'+str(server.server_port)
        try:
            self.agent.start(self.sid,'Respond')
            end=time.monotonic()+2
            while not any(e['type']=='text' for e in self.agent.events) and time.monotonic()<end:time.sleep(.01)
            self.assertTrue(any(e['type']=='text' for e in self.agent.events))
            raw=self.agent.client.response.raw
            self.assertIsNotNone(raw)
            start=time.monotonic();self.agent.stop();self.wait_idle()
            self.assertLess(time.monotonic()-start,2)
            self.assertEqual(self.session['history'][-1]['content'],'Partial from HTTP')
        finally:
            server.shutdown();server.server_close()

    def test_denied_computer_action_never_sends_input(self):
        self.runner.settings['permission']='auto'
        with patch.object(self.runner.computer,'action') as action:
            r=self.runner.execute('computer_action',{'snapshot_id':'unknown','index':0,'action':'click'})
            self.assertFalse(r['ok']);action.assert_not_called()

    def test_desktop_rejects_stale_snapshot_and_changed_element(self):
        computer=Computer(self.store.root)
        with self.assertRaises(ValueError):computer.action('unknown',0,'click')
        element=Mock();element.element_info.runtime_id=[1];element.element_info.control_type='Button';element.element_info.name='Changed'
        window=Mock();window.process_id.return_value=123
        computer.snapshots['snapshot']={'time':time.monotonic(),'window_id':1,'pid':123,'elements':[(element,([1],'Button','Original'))]}
        with patch.object(computer,'target',return_value=window):
            with self.assertRaises(ValueError):computer.action('snapshot',0,'click')
        element.click_input.assert_not_called();window.set_focus.assert_not_called()

    def test_protected_git_and_missing_web_parser(self):
        folder=self.workspace/'.git';folder.mkdir();(folder/'config').write_text('private')
        self.assertFalse(self.runner.execute('read_file',{'path':'.git/config'})['ok'])
        with patch('veyq.tools.BeautifulSoup',None):
            result=self.runner.execute('web_search',{'query':'test'})
            self.assertFalse(result['ok']);self.assertIn('Beautiful Soup',result['error'])

    def test_catalog_has_ten_families_and_unknown_estimates(self):
        self.assertEqual(len(catalog()),10)
        self.assertEqual(len({m['name'].split(':')[0] for m in catalog()}),10)
        self.assertIsNone(estimate('unknown:7b')['download_gb'])
        self.assertGreater(estimate('unknown:7b',4_000_000_000)['ram_recommended_gb'],4)
        self.assertIsNone(estimate('unknown')['ram_min_gb'])
        self.assertEqual(estimate('qwen3:14b')['capability'],'General agent')

    def test_live_model_metadata_overrides_catalog(self):
        response=Mock(status_code=200)
        response.json.return_value={'capabilities':['tools','vision'],'details':{'parameter_size':'15B','quantization_level':'Q8_0'},'model_info':{'qwen.context_length':65536}}
        with patch('veyq.desktop.requests.Session') as http,patch.object(self.api,'get_models',return_value={'ok':True,'details':[{'name':'qwen3:14b','size':15_000_000_000}]}):
            http.return_value.post.return_value=response
            result=self.api.get_model_info('qwen3:14b')
        self.assertTrue(result['installed']);self.assertTrue(result['vision']);self.assertEqual(result['context_tokens'],65536)
        self.assertEqual(result['quantization'],'Q8_0');self.assertEqual(result['installed_size_gb'],15)

    def test_remote_model_does_not_inherit_local_requirements(self):
        self.store.data['settings']['provider']='compatible'
        result=self.api.get_model_info('qwen3:14b')
        self.assertIsNone(result['ram_min_gb']);self.assertIsNone(result['tools'])

    def test_unlimited_controls_persist_and_command_does_not_time_out(self):
        self.api.save_settings({'max_steps':0,'command_timeout':0,'confirm_full':True})
        command='Start-Sleep -Milliseconds 1500; Write-Output done' if os.name=='nt' else 'sleep 1.5; echo done'
        result=self.runner.execute('exec_cmd',{'command':command,'timeout':1})
        self.assertTrue(result['ok']);self.assertFalse(result['result']['timed_out'])
        self.assertEqual(Store(self.store.root).data['settings']['max_steps'],0)

    def test_github_repository_argument_overrides_optional_default(self):
        self.runner.settings['github_repo']='default/repo'
        with patch('veyq.tools.public_request',return_value={'text':'{"name":"chosen"}'}) as http:
            self.assertEqual(self.runner.tool_github('GET','',repository='another/chosen')['name'],'chosen')
            self.assertEqual(http.call_args.args[0],'https://api.github.com/repos/another/chosen/')
        with self.assertRaises(ValueError):self.runner.tool_github('GET','contents',repository='../escape')

    def test_setup_does_not_download_if_engine_already_running(self):
        from veyq.setup import setup_engine
        with patch('veyq.setup.os.name','nt'),patch('veyq.setup.engine_available',return_value=True),patch('veyq.setup.requests.Session') as http:
            self.assertTrue(setup_engine(self.store.root)['ok']);http.assert_not_called()

    def test_compatible_image_payload_is_explicit(self):
        client=ModelClient({**self.store.data['settings'],'provider':'compatible'},'',threading.Event(),lambda *a:None)
        response=Mock();response.status_code=200;response.iter_lines.return_value=[b'data: {"choices":[{"delta":{"content":"Seen"},"finish_reason":"stop"}]}']
        with patch.object(client.session,'post',return_value=response) as post:
            client.chat([{'role':'user','content':'Inspect','images':['abc']}])
            content=post.call_args.kwargs['json']['messages'][0]['content']
            self.assertEqual(content[1]['image_url']['url'],'data:image/png;base64,abc')
        client.close()


if __name__=='__main__':unittest.main()
