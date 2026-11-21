#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/tmp/clipra_real_highbit_35s.mp4}"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i 'testsrc2=size=1280x720:rate=30' \
  -f lavfi -i 'sine=frequency=650:sample_rate=48000' -t 35 \
  -c:v libx264 -preset ultrafast -crf 0 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=size,duration -of default=noprint_wrappers=1 "$OUT"