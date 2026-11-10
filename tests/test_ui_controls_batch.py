"""First-batch button / confirm interaction checks. No price API and no provider call."""

import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


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


@pytest.fixture(scope="module")
def confirm_fixture_server():
    """Serve tests/js/confirm-fixture.html via the committed Vite config (port 5210)."""
    vite = ROOT / "node_modules" / ".bin" / "vite"
    if not vite.is_file():
        pytest.fail("needs node + npm install (run via scripts/gate.sh); no skip allowed")
    log = Path(tempfile.mkdtemp(prefix="confirm-vite-")) / "vite.log"
    proc = subprocess.Popen(
        [str(vite), "--config", str(ROOT / "tests/js/confirm-fixture.vite.ts")],
        cwd=ROOT,
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
    )
    url = "http://127.0.0.1:5210/tests/js/confirm-fixture.html"
    try:
        deadline = time.time() + 40
        last = ""
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"confirm fixture vite exited {proc.returncode}\n{log.read_text(errors='replace')[-2000:]}")
            try:
                with urllib.request.urlopen(url, timeout=1) as res:
                    if res.status == 200:
                        break
            except OSError as exc:
                last = str(exc)
            time.sleep(0.2)
        else:
            pytest.fail(f"confirm fixture vite did not listen ({last})\n{log.read_text(errors='replace')[-2000:]}")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _page_html(url: str) -> str:
    """Load the Vite fixture and wait for SelfTest to publish data-ready.

    Chrome --dump-dom often returns an empty string for this ESM page; Playwright
    waits until the dialog has actually run.
    """
    import playwright.sync_api as pw  # no importorskip: must run on the gate machine
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel='chrome', args=['--no-sandbox'])
        except Exception:
            browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page()
        try:
            # cold Vite start pre-bundles deps on the first request (seen >30s on the gate box); allow it
            page.goto(url, wait_until='domcontentloaded', timeout=120000)
            page.wait_for_function("() => document.documentElement.dataset.ready === '1'", timeout=20000)
            return page.content()
        finally:
            browser.close()


@pytest.mark.parametrize('mode,runs,cancels', [('ok', '1', '0'), ('cancel', '0', '1'), ('escape', '0', '1')])
def test_confirm_click_and_escape_fire_once(mode, runs, cancels, confirm_fixture_server):
    html = _page_html(f'{confirm_fixture_server}?selftest={mode}')
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
    print('chrome selftest: run via pytest so confirm_fixture_server starts Vite on :5210')
    print('ui controls batch source checks ok')
