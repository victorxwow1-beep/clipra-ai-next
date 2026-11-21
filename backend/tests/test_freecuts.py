from clipra.freecuts import propose_drafts


def test_local_drafts_do_not_claim_semantic_ai():
    cues = [{"time": 35, "activity_score": .95}, {"time": 90, "activity_score": .78}]
    cuts = propose_drafts(150, cues, 3, 22)
    assert cuts
    assert all(x["origin"] == "signal_draft" for x in cuts)
    assert all(x["confidence"] is None for x in cuts)
    assert all(0 <= x["start"] < x["end"] <= 150 for x in cuts)
    assert all("review" in x["reason"].lower() for x in cuts)


def test_local_drafts_work_without_activity():
    cuts = propose_drafts(120, [], 4, 20)
    assert cuts
    assert all("fallback" in x["reason"].lower() for x in cuts)


def test_draft_length_is_bounded():
    cuts = propose_drafts(8, [{"time": 5, "activity_score": 1.0}], 4, 22)
    assert cuts
    assert all(x["end"] <= 8 for x in cuts)


def test_bad_duration_and_bad_peaks_are_ignored():
    assert propose_drafts(0, [], 5) == []
    assert propose_drafts(90, [{"time": "no", "activity_score": 1}, {}], 2)


def test_max_clips_is_bounded():
    peaks = [{"time": i * 38 + 10, "activity_score": 1.0} for i in range(30)]
    cuts = propose_drafts(1200, peaks, 999, 20)
    assert len(cuts) <= 12
