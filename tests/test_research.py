import json

import pytest

from shorts_pipeline import research as r


class FakeResponse:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body = status, body
        self.text = text or (json.dumps(body) if body is not None else "")

    def json(self):
        return self._body


class FakeSession:
    """Routes requests to canned responses by URL substring; records calls."""

    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get("params"), kwargs.get("json")))
        for key, response in self.routes:
            if key in url and (not callable(response) or True):
                return response(method, url, kwargs) if callable(response) else response
        return FakeResponse(404, {"error": "not routed"})


WIKI_EXTRACT = ("Nobody is a 2021 American action thriller film.\n\n== Plot ==\n"
                "Hutch Mansell is an auditor whose house is robbed.\n\nHe fights men on a bus.\n\n== Cast ==\nBob")


def wiki(method, url, kwargs):
    params = kwargs.get("params") or {}
    if params.get("list") == "search":
        return FakeResponse(200, {"query": {"search": [{"title": "Nobody (2021 film)"}]}})
    return FakeResponse(200, {"query": {"pages": {"1": {"extract": WIKI_EXTRACT}}}})


DETAILS = {
    "id": 615457, "imdb_id": "tt7888964", "title": "Nobody", "original_title": "Nobody",
    "release_date": "2021-03-18", "runtime": 92, "overview": "An underestimated dad.", "genres": [{"name": "Action"}],
    "keywords": {"keywords": [{"name": "bus"}]},
    "credits": {"cast": [{"name": "Bob Odenkirk", "character": "Hutch", "order": 0, "profile_path": "/b.jpg"}],
                "crew": [{"name": "Ilya Naishuller", "job": "Director"}]},
    "videos": {"results": [
        {"key": "clip1", "name": "Bus Fight", "type": "Clip", "site": "YouTube", "official": True},
        {"key": "trl1", "name": "Trailer", "type": "Trailer", "site": "YouTube", "official": True},
        {"key": "bts1", "name": "Making of", "type": "Behind the Scenes", "site": "YouTube"}]},
    "images": {"backdrops": [{"file_path": "/x.jpg"}]}, "poster_path": "/p.jpg",
}


def routes(subtitle_status=200):
    return [
        ("/search/movie", FakeResponse(200, {"results": [
            {"id": 1, "title": "Nobody", "release_date": "2017-01-01"},
            {"id": 615457, "title": "Nobody", "release_date": "2021-03-18"}]})),
        ("/movie/615457", FakeResponse(200, DETAILS)),
        ("wikipedia.org", wiki),
        ("/subtitles", FakeResponse(200, {"data": [
            {"attributes": {"download_count": 900, "machine_translated": True, "files": [{"file_id": 9}]}},
            {"attributes": {"download_count": 500, "release": "Nobody.2021.1080p", "files": [{"file_id": 7}]}}]})),
        ("/download", FakeResponse(subtitle_status, {"link": "https://dl.example/file.srt", "remaining": 4})),
        ("dl.example", FakeResponse(200, None, text="1\n00:00:01,000 --> 00:00:02,000\nHello there.\n" * 200)),
    ]


@pytest.mark.parametrize("text,title,year", [
    ("John Wick: Chapter 3 (2019)", "John Wick: Chapter 3", 2019),
    ("Nobody 2021", "Nobody 2021", None),  # bare number: full title searched first
    ("Prisoners", "Prisoners", None),
    ("  Blade   Runner 2049  ", "Blade Runner 2049", None),
])
def test_parse_movie(text, title, year):
    query = r.parse_movie(text)
    assert (query.title, query.year) == (title, year)


def test_bare_trailing_year_falls_back_to_split(tmp_path):
    assert r.parse_movie("Nobody 2021").split == ("Nobody", 2021)
    result = r.research("Nobody 2021", tmp_path, http=r.Http(FakeSession(routes()), pause=0), tmdb_token="t",
                        subtitles_key="")
    assert result["movie"]["tmdb_id"] == 615457


def test_parse_movie_rejects_empty():
    with pytest.raises(ValueError):
        r.parse_movie("   ")


def test_year_picks_the_right_namesake():
    results = [{"id": 1, "title": "Nobody", "release_date": "2017-05-01"},
               {"id": 2, "title": "Nobody", "release_date": "2021-03-18"}]
    assert r.choose_tmdb_result(results, r.MovieQuery("Nobody", 2021))["id"] == 2
    assert r.choose_tmdb_result(results, r.MovieQuery("Nobody", 2022))["id"] == 2  # festival/regional year
    assert r.choose_tmdb_result(results, r.MovieQuery("Nobody", 1990)) is None
    assert r.choose_tmdb_result(results, r.MovieQuery("Nobody"))["id"] == 1  # TMDB order without a year


def test_exact_title_beats_a_shorter_namesake():
    results = [{"id": 1, "title": "Blade Runner", "release_date": "1982-06-25"},
               {"id": 2, "title": "Blade Runner 2049", "release_date": "2017-10-04"}]
    assert r.choose_tmdb_result(results, r.parse_movie("Blade Runner 2049"))["id"] == 2


def test_plot_section_extracts_only_the_plot():
    assert r.plot_section(WIKI_EXTRACT) == "Hutch Mansell is an auditor whose house is robbed.\n\nHe fights men on a bus."


def test_subtitle_choice_prefers_human_over_popular_machine_translation():
    chosen = r.choose_subtitle(routes()[3][1].json()["data"])
    assert chosen["attributes"]["files"][0]["file_id"] == 7


def test_research_end_to_end_with_cache(tmp_path):
    session = FakeSession(routes())
    result = r.research("Nobody (2021)", tmp_path, http=r.Http(session, pause=0),
                        tmdb_token="t", subtitles_key="k")
    movie = result["movie"]
    assert movie["tmdb_id"] == 615457 and movie["imdb_id"] == "tt7888964"
    assert [c["key"] for c in movie["clips"]] == ["clip1"]  # trailers and behind-the-scenes excluded
    assert movie["cast"][0]["photo"].endswith("/b.jpg")
    assert result["wikipedia"]["words"] > 5 and "Hutch" in open(result["plot_path"]).read()
    assert result["subtitles"]["remaining_quota"] == 4 and result["warnings"] == []
    downloads = sum(1 for c in session.calls if "/download" in c[1])
    again = r.research("Nobody (2021)", tmp_path, http=r.Http(session, pause=0), tmdb_token="t", subtitles_key="k")
    assert again["subtitles"]["path"] == result["subtitles"]["path"]
    assert sum(1 for c in session.calls if "/download" in c[1]) == downloads  # cached: no second download


def test_missing_subtitles_is_a_warning_not_a_failure(tmp_path):
    result = r.research("Nobody (2021)", tmp_path, http=r.Http(FakeSession(routes(subtitle_status=406)), pause=0),
                        tmdb_token="t", subtitles_key="k")
    assert "path" not in result["subtitles"] and result["warnings"]


def test_missing_tmdb_token_is_a_clear_error(tmp_path):
    with pytest.raises(r.ResearchError, match="TMDB_READ_TOKEN"):
        r.research("Nobody", tmp_path, http=r.Http(FakeSession([]), pause=0), tmdb_token="", subtitles_key="")
