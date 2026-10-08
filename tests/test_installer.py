import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InstallerTests(unittest.TestCase):
    def test_dark_icon_contains_windows_sizes(self):
        icon = (ROOT / 'assets/brand/veynuq-dark.ico').read_bytes()
        reserved, kind, count = struct.unpack_from('<HHH', icon)
        self.assertEqual((reserved, kind), (0, 1))
        sizes = {icon[6 + i * 16] or 256 for i in range(count)}
        self.assertEqual(sizes, {16, 24, 32, 48, 64, 128, 256})

    @unittest.skipUnless(os.name == 'nt', 'Windows COM shortcut test')
    def test_installer_creates_valid_shortcut_with_dark_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'install.ps1'), '-ShortcutOnly', '-ShortcutDirectory', directory], check=True, capture_output=True)
            link = Path(directory) / 'Veynuq.lnk'
            self.assertTrue(link.is_file(), 'Installer must keep the newly created shortcut')
            inspector = Path(directory) / 'inspect.ps1'
            inspector.write_text("param([string]$LinkPath)\n$link=(New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)\n@{icon=$link.IconLocation;root=$link.WorkingDirectory;target=$link.TargetPath;arguments=$link.Arguments}|ConvertTo-Json\n")
            result = subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(inspector),str(link)],capture_output=True,text=True,check=True)
            data = json.loads(result.stdout)
            self.assertEqual(Path(data['root']).resolve(), ROOT)
            self.assertTrue(data['icon'].endswith('veynuq-dark.ico,0'))
            self.assertIn('Launcher.ps1', data['arguments'])
            self.assertIn('-WindowStyle Hidden', data['arguments'])
