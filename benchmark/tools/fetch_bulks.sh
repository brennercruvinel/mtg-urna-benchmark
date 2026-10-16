#!/usr/bin/env sh
# fetch the scryfall bulks the card columns are built from, pinned to the
# files of 2026-10-16, and check each decompressed file against
# scalars/bulks.json. scryfall keeps only the latest bulk of each type at
# https://api.scryfall.com/bulk-data, so a pinned url answers 404 once a
# newer file replaces it; the sha256 is then the only way to know a later
# download is the same data.
#
#   benchmark/tools/fetch_bulks.sh [DIR]      default ${XDG_CACHE_HOME:-~/.cache}/urna/scryfall
set -eu
dir="${1:-${XDG_CACHE_HOME:-$HOME/.cache}/urna/scryfall}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
sums="$root/scalars/bulks.json"
mkdir -p "$dir"

fetch() {
  name="$1"; url="$2"
  if [ -f "$dir/$name.jsonl" ]; then
    printf "%s: present\n" "$name"
  else
    printf "%s: %s\n" "$name" "$url"
    curl -fsSL --retry 3 -o "$dir/$name.jsonl.gz" "$url"
    gunzip -f "$dir/$name.jsonl.gz"
  fi
  want="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$sums" "$name")"
  got="$(shasum -a 256 "$dir/$name.jsonl" | cut -d' ' -f1)"
  if [ "$want" != "$got" ]; then
    printf "%s: sha256 %s, scalars/bulks.json says %s (a newer bulk; the columns will differ)\n" "$name" "$got" "$want" >&2
    exit 1
  fi
  printf "%s: sha256 ok\n" "$name"
}

fetch oracle_cards https://data.scryfall.io/oracle-cards/oracle-cards-20261016090200.jsonl.gz
fetch rulings      https://data.scryfall.io/rulings/rulings-20261016090035.jsonl.gz
fetch oracle_tags  https://data.scryfall.io/oracle-tags/oracle-tags-20261016090036.jsonl.gz
fetch art_tags     https://data.scryfall.io/art-tags/art-tags-20261016090113.jsonl.gz
fetch all_cards    https://data.scryfall.io/all-cards/all-cards-20261016091845.jsonl.gz
