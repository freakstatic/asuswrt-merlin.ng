#include <assert.h>
#include <stdio.h>
#include "ax56u_compat_validation.h"

#define COUNT(a) (sizeof(a) / sizeof((a)[0]))

static void test_numbers(void)
{
	const char *good[] = {"1", "1024", "1.024", "102.39999999999999", "10240000", "10240000.0", "0001.25"};
	const char *bad[] = {NULL, "", "0", "0.999", "-1", "+1", " 1", "1 ", "1\n", "1e3", "0x100", ".5", "1.", "1.2.3", "nan", "inf", "10240001", "10240000.0001", "99999999999999999999999999999", "1;touch /tmp/x", "1$(id)", "1`id`", "1\\\n2", "1>file", "1\t2"};
	const char *bad_uint[] = {NULL, "", "-1", "+1", "1a", "1.0", " 1", "1\n", "32", "4294967296", "99999999999999999999", "1;id"};
	unsigned int n = 99;
	size_t i;
	for (i = 0; i < COUNT(good); ++i) assert(ax56u_qos_rate(good[i]));
	for (i = 0; i < COUNT(bad); ++i) assert(!ax56u_qos_rate(bad[i]));
	assert(ax56u_uint("0", 31, &n) && n == 0);
	assert(ax56u_uint("31", 31, &n) && n == 31);
	assert(ax56u_uint("4294967295", 4294967295U, &n) && n == 4294967295U);
	for (i = 0; i < COUNT(bad_uint); ++i) assert(!ax56u_uint(bad_uint[i], 31, NULL));
	assert(ax56u_uint("36500", 36500, NULL));
	assert(!ax56u_uint("36501", 36500, NULL));
}

static void test_addresses(void)
{
	struct example { const char *input, *output; int kind; } good[] = {
		{"192.168.1.2", "192.168.1.2", AX56U_QOS_IP},
		{"00:11:22:aA:BB:ff", "00:11:22:aA:BB:ff", AX56U_QOS_MAC},
		{"192.168.1.10-20", "192.168.1.10-192.168.1.20", AX56U_QOS_RANGE},
		{"192.168.1.10-192.168.2.20", "192.168.1.10-192.168.2.20", AX56U_QOS_RANGE},
		{"192.168.1.*", "192.168.1.1-192.168.1.254", AX56U_QOS_RANGE},
		{"192.168.1.0/24", "192.168.1.1-192.168.1.254", AX56U_QOS_RANGE},
		{"192.168.1.5/30", "192.168.1.5-192.168.1.6", AX56U_QOS_RANGE},
		{"128.0.0.0/1", "128.0.0.1-255.255.255.254", AX56U_QOS_RANGE},
		{"wl0.1", "wl0.1", AX56U_QOS_INTERFACE},
		{"wl1.3", "wl1.3", AX56U_QOS_INTERFACE}
	};
	const char *bad[] = {NULL, "", "192.168.1.256", "192.168.01.2", "127.1", "0x7f000001", "::1", "1.2.3.4;id", "1.2.3.4\n-A PREROUTING", "1.2.3.*;id", "1.2.*", "1.2.3.4/0", "1.2.3.4/31", "1.2.3.4/33", "1.2.3.4/24x", "1.2.3.5-4", "1.2.3.4-256", "1.2.3.4-", "1.2.3.4-2.2.2.2;id", "1234567890.2.3.4", "00:11:22:33:44:55;id", "0:11:22:33:44:55", "00:11:22:33:44:GG", "wl0.0", "wl0.16", "wl0.1;id", "wl0.1\n", "wl-1.1", "wl0.1.2", "@arbitrary-client"};
	char out[40];
	size_t i;
	for (i = 0; i < COUNT(good); ++i) {
		assert(ax56u_qos_address(good[i].input, out, sizeof(out)) == good[i].kind);
		assert(!strcmp(out, good[i].output));
		assert(!ax56u_qos_address(good[i].input, out, 2));
	}
	for (i = 0; i < COUNT(bad); ++i) assert(!ax56u_qos_address(bad[i], out, sizeof(out)));
	assert(!ax56u_qos_address("192.168.1.2", NULL, 40));
	assert(ax56u_ipv4("0.0.0.0"));
	assert(ax56u_ipv4("255.255.255.255"));
	assert(!ax56u_ipv4(NULL));
	assert(!ax56u_ipv4("1.2.3.4$(id)"));
	assert(!ax56u_ipv4("1.2.3.4\" --san=evil"));
}

