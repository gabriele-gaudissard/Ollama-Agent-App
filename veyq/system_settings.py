"""Typed Windows input-method operations; no arbitrary script arguments."""
import base64
import json
import os
import re

LAYOUTS = {
    "us": ("en-US", "0409:00000409"),
    "uk": ("en-GB", "0809:00000809"),
    "it": ("it-IT", "0410:00000410"),
    "fr": ("fr-FR", "040c:0000040c"),
    "de": ("de-DE", "0407:00000407"),
    "es": ("es-ES", "0c0a:0000040a"),
}
QUERY = """
$languages = Get-WinUserLanguageList
$override = Get-WinDefaultInputMethodOverride
$state = @{ default_tip = $override.InputMethodTip; languages = @($languages | ForEach-Object { @{language=$_.LanguageTag; input_tips=@($_.InputMethodTips)} }) }
Write-Output ('VEYNUQ_KEYBOARD_JSON=' + ($state | ConvertTo-Json -Depth 5 -Compress))
"""


def requested_layout(text):
    if not re.search(r'tastier|keyboard|layout|input method', text, re.I): return None
    for pattern, layout in [(r'\b(uk|british|britannic\w*)\b', 'uk'), (r'\b(us|usa|american\w*|stati uniti)\b', 'us'), (r'italian\w*', 'it'), (r'french|frances\w*', 'fr'), (r'german|tedesc\w*', 'de'), (r'spanish|spagnol\w*', 'es'), (r'english|inglese', 'us')]:
        if re.search(pattern, text, re.I): return layout
    return None


def keyboard_layout(runner, action="get", layout=""):
    if os.name != "nt":
        raise RuntimeError("Keyboard layout settings are available on Windows only.")
    if action not in {"get", "set"} or action == "set" and layout not in LAYOUTS:
        raise ValueError("Use get, or set with layout us/uk/it/fr/de/es.")
    script = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8;\n"
    if action == "set":
        language, tip = LAYOUTS[layout]
        # Values come exclusively from the fixed table; preserve existing
        # languages/layouts and the Windows display-language preference.
        script += f"""
$languages = Get-WinUserLanguageList
$entry = $languages | Where-Object LanguageTag -eq '{language}' | Select-Object -First 1
if (-not $entry) {{ $entry = (New-WinUserLanguageList '{language}')[0]; $languages.Add($entry) }}
if (-not $entry.InputMethodTips.Contains('{tip}')) {{ $entry.InputMethodTips.Add('{tip}') }}
Set-WinUserLanguageList -LanguageList $languages -Force
Set-WinDefaultInputMethodOverride -InputTip '{tip}'
"""
    script += QUERY
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    process = runner.run_process(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], runner.cwd, 60)
    if process['exit_code']:
        raise RuntimeError('Windows keyboard operation failed: ' + process.get('output', '')[:2000])
    marker = next((line.split('=', 1)[1] for line in process.get('output', '').splitlines() if line.startswith('VEYNUQ_KEYBOARD_JSON=')), None)
    if marker is None:
        raise RuntimeError('Windows did not return verifiable keyboard settings.')
    state = json.loads(marker)
    if action == 'set':
        if str(state.get('default_tip', '')).lower() != LAYOUTS[layout][1].lower():
            raise RuntimeError('Windows did not confirm the requested default keyboard layout.')
        state.update(verified=True, selected_layout=layout,
                     note='Default input method changed for this Windows user. Existing languages/layouts retained. Already open apps may retain their current input method until reopened; this tool does not claim to change every active window.')
    return state
