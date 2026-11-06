import random

from shorts_pipeline.locate import MovieTranscript, locate_captions, parse_cues, timed_words, tokens


def _stamp(seconds: float, comma: bool = True) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    sep = "," if comma else "."
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round(s * 1000)) % 1000:03d}"


def _movie(lines: int = 600, seed: int = 3):
    rng = random.Random(seed)
    vocab = ("the a he she gun time money car run stop wait never always where why you me we they "
             "kill find book doctor clock six hour bounty hotel rule dog suit table ring").split()
    cues = []
    for i in range(lines):
        text = " ".join(rng.choice(vocab) for _ in range(rng.randint(4, 9)))
        start = i * 3.1
        cues.append((start, start + 2.5, text))
    srt = "\n".join(f"{i + 1}\n{_stamp(a)} --> {_stamp(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues))
    return cues, srt


def _rolling_vtt(cues):
    """YouTube auto-caption style: each cue repeats the previous line, plus 10 ms hand-over cues."""
    out, previous = ["WEBVTT", ""], ""
    for k, (_, _, text) in enumerate(cues):
        start = k * 3.1
        out += [f"{_stamp(start, False)} --> {_stamp(start + 2.5, False)}", f"{previous}\n{text}".strip(), ""]
        out += [f"{_stamp(start + 2.5, False)} --> {_stamp(start + 2.51, False)}", text, ""]
        previous = text
    return "\n".join(out)


def test_tokens_drop_sound_tags_and_speaker_labels():
    assert tokens("[GUNSHOT] JOHN: I still have <i>time</i>. ♪ music ♪") == ["i", "still", "have", "time"]


def test_rolling_captions_are_not_double_counted():
    cues, _ = _movie(20)
    words = timed_words(parse_cues(_rolling_vtt(cues[:5])))
    assert len(words) == sum(len(t.split()) for _, _, t in cues[:5])


def test_clip_is_placed_at_its_movie_time_with_context():
    cues, srt = _movie()
    movie = MovieTranscript.from_subtitles(srt)
    result = locate_captions(movie, _rolling_vtt(cues[300:330]))
    assert result["matched"] and result["confidence"] == "high"
    assert abs(result["movie_start"] - 300 * 3.1) <= 2.5
    assert result["context"]["before"] and result["context"]["after"]


def test_too_little_dialogue_is_reported_not_guessed():
    cues, srt = _movie()
    movie = MovieTranscript.from_subtitles(srt)
    result = locate_captions(movie, "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n[EXPLOSION]\n")
    assert not result["matched"] and result["reason"] == "too little dialogue"


def test_unrelated_dialogue_does_not_match():
    _, srt = _movie(seed=3)
    other, _ = _movie(40, seed=99)
    movie = MovieTranscript.from_subtitles(srt)
    assert not locate_captions(movie, _rolling_vtt(other))["matched"]
