"""Disposable Windows desktop with a filtered read-only project copy."""
import os
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def executable():
    if os.name != 'nt': return None
    path = Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsSandbox.exe'
    return path if path.is_file() else None


def prepare(workspace, data_root, cancel):
    from .tools import sensitive,linklike,SKIP
    workspace,data_root = Path(workspace).resolve(),Path(data_root).resolve()
    folder = data_root/'windows-sandboxes'/uuid.uuid4().hex
    source = folder/'source'
    source.mkdir(parents=True)
    total = count = 0
    for directory,folders,files in os.walk(workspace,followlinks=False):
        if cancel.is_set(): raise RuntimeError('Activity stopped; Windows Sandbox was not opened.')
        folders[:] = [n for n in folders if n not in SKIP and not sensitive(Path(directory,n)) and not linklike(Path(directory,n)) and not Path(directory,n).resolve().is_relative_to(data_root)]
        for name in files:
            path = Path(directory,name)
            if sensitive(path) or linklike(path) or path.resolve().is_relative_to(data_root): continue
            size=path.stat().st_size; total+=size; count+=1
            if size>5_000_000 or total>50_000_000 or count>2000:
                raise ValueError('Windows Sandbox copy exceeds 50 MB / 2000 files / 5 MB per file.')
            target=source/path.relative_to(workspace)
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
    config=ET.Element('Configuration')
    for key,value in {'vGPU':'Disable','Networking':'Disable','AudioInput':'Disable','VideoInput':'Disable',
                      'ProtectedClient':'Enable','PrinterRedirection':'Disable','ClipboardRedirection':'Disable',
                      'MemoryInMB':'4096'}.items(): ET.SubElement(config,key).text=value
    mappings=ET.SubElement(config,'MappedFolders'); mapping=ET.SubElement(mappings,'MappedFolder')
    ET.SubElement(mapping,'HostFolder').text=str(source)
    ET.SubElement(mapping,'SandboxFolder').text=r'C:\VeynuqInput'
    ET.SubElement(mapping,'ReadOnly').text='true'
    config_path=folder/'Veynuq.wsb'
    ET.ElementTree(config).write(config_path,encoding='utf-8',xml_declaration=True)
    return {'configuration':str(config_path),'copied_files':count,'bytes':total,
            'guest_input':r'C:\VeynuqInput','network':False,'host_writes':False,
            'note':'Copy inputs inside the guest before editing. Guest changes are discarded on closing; no automatic host export.'}


def open_desktop(workspace,data_root,cancel):
    app=executable()
    if not app: raise RuntimeError('Windows Sandbox is unavailable. No host task was run. It requires a supported Windows edition and the optional feature already enabled.')
    result=prepare(workspace,data_root,cancel)
    if cancel.is_set(): raise RuntimeError('Activity stopped; Windows Sandbox was not opened.')
    process=subprocess.Popen([str(app),result['configuration']],creationflags=subprocess.CREATE_NO_WINDOW)
    return {**result,'launcher_pid':process.pid,'note':result['note']+' Inspect computer_windows to locate the visible Windows Sandbox client. Do not operate unrelated host windows.'}
