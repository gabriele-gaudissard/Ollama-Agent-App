"""Opt-in Windows Task Scheduler worker: bounded, read-only, no desktop input."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from .runtime import ProfileLease, profile_root


def task_name(root):
    return 'Veynuq Read-only '+hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]


def ps_literal(value): return "'"+str(value).replace("'", "''")+"'"


def task_xml(app_root, data_root, python, sid):
    namespace = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
    ET.register_namespace('',namespace)
    def child(parent, name, value=None, **attrs):
        node = ET.SubElement(parent, '{'+namespace+'}'+name, attrs)
        if value is not None: node.text = value
        return node
    task = ET.Element('{'+namespace+'}Task',version='1.2')
    registration = child(task,'RegistrationInfo')
    child(registration,'Description','Veynuq scheduled project reads. No commands, mutations or desktop control.')
    triggers = child(task,'Triggers')
    timer = child(triggers,'TimeTrigger')
    repetition = child(timer,'Repetition')
    child(repetition,'Interval','PT5M')
    child(repetition,'StopAtDurationEnd','false')
    child(timer,'StartBoundary',(datetime.now()+timedelta(minutes=5)).replace(microsecond=0).isoformat())
    child(timer,'Enabled','true')
    login = child(triggers,'LogonTrigger')
    child(login,'Enabled','true'); child(login,'UserId',sid)
    principals = child(task,'Principals')
    principal = child(principals,'Principal',id='User')
    child(principal,'UserId',sid); child(principal,'LogonType','InteractiveToken'); child(principal,'RunLevel','LeastPrivilege')
    settings = child(task,'Settings')
    for key,value in {'MultipleInstancesPolicy':'IgnoreNew','DisallowStartIfOnBatteries':'false',
                      'StopIfGoingOnBatteries':'false','StartWhenAvailable':'true','RunOnlyIfNetworkAvailable':'false',
                      'AllowStartOnDemand':'true','Enabled':'true','Hidden':'false','WakeToRun':'false',
                      'ExecutionTimeLimit':'PT6M'}.items(): child(settings,key,value)
    actions = child(task,'Actions',Context='User')
    action = child(actions,'Exec')
    child(action,'Command',str(python))
    child(action,'Arguments',subprocess.list2cmdline([str(Path(app_root)/'app.py'),'--background','--background-profile',str(data_root)]))
    child(action,'WorkingDirectory',str(app_root))
    return ET.tostring(task,encoding='unicode')


def configure(app_root, store, enabled):
    if os.name != 'nt': raise RuntimeError('Background schedules are available on Windows only.')
    if type(enabled) is not bool: raise ValueError('Invalid background setting.')
    name = task_name(store.root)
    marker = store.root/'background-task.json'
    flags = {'creationflags':subprocess.CREATE_NO_WINDOW}
    if enabled:
        if (Path(app_root)/'.git').exists():
            raise RuntimeError('Background scheduling requires an installed release, not a development checkout.')
        sid_result = subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,timeout=10,check=True,**flags)
        sid = re.search(r'\bS-1-(?:\d+-)+\d+\b',sid_result.stdout)
        if not sid: raise RuntimeError('Cannot identify the current Windows user.')
        runtime=Path(app_root)/'runtime.json'
        python=Path(json.loads(runtime.read_text(encoding='utf-8'))['python']).with_name('pythonw.exe') if runtime.exists() else Path(app_root)/'.venv/Scripts/pythonw.exe'
        if not python.is_file() or not python.resolve().is_relative_to(Path(app_root).resolve()):
            raise RuntimeError('A verified installed Python runtime is required.')
        document = store.root/'background-task.xml'
        document.write_text(task_xml(app_root,store.root,python,sid.group()),encoding='utf-8')
        command = "$s=New-Object -ComObject Schedule.Service; $s.Connect(); $f=$s.GetFolder('\\'); $f.RegisterTask("+ps_literal(name)+",[IO.File]::ReadAllText("+ps_literal(document)+"),6,"+ps_literal(sid.group())+",$null,3,$null)|Out-Null"
    else:
        command = "$s=New-Object -ComObject Schedule.Service; $s.Connect(); $f=$s.GetFolder('\\'); try { $null=$f.GetTask("+ps_literal(name)+"); $f.DeleteTask("+ps_literal(name)+",0) } catch { if($_.Exception.HResult -ne -2147024894){throw} }"
    completed = subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=20,**flags)
    if completed.returncode: raise RuntimeError('Windows could not update the background schedule. No setting was saved.')
    from .storage import atomic_json
    if enabled: atomic_json(marker,{'name':name,'app_root':str(Path(app_root).resolve()),'python':str(python)})
    else:
        marker.unlink(missing_ok=True)
        (store.root/'background-stop').write_text(str(time.time()),encoding='ascii')
    return {'enabled':enabled}


def run(app_root,data_root=None):
    if data_root and not Path(data_root).is_absolute(): raise ValueError('Background profile must be absolute.')
    root = Path(data_root).resolve() if data_root else profile_root(app_root)
    try: lease = ProfileLease(root).acquire()
    except RuntimeError: return  # Foreground app already owns all scheduling.
    with lease:
        root = lease.root
        marker = root/'background-task.json'
        if not marker.is_file(): return
        record = json.loads(marker.read_text(encoding='utf-8'))
        if record.get('app_root') != str(Path(app_root).resolve()): return
        # Never run a partial/locally changed installation in the background.
        installation = json.loads((root/'installation.json').read_text(encoding='utf-8'))
        if installation.get('root') != str(Path(app_root).resolve()): return
        from .updater import program_path
        for name,digest in installation['files'].items():
            program_path(name)
            path = Path(app_root)/name
            if path.is_symlink() or not path.resolve().is_relative_to(Path(app_root).resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest: return
        from .storage import Store, atomic_json
        store = Store(root)
        if not store.data['settings'].get('background_schedules'): return
        from .desktop import DesktopAPI
        api = DesktopAPI(store)
        # A detached worker must never wait for an absent approver/user.
        api._agent.approve = lambda preview: False
        def no_question(*args): raise RuntimeError('A scheduled run cannot ask interactive questions.')
        api._agent.ask = no_question
        started = time.time()
        heartbeat = root/'background-status.json'
        def requested_stop():
            try: return float((root/'background-stop').read_text()) >= started-30
            except (OSError,ValueError): return False
        if requested_stop(): return
        try:
            api._scheduler.tick()
            while api._agent.busy and time.time()-started<240 and not requested_stop():
                atomic_json(heartbeat,{'state':'running','time':time.time()})
                time.sleep(.5)
            if api._agent.busy: api._agent.stop()
            worker = getattr(api._agent,'worker',None)
            if worker: worker.join(timeout=20)
            if not api._agent.busy: api._scheduler.tick(finish_only=True)
            atomic_json(heartbeat,{'state':api._agent.state,'time':time.time()})
        finally:
            api._agent.stop(); api._voice.close()
