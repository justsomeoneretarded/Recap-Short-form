"""Validate the four Generate Shorts inputs before any model download.

User text arrives through the SHORTS_INPUTS environment variable (never interpolated into shell
code) and is written back as validated step outputs: movie, narrator, length, speech_model.
"""
import json
import os
import re
import sys

NARRATORS = {"warguy", "kit-laser", "female"}
MODELS = {"original", "turbo", "nano"}

data = json.loads(os.environ.get("SHORTS_INPUTS") or "{}")
movie = " ".join(str(data.get("movie", "")).split())
errors = []
if not movie or len(movie) > 120 or not re.search(r"[A-Za-z0-9]", movie):
    errors.append("Movie: enter a movie name (optionally with its year), e.g. 'Nobody (2021)'.")
if any(ch in movie for ch in "\n\r`$<>|;"):
    errors.append("Movie: remove special characters such as ` $ < > | ;")
narrator = str(data.get("narrator", "warguy")).strip().lower()
if narrator not in NARRATORS:
    errors.append(f"Narrator must be one of {sorted(NARRATORS)}.")
try:
    length = int(float(str(data.get("length", "150")).strip()))
except ValueError:
    length = -1
if not 30 <= length <= 180:
    errors.append("Length must be between 30 and 180 seconds.")
speech = str(data.get("speech_model", "original")).strip().lower()
if speech not in MODELS:
    errors.append(f"Speech model must be one of {sorted(MODELS)}.")
if errors:
    for error in errors:
        print(f"::error title=Invalid input::{error}")
    sys.exit(1)
values = {"movie": movie, "narrator": narrator, "length": str(length), "speech_model": speech}
print(json.dumps(values))
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        for key, value in values.items():
            out.write(f"{key}={value}\n")
