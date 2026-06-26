from media_core.video_builder import _align_segment_durations_to_beats


def test_beat_alignment_only_extends_safe_boundaries():
    durations = [1.9, 2.0, 2.0]
    aligned = _align_segment_durations_to_beats(durations, bpm=120, max_extension=0.12)

    assert aligned[0] == 2.0
    assert aligned[1] == 2.0
    assert aligned[2] == 2.0
    assert sum(aligned) >= sum(durations)


def test_beat_alignment_skips_large_adjustments_and_last_segment():
    durations = [1.7, 2.0, 1.7]
    aligned = _align_segment_durations_to_beats(durations, bpm=120, max_extension=0.12)

    assert aligned == durations
