"""#322: Agent (quiet) generation results auto-follow the viewport; manual gen stays #307 (select only)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = (ROOT / 'src/jobs.ts').read_text()


def test_agent_quiet_follows_latest_result():
    sel = JOBS.split('export function selectResults')[1].split('export function followResultViewport')[0]
    assert 'holder.meta.quiet' in sel
    assert 'ids[ids.length - 1]' in sel
    assert 'followResultViewport(editor)' in sel
    # multi-result: only the latest is selected, not ...ids on the quiet path
    quiet_branch = sel.split('if (holder.meta.quiet)')[1].split('editor.select(...ids)')[0]
    assert 'editor.select(...ids)' not in quiet_branch
    assert 'ids[ids.length - 1]' in quiet_branch


def test_follow_skips_mid_pan_pinch():
    body = JOBS.split('export function followResultViewport')[1].split('async function keepPartial')[0]
    assert "getCameraState() !== 'idle'" in body
    assert 'getIsPanning()' in body
    assert 'isPinching' in body
    assert 'zoomToSelection' in body


def test_manual_gen_still_select_only_no_inline_zoom():
    # #307 product: non-quiet path must not zoom inside selectResults
    sel = JOBS.split('export function selectResults')[1].split('export function followResultViewport')[0]
    assert 'zoomToSelection' not in sel
    assert 'editor.select(...ids)' in sel
