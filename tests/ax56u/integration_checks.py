#!/usr/bin/env python3
"""Host-only checks for AX56U compatibility wiring in the 3006 source tree."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests/ax56u"
ROUTER = ROOT / "release/src/router"
HOST_CC = os.environ.get("CC", "cc")
HOST_CFLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror"]
if os.environ.get("VALIDATION_SANITIZE") == "1":
    HOST_CFLAGS += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g"]


def check_source_wiring():
    qos = (ROUTER / "rc/qos.c").read_text()
    assert qos.count("ax56u_qos_record(p)") == 2
    assert qos.count("ax56u_bw_address(&addr_type") == 2
    assert "ax56u_ifname(get_wan_ifname(wan_primary_ifunit()))" in qos
    assert "ax56u_qos_rate(nvram_safe_get(strcat_r(wlv, \"_bw_dl\", tmp)))" in qos
    assert qos.count("#ifndef RTAX56U\n\t\tif (*dlc == '\\0' || !isNumber(dlc)") == 2

    ipsec = (ROUTER / "rc/rc_ipsec.c").read_text()
    for validator in ("ax56u_device_cn(value)", "ax56u_dns_name(value)", "ax56u_ipv4(value)", "ax56u_uint(value, 36500"):
        assert validator in ipsec
    assert 'if (fclose(fp) != 0) return;' in ipsec

    rc = (ROUTER / "rc/rc.c").read_text()
    stub = rc[rc.index("int firmware_webs_update_main(int argc, char *argv[])"):]
    stub = stub[:stub.index("\n}") + 2]
    assert "unsupported on this RT-AX56U build" in stub
    assert "return ENOTSUP;" in stub
    assert '"webs_state_error", "1"' in stub
    assert "firmware_webs_update_main(0, NULL);" in (ROUTER / "rc/services.c").read_text()

    rc_make = (ROUTER / "rc/Makefile").read_text()
    assert "qos.o rc_ipsec.o: $(TOP)/shared/ax56u_compat_validation.h" in rc_make
    shared_make = (ROUTER / "shared/Makefile").read_text()
    assert "OBJS += ax56u_legacy_consent.o ax56u_compat_runtime.o" in shared_make
    uqmi_make = (ROUTER / "uqmi/Makefile").read_text()
    assert "ifneq ($(strip $(ASUSWRT_BRCM_SDK_VERSION)),)" in uqmi_make
    assert "CFLAGS += -I$(LIBUBOX) -I$(LIBUBOX)/.." in uqmi_make
    netstat_nat_make = (ROUTER / "netstat-nat/GNUmakefile").read_text()
    assert "-std=gnu11" in netstat_nat_make
    assert "-std=c17" not in netstat_nat_make
    assert "$(filter-out prebuilt/%,$(EXES))" in (
        ROOT / "release/src-rt-5.02axhnd.675x/bcmdrivers/broadcom/net/wl/impl69/main/components/apps/cevent_app/Makefile"
    ).read_text()

    platform_make = (ROOT / "release/src-rt/Makefile").read_text()
    assert 'if [ "$(TPVPN)" = "n" ] || [ "$(BUILD_NAME)" = "RT-AX56U" ]; then' in platform_make
    assert 'echo "# RTCONFIG_NBR_RPT is not set"' in platform_make
    assert platform_make.index('$(call platformRouterOptions, $(1))') < platform_make.index(
        'echo "# RTCONFIG_NBR_RPT is not set"'
    )
    amas_lldpd = (ROUTER / "rc/services.c").read_text()
    assert "#ifdef RTAX56U\n\t\t\t\tif (is_router_mode() || access_point_mode())\n#else\n\t\t\t\tif (IS_CAP())" in amas_lldpd
    httpd_web = (ROUTER / "httpd/web.c").read_text()
    assert re.search(
        r"#ifdef RTCONFIG_MULTILAN_CFG\s+#define NVRAM_MODIFIED_SDN_BIT\s+256\s+"
        r"static int set_sdn_nvram",
        httpd_web,
    )
    assert "#ifdef RTCONFIG_SCHED_V2\n#if defined(RTCONFIG_LED_SCHED)" in httpd_web
    assert "#endif\n#endif /* RTCONFIG_SCHED_V2 */\n#ifdef RTCONFIG_MULTILAN_CFG\n\n#ifdef RTCONFIG_SCHED_V2\nint get_apx_wifi_sched_on" in httpd_web
    assert "#ifndef RTAX56U\n\t\t\t\tif(!check_apply_nvram_lan_only(name))" in httpd_web
    assert '#ifdef RTAX56U\n\t{ "wps_info_5g", ej_wps_info},' in httpd_web
    assert '#ifdef RTCONFIG_HAS_5G_2\n\t{ "wps_info_5g_2", ej_wps_info_5g_2},' in httpd_web
    assert '#if defined(RTCONFIG_HAS_6G_2)\n\t{ "chanspecs_6g_2", ej_wl_chanspecs_6g_2},' in httpd_web
    assert '#ifndef RTAX56U\n\t{ "hw_accel_status", ej_hw_accel_status },' in httpd_web
    assert '#if defined(RTCONFIG_BWDPI) && !defined(RTAX56U)\n\tbwdpi_cgi_mon_to_json' in httpd_web
    web_am = (ROUTER / "httpd/sysdeps/web-broadcom-am.c").read_text()
    assert "webswrite(" not in web_am
    init = (ROUTER / "rc/init.c").read_text()
    assert "#ifndef RTAX56U\n\tchar wifi_gen[16] = {0};" in init
    assert "#ifndef RTAX56U\n\t/* set wifi generation in misc info */" in init

    # The AX56U has MLO disabled and ships no libnmpapi prebuilt. Keep the
    # dependency limited to MLO-enabled builds wherever it is linked.
    nmpapi_makefiles = (
        "cfg_mnt/Makefile", "httpd/Makefile", "iwevent/Makefile",
        "libwebapi/Makefile", "networkmap/Makefile", "rc/Makefile", "wlceventd/Makefile",
        "aws-iot/src/Makefile", "uploader/src/Makefile",
    )
    for name in nmpapi_makefiles:
        makefile = (ROUTER / name).read_text()
        links = 0
        conditions = []
        for line in makefile.splitlines():
            stripped = line.strip()
            if re.match(r"^(?:ifeq|ifneq|ifdef|ifndef)\b", stripped):
                conditions.append(stripped)
            if "-lnmpapi" in line and not stripped.startswith("#"):
                links += 1
                assert any("RTCONFIG_MLO" in condition for condition in conditions), name
            if stripped.startswith("endif") and conditions:
                conditions.pop()
        assert links > 0, name
        assert "ifeq ($(RTCONFIG_MLO),y)" in makefile, name
    router_make = (ROUTER / "Makefile").read_text()
    assert "if [ -f libcap-ng/src/.libs/libdrop_ambient.so.0.0.0 ]; then" in router_make
    assert "obj-$(RTCONFIG_MLO) += nmp-api" in router_make
    assert "networkmap: $(if $(RTCONFIG_MLO),nmp-api)" in router_make
    assert "networkmap-install: $(if $(RTCONFIG_MLO),nmp-api-install)" in router_make
    assert "$(if $(RTCONFIG_DMALLOC),dmalloc) $(if $(RTCONFIG_MLO),nmp-api)" in router_make
    networkmap_make = (ROUTER / "networkmap/Makefile").read_text()
    nmp_install = networkmap_make.index("install -D api/$(NMP_API_SO)")
    assert "ifeq ($(RTCONFIG_MLO),y)" in networkmap_make[:nmp_install]

    httpd = (ROUTER / "httpd/web.c").read_text()
    conditions = []
    for line in httpd.splitlines():
        stripped = line.strip()
        if stripped.startswith(("#if ", "#ifdef ", "#ifndef ")):
            conditions.append(stripped)
        elif stripped.startswith("#endif"):
            if conditions:
                conditions.pop()
        if "nvram_modify_log(" in line or "handle_nvram_modify_log(" in line:
            assert any("!defined(RTAX56U)" in condition for condition in conditions)

    # The 3006 build intentionally does not restore either absent API hook.
    assert "httpd_reject_url" not in (ROUTER / "httpd/httpd.c").read_text()

    awsiot = (ROUTER / "aws-iot/src/awsiot.c").read_text()
    assert "#ifndef RTAX56U\n            if (strncmp(system_action, AWSIOT_ACTION_UPDATE_PPVERSION" in awsiot
    assert "#ifndef RTAX56U\n                char from_service[10] = {0};" in awsiot
    assert "set_ASUS_privacy_policy(\"1\", \"0\", from_service);\n#endif" in awsiot


def check_update_applet():
    source = (ROUTER / "rc/rc.c").read_text()
    start = source.index("int firmware_webs_update_main(int argc, char *argv[])\n{")
    end = source.index("\n}\n", start) + 3
    function = source[start:end]
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
    puts("unsupported mesh-update applet passed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="ax56u-host-tests-") as directory:
        path = Path(directory)
        (path / "applet.c").write_text(program)
        subprocess.run([HOST_CC, *HOST_CFLAGS, str(path / "applet.c"), "-o", str(path / "applet")], check=True)
        subprocess.run([str(path / "applet")], check=True)
        subprocess.run([
            HOST_CC, *HOST_CFLAGS, "-DRTAX56U",
            "-I" + str(TESTS / "compat_stubs"), str(TESTS / "legacy_consent.c"),
            str(ROUTER / "shared/ax56u_legacy_consent.c"), "-o", str(path / "consent"),
        ], check=True)
        subprocess.run([str(path / "consent")], check=True)


def check_safe_command_compat():
    with tempfile.TemporaryDirectory(prefix="ax56u-host-tests-") as directory:
        executable = Path(directory) / "safe-command"
        subprocess.run([
            HOST_CC, *HOST_CFLAGS, "-DRTAX56U",
            str(TESTS / "safe_command.c"),
            str(ROUTER / "shared/ax56u_compat_runtime.c"), "-o", str(executable),
        ], check=True)
        (Path(directory) / "ethswctl").symlink_to(executable)
        environment = os.environ.copy()
        environment["PATH"] = directory + os.pathsep + environment.get("PATH", "")
        subprocess.run([str(executable), str(Path(directory) / "output")], env=environment, check=True)


def check_dslite_local_address():
    services = (ROUTER / "rc/services.c").read_text()
    tunnel = services[services.index("void start_s46_tunnel(int unit)"):]
    branch = tunnel[tunnel.index("\tcase WAN_DSLITE:"):tunnel.index("\n\tdefault:")]
    misc = (ROUTER / "shared/misc.c").read_text()
    start = misc.index("const char *ipv6_router_address_by_unit(")
    helper = misc[start:misc.index("\n}\n", start) + 3]
    # Exercise the actual source-owned address helper and DS-Lite branch, not
    # a reimplementation. No network commands or target binaries are executed.
    program = r'''
#define _DEFAULT_SOURCE
#include <arpa/inet.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
enum { WAN_DSLITE = 1, IPV6_NATIVE_DHCP = 2, IPV6_MANUAL = 3 };
static const char *delegated, *router, *ra;
static char selected[INET6_ADDRSTRLEN];
static int service, selected_ok, expected_unit, ra_reads;
char *ipv6_nvname_by_unit(const char *name, int unit) {
    assert(unit == expected_unit);
    return (char *)name;
}
char *nvram_get(const char *name) {
    if (!strcmp(name, "ipv6_prefix")) return (char *)delegated;
    if (!strcmp(name, "ipv6_rtr_addr")) return (char *)router;
    if (!strcmp(name, "ipv6_ra_addr")) { ++ra_reads; return (char *)ra; }
    if (!strcmp(name, "ipv6_s46_b4addr")) return "192.0.0.2";
    if (!strcmp(name, "ipv6_s46_aftr_addr")) return "2001:db8:ffff::1";
    assert(0); return NULL;
}
char *nvram_safe_get(const char *name) {
    char *value = nvram_get(name);
    return value ? value : "";
}
int get_ipv6_service_by_unit(int unit) {
    assert(unit == expected_unit);
    return service;
}
void logmessage(const char *tag, const char *message) {
    assert(!strcmp(tag, "dslite"));
    assert(strstr(message, "IPv6"));
}
''' + helper + r'''
static void select_local(int unit) {
    char ipaddr[INET_ADDRSTRLEN], AFTR[INET6_ADDRSTRLEN], local[INET6_ADDRSTRLEN];
    switch (WAN_DSLITE) {
''' + branch + r'''
    }
    snprintf(selected, sizeof(selected), "%s", local);
    selected_ok = 1;
}
static void check(const char *prefix, const char *rtr, const char *ra_addr,
                  int mode, const char *expected) {
    delegated = prefix; router = rtr; ra = ra_addr; service = mode;
    selected_ok = 0; selected[0] = '\0'; ra_reads = 0;
    select_local(expected_unit);
    assert(selected_ok == (expected != NULL));
    if (expected) assert(!strcmp(selected, expected));
    if (mode == IPV6_NATIVE_DHCP) assert(ra_reads == 0);
}
int main(void) {
    for (expected_unit = 0; expected_unit < 2; ++expected_unit) {
        check("2001:db8:1234:5600::", "", "", IPV6_NATIVE_DHCP, "2001:db8:1234:5600::1");
        check("2001:db8:1234:5600::", "", "2001:db8:ffff::2", IPV6_NATIVE_DHCP, "2001:db8:1234:5600::1");
        check("2001:db8:1234:5600::", "2001:db8:1234:5600::42", "", IPV6_NATIVE_DHCP, "2001:db8:1234:5600::42");
        check("fd12:3456:789a::", "", "", IPV6_NATIVE_DHCP, "fd12:3456:789a::1");
        check("", "", "2001:db8:ffff::2", IPV6_NATIVE_DHCP, NULL);
        check("invalid", "", "2001:db8:ffff::2", IPV6_NATIVE_DHCP, NULL);
        check("fe80::", "", "", IPV6_NATIVE_DHCP, NULL);
        check("ff02::", "", "", IPV6_NATIVE_DHCP, NULL);
        check("2001:db8:1234:5600::", "invalid", "", IPV6_NATIVE_DHCP, NULL);
        check("2001:db8:1234:5600::", "", "2001:db8:ffff::2", IPV6_MANUAL, "2001:db8:ffff::2");
    }
    puts("AX56U DS-Lite local-address regression tests passed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="ax56u-host-tests-") as directory:
        path = Path(directory)
        (path / "dslite.c").write_text(program)
        subprocess.run([
            HOST_CC, *HOST_CFLAGS, "-DRTAX56U",
            str(path / "dslite.c"), "-o", str(path / "dslite"),
        ], check=True)
        subprocess.run([str(path / "dslite")], check=True)


if __name__ == "__main__":
    check_source_wiring()
    check_update_applet()
    check_safe_command_compat()
    check_dslite_local_address()
