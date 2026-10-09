"""User-started local dictation, with a disposable worker and no saved audio."""
import copy
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

MODEL_REVISION = 'ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66'


class VoiceInput:
    def __init__(self, data_root):
        self.root = Path(data_root)/'voice-models'/'base'
        self.lock = threading.RLock()
        self.process = None
        self.status = {'state':'idle'}
        self.generation = 0

    def ready(self):
        try:
            return self.root.joinpath('veynuq-ready.txt').read_text() == MODEL_REVISION and self.root.joinpath('model.bin').is_file()
        except OSError: return False

    def busy(self):
        with self.lock: return self.status['state'] in {'downloading','starting','recording','transcribing'}

    def snapshot(self):
        with self.lock: return {**copy.deepcopy(self.status), 'ready':self.ready()}

    def start(self, operation):
        if operation not in {'prepare','record'}: raise ValueError('Unknown dictation operation.')
        with self.lock:
            if self.busy(): raise RuntimeError('Dictation is already active.')
            if operation == 'record' and not self.ready(): raise RuntimeError('Download the local speech model first.')
            self.generation += 1
            generation = self.generation
            self.status = {'state':'downloading' if operation=='prepare' else 'starting', 'started_at':time.time()}
            env = {k:v for k,v in os.environ.items() if not re.search(r'(?i)(token|secret|password|api_key|credential)',k)}
            env.update(HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(self.root.parent/'cache'),HF_HUB_DISABLE_PROGRESS_BARS='1')
            env['PYTHONIOENCODING']='utf-8'
            if operation == 'record': env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
            flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            try:
                process = subprocess.Popen([sys.executable,'-m','veyq.voice_worker',operation,str(self.root)],
                    cwd=Path(__file__).resolve().parent.parent,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=flags)
            except Exception:
                self.status={'state':'error','error':'Cannot start local dictation.'}
                raise
            self.process = process
            reader = threading.Thread(target=self._read,args=(process,generation,operation),daemon=True)
            reader.start()
            return self.snapshot()

    def _read(self, process, generation, operation):
        # Bound all worker output; never put transcripts in logs or on disk.
        try:
            while True:
                line = process.stdout.readline(40000)
                if not line: break
                item = json.loads(line)
                if item.get('state') not in {'ready','recording','transcribing','completed','error'}: raise ValueError('Invalid dictation result.')
                with self.lock:
                    if generation != self.generation: return
                    if item['state']=='ready': self.root.joinpath('veynuq-ready.txt').write_text(MODEL_REVISION)
                    self.status.update(item)
            process.wait(timeout=10)
            with self.lock:
                if generation==self.generation and self.busy():
                    self.status={'state':'error','error':'Local dictation stopped unexpectedly.'}
        except Exception:
            with self.lock:
                if generation==self.generation: self.status={'state':'error','error':'Local dictation failed. Check the microphone and retry.'}
        finally:
            if process.poll() is None: process.kill()
            for stream in (process.stdin,process.stdout):
                try: stream.close()
                except (OSError, ValueError): pass
            with self.lock:
                if self.process is process: self.process=None

    def stop(self):
        with self.lock:
            if self.process and self.status['state'] in {'starting','recording'}:
                try:
                    self.process.stdin.write('stop\n');self.process.stdin.flush()
                except (OSError, ValueError): pass
            return {'ok':True}

    def cancel(self):
        with self.lock:
            self.generation += 1
            process,self.process=self.process,None
            self.status={'state':'idle'}
            if process and process.poll() is None:
                process.kill()
        return {'ok':True}

    close = cancel
