#!/usr/bin/env python3
"""Host-only tests for AX56U applet and notification compatibility wiring."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests/ax56u"
ROUTER = ROOT / "release/src/router"


def main():
    source = (ROUTER / "rc/rc.c").read_text()
    start = source.index("int firmware_webs_update_main(int argc, char *argv[])\n{")
    end = source.index("\n}\n", start) + 3
    function = source[start:end]
    dispatch = source[source.index('{ "firmware_check",'):]
    assert '#if defined(RTCONFIG_CFGSYNC)\n\t{ "firmware_webs_update"' in dispatch
    assert 'firmware_webs_update_main(0, NULL);' in (ROUTER / "rc/services.c").read_text()
    assert 'OBJS += ax56u_legacy_consent.o' in (ROUTER / "shared/Makefile").read_text()
    event_makefile = ROOT / "release/src-rt-5.02axhnd.675x/bcmdrivers/broadcom/net/wl/impl69/main/components/apps/cevent_app/Makefile"
    assert '$(filter-out prebuilt/%,$(EXES))' in event_makefile.read_text()
    program = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static int flag, error, complete;
static void nvram_set(const char *name, const char *value) {
    if (!strcmp(name, "webs_state_flag")) { assert(!strcmp(value, "0")); flag = 1; }
    else if (!strcmp(name, "webs_state_error")) { assert(!strcmp(value, "1")); error = 1; }
    else if (!strcmp(name, "webs_state_update")) { assert(!strcmp(value, "1")); complete = 1; }
    else assert(0);
}
static void logmessage(const char *tag, const char *message) {
    assert(!strcmp(tag, "firmware")); assert(strstr(message, "unsupported"));
}
''' + function + r'''
int main(void) {
    assert(firmware_webs_update_main(0, NULL) == ENOTSUP);
    assert(flag && error && complete);
    puts("unsupported update applet: explicit error and completed failure state passed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="ax56u-host-tests-") as directory:
        path = Path(directory)
        (path / "applet.c").write_text(program)
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", str(path / "applet.c"), "-o", str(path / "applet")], check=True)
        subprocess.run([str(path / "applet")], check=True)
        subprocess.run([
            "cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-DRTAX56U",
            "-I" + str(TESTS / "compat_stubs"), str(TESTS / "legacy_consent.c"),
            str(ROUTER / "shared/ax56u_legacy_consent.c"), "-o", str(path / "consent"),
        ], check=True)
        subprocess.run([str(path / "consent")], check=True)


if __name__ == "__main__":
    main()
