import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from veyq.voice import VoiceInput,MODEL_REVISION
from veyq.voice_worker import transcribe_samples


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='veynuq-voice-qa-');self.voice=VoiceInput(Path(self.temp.name))
    def tearDown(self):
        self.voice.close();self.temp.cleanup()
    def ready(self):
        self.voice.root.mkdir(parents=True)
        (self.voice.root/'veynuq-ready.txt').write_text(MODEL_REVISION)
        (self.voice.root/'model.bin').write_bytes(b'fixture')
    def test_mic_never_starts_before_model_is_ready(self):
        with patch('veyq.voice.subprocess.Popen') as process:
            with self.assertRaises(RuntimeError):self.voice.start('record')
        process.assert_not_called()
    def test_cancel_kills_only_own_worker_and_discards_transcript(self):
        process=Mock();process.poll.return_value=None;self.voice.process=process
        self.voice.status={'state':'recording','text':'private dictation'}
        self.voice.cancel();process.kill.assert_called_once();self.assertEqual(self.voice.status,{'state':'idle'})
    def test_stop_signals_capture_without_saving_audio(self):
        process=Mock();self.voice.process=process;self.voice.status={'state':'recording'}
        self.voice.stop();process.stdin.write.assert_called_once_with('stop\n');process.stdin.flush.assert_called_once()
        self.assertFalse(list(Path(self.temp.name).rglob('*.wav')))
        process.poll.return_value=0
    def test_record_worker_has_offline_flags_and_no_credentials(self):
        self.ready();process=Mock();process.stdout=io.StringIO('{"state":"completed","text":"Test phrase"}\n');process.stdin=io.StringIO();process.poll.return_value=0
        with patch.dict('os.environ',{'HF_TOKEN':'SHOULD-NOT-PASS','API_KEY':'SHOULD-NOT-PASS'}),patch('veyq.voice.subprocess.Popen',return_value=process) as launch:
            self.voice.start('record')
            deadline=time.monotonic()+2
            while self.voice.busy() and time.monotonic()<deadline:time.sleep(.01)
            env=launch.call_args.kwargs['env']
            self.assertEqual(env['HF_HUB_OFFLINE'],'1');self.assertNotIn('HF_TOKEN',env);self.assertNotIn('API_KEY',env)
            self.assertEqual(self.voice.snapshot()['text'],'Test phrase')
        self.assertEqual(list(Path(self.temp.name).rglob('*.wav')),[])
    def test_silence_does_not_generate_hallucinated_text(self):
        import numpy as np
        model=Mock();self.assertEqual(transcribe_samples(model,np.zeros(16000,dtype=np.float32)),'');model.transcribe.assert_not_called()
    def test_transcription_returns_original_language_and_bounded_text(self):
        import numpy as np
        segment=Mock();segment.text=' Apri il progetto e verifica i file. '
        model=Mock();model.transcribe.return_value=([segment],None)
        self.assertEqual(transcribe_samples(model,np.ones(16000,dtype=np.float32)*.1),'Apri il progetto e verifica i file.')
        self.assertIsNone(model.transcribe.call_args.kwargs['language']);self.assertTrue(model.transcribe.call_args.kwargs['vad_filter'])
    def test_parent_disconnect_closes_capture_and_discards_audio(self):
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        import numpy as np
        from veyq import voice_worker
        closed=[]
        class Stream:
            def __init__(self,**args):self.callback=args['callback']
            def __enter__(self):
                self.callback((np.ones(16000,dtype=np.int16)*2000).tobytes(),16000,None,False)
                return self
            def __exit__(self,*args):closed.append(True)
        output=io.StringIO()
        with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(WhisperModel=Mock()),'sounddevice':SimpleNamespace(RawInputStream=Stream)}),patch('sys.argv',['worker','record',str(self.voice.root)]),patch('sys.stdin',io.StringIO('')),patch.object(voice_worker,'transcribe_samples') as transcribe,redirect_stdout(output):
            voice_worker.main()
        self.assertEqual(closed,[True]);transcribe.assert_not_called();self.assertNotIn('completed',output.getvalue())
