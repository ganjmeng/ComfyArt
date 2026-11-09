"""Refresh recovery R02/R05/R06/R09/R10 source contract (no live API)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY = (ROOT / "src/comfy.ts").read_text(encoding="utf-8")
JOBS = (ROOT / "src/jobs.ts").read_text(encoding="utf-8")
GEN = (ROOT / "src/shapes/GeneratorShape.tsx").read_text(encoding="utf-8")
ZH = (ROOT / "src/locales/zh.json").read_text(encoding="utf-8")
EN = (ROOT / "src/locales/en.json").read_text(encoding="utf-8")


def test_locale_keys_present():
    for blob in (ZH, EN):
        assert "jobs.queryingStatus" in blob
        assert "jobs.resultPendingShort" in blob
        assert "jobs.resultPendingHint" in blob
    assert "正在查询任务状态" in ZH
    assert "结果待确认" in ZH
    assert "暂时无法确认处理结果，请勿重复提交" in ZH


def test_history_miss_and_http_use_uncertain_not_lost():
    assert "class UncertainResultError" in COMFY
    assert "throw new UncertainResultError" in COMFY
    # Must not throw jobs.lost from the miss counter path anymore
    assert "throw new Error(t('jobs.lost'))" not in COMFY
    assert "if (!res.ok) throw new UncertainResultError" in COMFY


def test_resume_skips_pending_without_id_and_guards_late():
    assert "if (!job.id) continue" in JOBS
    assert "if (!job.id) return" in JOBS
    assert "const terminals = new Map" in JOBS
    assert "ignore-ok-after-" in JOBS
    assert "ignore-error-after-ok" in JOBS
    assert "phase: job.phase ?? 'querying'" in JOBS
    assert "uncertain: true" in JOBS
    assert "pending: true" in JOBS


def test_generator_shows_querying_and_pending_status_not_error_red():
    assert "jobs.queryingStatus" in GEN
    assert "ca-gen-card__status" in GEN
    assert "data-pending" in GEN
    assert "data-querying" in GEN
    # pending copy uses status role, not the error alert class for pending
    assert 'role="status"' in GEN
    assert "jobs.resultPendingShort" in GEN