static void test_rules(void)
{
	const char *bad[] = {"", "1>1.2.3.4>100>100", "1>1.2.3.4>100>100>0>ignored", "2>1.2.3.4>100>100>0", "01>1.2.3.4>100>100>0", "-1>1.2.3.4>100>100>0", "1>1.2.3.4>0>100>0", "1>1.2.3.4>100>100>32", "1>1.2.3.4>100>100>2147483647", "1>1.2.3.4>100;id>100>0", "1>1.2.3.4>100>100$(id)>0", "1>1.2.3.4\n>100>100>0", "1>1.2.3.4>100>100>0x1", "0>bad>100>100>0", "1>wl0.1;id>100>100>0"};
	size_t i;
	assert(ax56u_qos_record("1>1.2.3.4>1.024>10240000>0"));
	assert(ax56u_qos_record("0>00:11:22:33:44:55>100>100>31"));
	assert(ax56u_qos_record("1>wl0.1>100>100>0"));
	assert(ax56u_qos_record("1>192.168.1.1-254>100>100>0"));
	assert(!ax56u_qos_record(NULL));
	for (i = 0; i < COUNT(bad); ++i) assert(!ax56u_qos_record(bad[i]));
}

static void test_certificate_inputs(void)
{
	const char *dns_good[] = {"router.asuscomm.com", "router-1.example", "a", "123.example", "router.example."};
	const char *dns_bad[] = {NULL, "", ".example", "x..example", "-x.example", "x-.example", "x_example", "x example", "x;id", "$(id)", "x`id`", "x\"", "x'", "x\\", "x\n", "x\r", "x,CN=bad", "x+CN=bad", "x/../etc"};
	const char *cn_good[] = {"RT-AX56U", "router_name", "router.example", "My Router"};
	const char *cn_bad[] = {NULL, "", "$(id)", "router`id`", "router\"", "router'", "router\\", "router\n", "router\r", "router,CN=bad", "router+CN=bad", "router;id", " router", "router "};
	char long_label[65], long_cn[65], long_dns[255];
	size_t i;
	for (i = 0; i < COUNT(dns_good); ++i) assert(ax56u_dns_name(dns_good[i]));
	for (i = 0; i < COUNT(dns_bad); ++i) assert(!ax56u_dns_name(dns_bad[i]));
	for (i = 0; i < COUNT(cn_good); ++i) assert(ax56u_device_cn(cn_good[i]));
	for (i = 0; i < COUNT(cn_bad); ++i) assert(!ax56u_device_cn(cn_bad[i]));
	memset(long_label, 'a', 64); long_label[64] = '\0';
	assert(!ax56u_dns_name(long_label));
	long_label[63] = '\0'; assert(ax56u_dns_name(long_label));
	memset(long_cn, 'a', 64); long_cn[64] = '\0';
	assert(!ax56u_device_cn(long_cn));
	long_cn[63] = '\0'; assert(ax56u_device_cn(long_cn));
	memset(long_dns, 'a', 254); long_dns[254] = '\0';
	assert(!ax56u_dns_name(long_dns));
}

static void test_interfaces_and_urls(void)
{
	const char *ifs_good[] = {"eth0", "ppp0", "vlan4000", "wl0.1", "br0", "wds0_1"};
	const char *ifs_bad[] = {NULL, "", "-eth0", "eth0;id", "eth0$(id)", "eth0\n", "eth0 x", "eth0/../../x", "1234567890123456"};
	size_t i;
	for (i = 0; i < COUNT(ifs_good); ++i) assert(ax56u_ifname(ifs_good[i]));
	for (i = 0; i < COUNT(ifs_bad); ++i) assert(!ax56u_ifname(ifs_bad[i]));
}

int main(void)
{
	test_numbers();
	test_addresses();
	test_rules();
	test_certificate_inputs();
	test_interfaces_and_urls();
	puts("AX56U portable validation tests passed");
	return 0;
}
