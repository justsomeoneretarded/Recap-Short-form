#!/usr/bin/env bash
# Install rife-ncnn-vulkan (MIT) for true 60 fps frame interpolation on CPU and export its paths.
set -euo pipefail
DIR="${RUNNER_TEMP:-/tmp}/rife"
mkdir -p "$DIR"
auth=()
[ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
url="$(curl -fsSL --retry 3 "${auth[@]}" https://api.github.com/repos/nihui/rife-ncnn-vulkan/releases/latest |
       jq -r '[.assets[] | select(.name | test("ubuntu\\.zip$"))][0].browser_download_url')"
[ -n "$url" ] && [ "$url" != null ] || { echo "No rife-ncnn-vulkan Ubuntu release found"; exit 1; }
curl -fsSL --retry 3 -o "$DIR/rife.zip" "$url"
unzip -q -o "$DIR/rife.zip" -d "$DIR"
bin="$(find "$DIR" -type f -name rife-ncnn-vulkan | head -1)"
chmod +x "$bin"
model="$(find "$(dirname "$bin")" -maxdepth 1 -type d -name 'rife-v4*' | sort -V | tail -1)"
[ -n "$model" ] || { echo "No RIFE v4 model in the release"; exit 1; }
{ echo "SHORTS_RIFE_BIN=$bin"; echo "SHORTS_RIFE_MODEL=$model"; echo "SHORTS_RIFE_GPU=-1"; } >> "$GITHUB_ENV"
echo "RIFE ready: $(basename "$model")"
