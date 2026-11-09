"""#721: non-WaveSpeed / unknown raw errors on the gen card map to friendly i18n; raw only in logs.

Mutation check (PR): temporarily change mapUnknownError / promptError / localizeError fallbacks
back to `return raw` / `return lines.join('\\n')` / `return msg` — these tests must fail.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)
GENERIC = {
    "zh": "这次生成没有完成，请稍后再试。",
    "en": "This generation didn't finish. Please try again.",
}
FAILED = {
    "zh": "任务没能完成，请检查输入后再试。",
    "en": "This job could not finish. Check the inputs and try again.",
}
BANNED = re.compile(
    r"wavespeedai|kie|控制台|后台|console|dashboard|生成记录|历史记录|Internal Error xyz|engine\.py|CUDA OOM|\[object Object\]",
    re.I,
)
RAW_SNIP = "Internal Error xyz"


@pytest.fixture(scope="module")
def js(tmp_path_factory):
    out = tmp_path_factory.mktemp("e721") / "e721.mjs"
    proc = subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.error721.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "OUT": str(out)},
    )
    if proc.returncode != 0:
        raise AssertionError(f"rolldown failed:\n{proc.stderr or proc.stdout}")
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_721_each_site_maps_to_friendly_copy(js, lang):
    assert js["bannedCheck"] is True, js.get("bannedHit")
    s = js[lang]
    assert s["generic"] == GENERIC[lang]
    assert s["failed"] == FAILED[lang]
    # wsBodyError raw string / message → generic
    assert s["bodyStr"] == GENERIC[lang] and RAW_SNIP not in s["bodyStr"]
    assert s["bodyMsg"] == GENERIC[lang]
    # tagged kinds unchanged
    assert s["bodyTagged"] == FAILED[lang]
    assert "tid-721" in s["bodyTimeoutId"] and ("任务编号" in s["bodyTimeoutId"] or "Task ID" in s["bodyTimeoutId"])
    # localizeError / errorText / mapUnknown
    assert s["locRaw"] == GENERIC[lang]
    assert s["locFailed"] == FAILED[lang] and RAW_SNIP not in s["locFailed"]  # no {0} embed
    assert s["locAllow"] == "mask file not found"
    assert s["locFriendly"] == FAILED[lang]
    assert s["errText"] == GENERIC[lang]
    assert s["mapped"] == GENERIC[lang]
    assert s["exec"] == GENERIC[lang]
    # promptError sites
    assert s["peNodes"] == GENERIC[lang]
    assert s["peQueue"] == FAILED[lang]
    assert s["peStatus"] == FAILED[lang]
    assert "Too many" in s["peTagged"] or "请求太多" in s["peTagged"]
    for k, v in s.items():
        if isinstance(v, str) and k != "locAllow":
            assert not BANNED.search(v), (lang, k, v)


def test_721_generic_in_locales_and_de_vendor_suite():
    for lang, text in GENERIC.items():
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text(encoding="utf-8"))
        assert loc["wsErr.generic"] == text
        assert not re.search(r"wavespeed|kie|控制台|后台|console|dashboard|生成记录|历史记录", text, re.I)
    # jobs.wsFailed no longer embeds {0}
    zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    assert "{0}" not in zh["jobs.wsFailed"] and "{0}" not in en["jobs.wsFailed"]
    assert zh["jobs.wsFailed"] == FAILED["zh"] and en["jobs.wsFailed"] == FAILED["en"]


def test_721_source_sites_do_not_pass_through_raw():
    jobs = (ROOT / "src/jobs.ts").read_text(encoding="utf-8")
    comfy = (ROOT / "src/comfy.ts").read_text(encoding="utf-8")
    ws = (ROOT / "src/wsErrors.ts").read_text(encoding="utf-8")
    assert "mapUnknownError" in jobs and "wsErr.failed" in jobs
    assert "t('jobs.wsFailed'" not in jobs  # no embed path
    assert "return t('wsErr.failed')" in jobs  # WaveSpeed task failed → fixed copy
    assert "return mapUnknownError(msg)" in jobs
    assert "t('wsErr.generic')" in comfy and "t('wsErr.failed')" in comfy
    assert "logRawGenError(lines.join" in comfy
    assert "mapUnknownError(raw)" in comfy  # execution_error path
    assert "OWN_ERROR_ALLOWLIST" in ws and "wsErr.generic" in ws
    assert "console.warn('[gen] raw error:" in ws
    # mirrors in tests/js/error_721.ts must stay aligned with these call sites
    mirror = (ROOT / "tests/js/error_721.ts").read_text(encoding="utf-8")
    assert "t('wsErr.generic')" in mirror and "t('wsErr.failed')" in mirror
    assert "mapUnknownError" in mirror
