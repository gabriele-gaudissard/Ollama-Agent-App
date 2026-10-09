import copy
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from veyq.browser import Browser
from veyq.computer import Computer
from veyq.desktop import DesktopAPI
from veyq.engine import ModelClient, action_intent
from veyq.storage import Store
from veyq.tools import ToolRunner


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'data');self.workspace=self.root/'project';self.workspace.mkdir()
        self.store.data['settings'].update(workspace=str(self.workspace),permission='full',network=True)
        self.api=DesktopAPI(self.store);self.sid=self.api.create_session();self.agent=self.api._agent
        self.runner=ToolRunner(self.store,self.store.snapshot()['settings'],'controls',threading.Event(),lambda *a:None,lambda *a:True,self.root,{})
    def tearDown(self):
        self.agent.stop();self.runner.close();self.temp.cleanup()
    def pointer_fixture(self):
        computer=Computer(self.store.root);rect=types.SimpleNamespace(left=100,top=100,right=500,bottom=500)
        window=Mock();window.rectangle.return_value=rect;window.handle=42
        element=Mock();element.rectangle.return_value=types.SimpleNamespace(left=110,top=110,right=130,bottom=130)
        snapshot={'rect':[100,100,500,500],'window_id':42};computer.snapshots['s']=snapshot
        hit=Mock();hit.top_level_parent.return_value.handle=42
        return computer,snapshot,window,element,hit
    def test_mouse_click_uses_observed_point_and_consumes_snapshot(self):
        computer,snapshot,window,element,hit=self.pointer_fixture();mouse=Mock()
        with patch.object(computer,'checked_element',return_value=(snapshot,window,element,False)),patch.object(computer,'desktop') as desktop,patch.object(computer,'password',return_value=False),patch.dict(sys.modules,{'pywinauto':types.SimpleNamespace(mouse=mouse)}):
            desktop.return_value.from_point.return_value=hit
            self.assertEqual(computer.pointer('s',0,'double_click')['performed'],'double_click')
        mouse.double_click.assert_called_once_with(coords=(120,120));self.assertNotIn('s',computer.snapshots)
    def test_mouse_rejects_other_window_covering_target(self):
        computer,snapshot,window,element,hit=self.pointer_fixture();hit.top_level_parent.return_value.handle=99
        with patch.object(computer,'checked_element',return_value=(snapshot,window,element,False)),patch.object(computer,'desktop') as desktop:
            desktop.return_value.from_point.return_value=hit
            with self.assertRaises(PermissionError):computer.pointer('s',0,'click')
        self.assertIn('s',computer.snapshots)
    def test_drag_releases_mouse_even_if_move_fails(self):
        computer,snapshot,window,element,hit=self.pointer_fixture();mouse=Mock();mouse.move.side_effect=RuntimeError('Lost connection')
        with patch.object(computer,'checked_element',return_value=(snapshot,window,element,False)),patch.object(computer,'desktop') as desktop,patch.object(computer,'password',return_value=False),patch.dict(sys.modules,{'pywinauto':types.SimpleNamespace(mouse=mouse)}):
            desktop.return_value.from_point.return_value=hit
            with self.assertRaises(RuntimeError):computer.pointer('s',0,'drag',end_x=200,end_y=200)
        mouse.release.assert_called_once_with(coords=(300,300))
    def test_cancelled_mouse_tool_sends_no_input(self):
        self.runner.cancel.set()
        with patch.object(self.runner.computer,'pointer') as pointer:
            self.assertFalse(self.runner.execute('computer_pointer',{'snapshot_id':'s','index':0,'action':'click'})['ok']);pointer.assert_not_called()
    def test_literal_typing_escapes_keyboard_metacharacters(self):
        computer=Computer(self.store.root);window=Mock();window.process_id.return_value=123;element=Mock();element.element_info.control_type='Edit';element.element_info.process_id=123
        snapshot={'window_id':42,'elements':[(element,())]};computer.snapshots['s']=snapshot;send=Mock()
        with patch.object(computer,'checked_element',return_value=(snapshot,window,element,False)),patch.object(computer,'verify_focus'),patch.dict(sys.modules,{'pywinauto.keyboard':types.SimpleNamespace(send_keys=send)}):
            computer.action('s',0,'type','hello +^%{world}')
        self.assertEqual(send.call_args.args[0],'hello {+}{^}{%}{{}world{}}');self.assertNotIn('s',computer.snapshots)
    def test_readonly_field_rejects_typing_without_consuming_snapshot(self):
        computer=Computer(self.store.root);element=Mock();element.element_info.control_type='Edit';element.iface_value.CurrentIsReadOnly=True;window=Mock()
        snapshot={'elements':[(element,())]};computer.snapshots['s']=snapshot
        with patch.object(computer,'checked_element',return_value=(snapshot,window,element,False)):
            with self.assertRaises(ValueError):computer.action('s',0,'type','text')
        self.assertIn('s',computer.snapshots);window.set_focus.assert_not_called()
    def test_deep_windows_controls_are_visible_in_inspection(self):
        computer=Computer(self.store.root);rect=types.SimpleNamespace(left=0,top=0,right=100,bottom=100);controls=[]
        for i in range(23):
            element=Mock();element.element_info.runtime_id=[i];element.element_info.control_type='Edit' if i==22 else 'Pane';element.element_info.name='Input' if i==22 else 'Container';element.rectangle.return_value=rect;element.window_text.return_value=element.element_info.name;element.iface_value.CurrentIsReadOnly=False;controls.append(element)
        for i, element in enumerate(controls):element.children.return_value=controls[i+1:i+2]
        controls[0].process_id.return_value=123
        with patch.object(computer,'target',return_value=controls[0]),patch.object(computer,'password',return_value=False):result=computer.inspect(42)
        self.assertIn(22,result['editable_indexes']);self.assertFalse(result['truncated'])
    def test_native_control_initializes_each_worker_and_balances_own_com_reference(self):
        computer=Computer(self.store.root);desktop=Mock()
        with patch.object(sys,'coinit_flags',0,create=True),patch('veyq.computer.ctypes.windll.ole32.CoInitializeEx',return_value=0) as initialize,patch('veyq.computer.ctypes.windll.ole32.CoUninitialize') as finish,patch.dict(sys.modules,{'pywinauto':types.SimpleNamespace(Desktop=desktop)}):
            computer.desktop();computer.desktop();initialize.assert_called_once_with(None,0)
            computer.snapshots['s']={};computer.close();computer.close();finish.assert_called_once();self.assertFalse(computer.snapshots)
            def another_activity():
                other=Computer(self.store.root);other.desktop();other.close()
            worker=threading.Thread(target=another_activity);worker.start();worker.join(timeout=2)
            self.assertFalse(worker.is_alive());self.assertEqual(initialize.call_count,2);self.assertEqual(finish.call_count,2)
    def test_changed_control_identity_rejects_stale_click(self):
        computer=Computer(self.store.root);element=Mock();element.element_info.runtime_id=[2];element.element_info.control_type='Button';element.element_info.name='Different'
        window=Mock();window.process_id.return_value=123
        computer.snapshots['s']={'time':0,'window_id':42,'pid':123,'elements':[(element,((1,),'Button','Original'))]}
        with patch.object(computer,'target',return_value=window):
            with self.assertRaises(ValueError):computer.action('s',0,'click')
        element.click_input.assert_not_called()
    def test_followup_after_action_still_requires_new_requested_action(self):
        contexts=[]
        replies=[{'role':'assistant','content':'','tool_calls':[{'id':'a','function':{'name':'write_file','arguments':{'path':'first.txt','content':'first'}}}]},{'role':'assistant','content':'First done.'},{'role':'assistant','content':'You can write second.txt yourself.'},{'role':'assistant','content':'','tool_calls':[{'id':'b','function':{'name':'write_file','arguments':{'path':'second.txt','content':'second'}}}]},{'role':'assistant','content':'','tool_calls':[{'id':'verify','function':{'name':'read_file','arguments':{'path':'second.txt'}}},{'id':'verifyfirst','function':{'name':'read_file','arguments':{'path':'first.txt'}}}]},{'role':'assistant','content':'Both written.'}]
        original=self.agent._drain_followups;injected=[]
        def drain(session):
            if len(contexts)==2 and not injected:
                injected.append(True);self.agent.followups.append('Create second.txt for me')
            return original(session)
        def chat(client,messages):contexts.append(copy.deepcopy(messages));return replies.pop(0)
        with patch.object(ModelClient,'chat',chat),patch.object(self.agent,'_drain_followups',side_effect=drain):
            self.agent.start(self.sid,'Create first.txt')
            deadline=time.monotonic()+5
            while self.agent.busy and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.agent.busy);self.assertEqual((self.workspace/'second.txt').read_text(),'second');self.assertEqual(len(contexts),6)
    def test_mixed_execute_and_explain_request_still_requires_execution(self):
        self.assertTrue(action_intent('Scrivi il file e spiegami cosa contiene'))
        self.assertTrue(action_intent('Impostami la tastiera senza istruzioni'))
        self.assertFalse(action_intent('Explain how to write the file'))
    def test_download_checksum_failure_preserves_existing_file(self):
        target=self.workspace/'download.txt';target.write_text('original')
        with patch('veyq.tools.public_request',return_value={'data':b'wrong','url':'https://example.com/file'}):
            result=self.runner.execute('download_file',{'url':'https://example.com/file','path':'download.txt','sha256':'0'*64})
        self.assertFalse(result['ok']);self.assertEqual(target.read_text(),'original')
    def test_restore_preserves_current_file_in_new_backup(self):
        target=self.workspace/'recover.txt';target.write_text('before');backup=self.runner.backup(target);target.write_text('after')
        result=self.runner.execute('restore_backup',{'backup_id':backup});self.assertTrue(result['ok']);self.assertEqual(target.read_text(),'before')
        self.assertEqual((self.store.root/'backups'/result['result']['previous_content_backup']).read_text(),'after')
    def test_browser_offline_denial_does_not_start_browser(self):
        self.runner.settings['network']=False
        with patch.object(self.runner.browser,'call') as browser:
            self.assertFalse(self.runner.execute('browser_open',{'url':'https://example.com'})['ok']);browser.assert_not_called()
    def test_tool_catalog_covers_actual_available_tools(self):
        from veyq.tools import TOOLS
        catalog=self.api.get_tool_catalog();self.assertEqual(catalog['total'],len(TOOLS));self.assertEqual(sum(g['count'] for g in catalog['groups']),len(TOOLS))
    def test_inspection_reports_literal_value_and_checkbox_state(self):
        computer=Computer(self.store.root)
        window=Mock();window.handle=42;window.process_id.return_value=123
        field=Mock();field.element_info.control_type='Edit';field.iface_value.CurrentValue='Typed test value'
        check=Mock();check.element_info.control_type='CheckBox';check.get_toggle_state.return_value=1
        password=Mock();password.element_info.control_type='Edit';password.iface_value.CurrentValue='SECRET'
        for i,element in enumerate([window,field,check,password]):
            element.element_info.runtime_id=[i];element.element_info.name=str(i);element.children.return_value=[]
            element.rectangle.return_value=types.SimpleNamespace(left=0,top=0,right=100,bottom=100)
            element.window_text.return_value=str(i);element.is_visible.return_value=True;element.is_enabled.return_value=True
        window.element_info.control_type='Window';window.children.return_value=[field,check,password]
        with patch.object(computer,'target',return_value=window),patch.object(computer,'password',side_effect=lambda e:e is password),patch.object(computer,'editable',side_effect=lambda e:e is field):
            state=computer.inspect(42)
        self.assertEqual(next(e for e in state['elements'] if e['type']=='Edit')['value'],'Typed test value')
        self.assertEqual(next(e for e in state['elements'] if e['type']=='CheckBox')['toggle_state'],1)
        self.assertNotIn('SECRET',json.dumps(state))
    def test_real_isolated_browser_acts_and_rejects_old_snapshot(self):
        candidates=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
        if not any(p.exists() for p in candidates): self.skipTest('Microsoft Edge is not available on this host')
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
                self.wfile.write(b'<html><body><label>Message<input aria-label="Message"></label><input type="password"><button onclick="document.querySelector(\'output\').textContent=document.querySelector(\'input\').value">Apply</button><output></output></body></html>')
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        browser=Browser(self.store.root,threading.Event())
        try:
            state=browser.call('open',url=f'http://127.0.0.1:{server.server_port}/');self.assertFalse(any(e['type']=='password' for e in state['elements']))
            field=next(e['index'] for e in state['elements'] if e['tag']=='input')
            state=browser.call('action',snapshot_id=state['snapshot_id'],index=field,action='type',text='real browser action')
            old=state['snapshot_id'];button=next(e['index'] for e in state['elements'] if e['tag']=='button')
            state=browser.call('action',snapshot_id=old,index=button,action='click');self.assertIn('real browser action',state['text'])
            with self.assertRaises(RuntimeError):browser.call('action',snapshot_id=old,index=button,action='click')
        finally:
            browser.stop();server.shutdown();server.server_close()
        self.assertIsNotNone(browser.process.poll())
