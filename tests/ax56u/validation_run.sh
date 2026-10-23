#!/bin/sh
# Compile and execute only a host-side test, never a firmware executable.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/ax56u-validation.XXXXXX")
trap 'rm -f "$tmp/validation_helpers"; rmdir "$tmp"' EXIT HUP INT TERM
set -- -std=c99 -Wall -Wextra -Werror -pedantic
if [ "${VALIDATION_SANITIZE:-0}" = 1 ]; then
    set -- "$@" -fsanitize=address,undefined -fno-omit-frame-pointer -g
fi
"${CC:-cc}" "$@" \
    -I"$root/release/src/router/shared" \
    "$root/tests/ax56u/validation_helpers.c" -o "$tmp/validation_helpers"
"$tmp/validation_helpers"
