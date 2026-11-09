"""First-batch button / confirm interaction checks. No price API and no provider call."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which('google-chrome') or shutil.which('google-chrome-stable')


def test_first_gate_lets_the_first_call_through_only():
    node = shutil.which('node')
    if not node:
        pytest.skip('needs node')
    got = subprocess.run(
        [node, '--experimental-strip-types', 'tests/js/first_action.ts'],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    body = json.loads(got.stdout)
    assert body == {'first': True, 'second': False, 'again': True}


def test_confirm_keeps_quote_sentence_and_shared_actions():
    confirm = (ROOT / 'src/ui/Confirm.tsx').read_text()
    text = (ROOT / 'src/confirmText.ts').read_text()
    chooser = (ROOT / 'src/ui/MemoryChooser.tsx').read_text()
    assert 'confirmDesc' not in confirm  # the sentence is still built by askCost, not recomputed here
    assert 'data-testid="confirm-desc"' in confirm
    assert 'ConfirmActions' in confirm and 'firstGate' in confirm
    assert 'frame_count' in text and 'frame_duration_ms' in text
    assert 'ConfirmActions' in chooser and 'memory-chooser-ok' in chooser
    assert 'ca-panel__primary' in (ROOT / 'src/ui/Button.tsx').read_text()
    # Settings and the SVG integration files stay out of this batch.
    assert 'from \'./Button\'' not in (ROOT / 'src/ui/KeySettings.tsx').read_text()
    assert 'from \'./Button\'' not in (ROOT / 'src/ui/ImageToolbar.tsx').read_text()


def _dump(url: str) -> str:
    assert CHROME
    env = os.environ.copy()
    profile = tempfile.mkdtemp(prefix='chrome-ui-')
    proc = subprocess.run(
        ['timeout', '20', CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
         f'--user-data-dir={profile}', '--virtual-time-budget=6000', '--dump-dom', url],
        cwd=ROOT, capture_output=True, text=True,
    )
    # Chrome often writes the DOM and then lingers; timeout may return 124 with the DOM already printed.
    html = proc.stdout or ''
    if 'data-ready' not in html and proc.returncode not in (0, 124):
        raise AssertionError(proc.stderr[-500:])
    return html


@pytest.mark.skipif(not CHROME, reason='needs google-chrome')
@pytest.mark.parametrize('mode,runs,cancels', [('ok', '1', '0'), ('cancel', '0', '1'), ('escape', '0', '1')])
def test_confirm_click_and_escape_fire_once(mode, runs, cancels):
    html = _dump(f'http://127.0.0.1:5210/tests/js/confirm-fixture.html?selftest={mode}')
    assert f'data-runs="{runs}"' in html
    assert f'data-cancels="{cancels}"' in html
    assert 'data-focus="confirm-cancel"' in html
    if mode == 'ok':
        assert 'GIF 16 帧（已从 99 帧调整）' in html
        assert '每帧 20 毫秒（已从 5 毫秒调整）' in html
        assert '5 积分' in html


if __name__ == '__main__':
    test_first_gate_lets_the_first_call_through_only()
    test_confirm_keeps_quote_sentence_and_shared_actions()
    if not CHROME:
        print('skip chrome interaction')
    else:
        for mode, runs, cancels in (('ok', '1', '0'), ('cancel', '0', '1'), ('escape', '0', '1')):
            test_confirm_click_and_escape_fire_once(mode, runs, cancels)
            print('pass', mode)
    print('ui controls batch ok')
