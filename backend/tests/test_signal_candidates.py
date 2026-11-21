"""Real signal extraction is cheap prefiltering, NEVER semantic highlights."""
from clipra.signals import discover_signals,select_analysis_windows


def test_short_source_gets_full_semantic_coverage():
    windows,coverage=select_analysis_windows(60,[],4)
    assert windows==[0.]
    assert coverage['full_coverage'] is True


def test_long_source_gets_bounded_partial_windows():
    windows,coverage=select_analysis_windows(1800,[{'time':800,'activity_score':.9},{'time':200,'activity_score':.8}],2)
    assert len(windows)==2 and all(0<=x<=1710 for x in windows)
    assert coverage['full_coverage'] is False
    assert 'semantic' in coverage['selection']


def test_audio_visual_candidate_discovery_is_not_semantic(source):
    cues=discover_signals(source,60,max_events=5)
    assert len(cues)<=5
    for cue in cues:
        assert 0 <= cue['time'] <=60
        assert 0 <= cue['activity_score'] <=1
        assert 'signals' in cue
        assert 'title' not in cue and 'event' not in cue