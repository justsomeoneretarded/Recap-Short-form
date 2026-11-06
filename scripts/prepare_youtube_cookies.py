"""Write the optional YOUTUBE_COOKIES secret to a private file and export YOUTUBE_COOKIE_FILE.

Mirrors Top10-Movies: the value must be a Netscape-format cookies.txt export (it starts with
'# Netscape HTTP Cookie File') containing youtube.com cookies. Never prints the contents.
"""
import os
from http.cookiejar import LoadError, MozillaCookieJar
from pathlib import Path

contents = os.environ.get("YOUTUBE_COOKIES", "").strip()
if not contents:
    print("No YOUTUBE_COOKIES secret: downloads run signed out (WARP + PO-token fallbacks still apply).")
    raise SystemExit(0)
path = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "youtube-cookies.txt"
path.unlink(missing_ok=True)
fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as stream:
    stream.write(contents + "\n")
try:
    jar = MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    if not any(c.domain.lstrip(".").endswith("youtube.com") for c in jar):
        raise LoadError("no youtube.com cookies")
except (LoadError, OSError, ValueError) as exc:
    path.unlink(missing_ok=True)
    print(f"::warning title=YOUTUBE_COOKIES ignored::Not a usable Netscape cookies.txt with youtube.com cookies ({exc}).")
    raise SystemExit(0)
with open(os.environ["GITHUB_ENV"], "a") as env:
    env.write(f"YOUTUBE_COOKIE_FILE={path}\n")
print(f"YouTube cookies configured ({sum(1 for _ in jar)} cookies).")
