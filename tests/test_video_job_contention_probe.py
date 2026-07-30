from scripts.run_video_job_contention_probe import run_probe


def test_video_job_contention_probe_has_no_duplicate_claims_or_stale_leases() -> None:
    result = run_probe(jobs=32, workers=6, deadline_seconds=15)

    assert result["ok"] is True
    assert result["completed"] == 32
    assert result["duplicate_claims"] == 0
    assert result["active_leases"] == 0
    assert result["attempt_violations"] == 0
    assert result["error_count"] == 0
