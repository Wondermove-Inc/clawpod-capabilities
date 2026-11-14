#!/usr/bin/env bash
# Runs every example script against the installed FigCraft, renders each result and runs check_layout.py on it.
# Use it after FigCraft is updated, or to see what an example produces.
#   bash verify.sh [folder]     results go to the folder (default: a new temporary one); this folder is never written to
# Exit code 1 if a script fails or a layout check finds something.
src="$(cd "$(dirname "$0")" && pwd)" || exit 1
work="${1:-$(mktemp -d)}"; mkdir -p "$work" || exit 1
tar -C "$src" --exclude=./out --exclude=./enterprise -cf - . | tar -C "$work" -xf - || exit 1
cd "$work" || exit 1
mkdir -p out; fail=0
for f in */*.jsonl; do
  n=$(basename "$f" .jsonl); in=$(sed -n 's#^// in: ##p' "$f"); args=()
  if [ -n "$in" ]; then case "$in" in *.figcraft) args=(--in "$in");; *) args=(--in "out/$(basename "$in").figcraft");; esac; fi
  if o=$(figcraft-cli run "$f" "${args[@]}" --out "out/$n.figcraft" 2>&1); then
    figcraft-cli render "out/$n.figcraft" -o "out/$n.png" >/dev/null 2>&1
    c=$(python3 check_layout.py "out/$n.figcraft" 2>&1); rc=$?
    if [ $rc -eq 1 ]; then fail=1; echo "LOOK  $f"; echo "$c" | tail -n +2
    elif grep -q 'NOT CHECKED\|not on PATH' <<<"$c"; then echo "ok    $f   (layout not checked: $(echo "$c" | head -1 | cut -c1-160))"
    else echo "ok    $f   layout ok"; fi
  else fail=1; echo "FAIL  $f"; grep -E '"ok":false' <<<"$o" | cut -c1-400 | head -1; fi
done
echo "results: $work/out"
exit $fail
