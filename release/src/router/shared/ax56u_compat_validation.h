/* Source-owned AX56U consumer checks; no private/vendor library dependency. */
#ifndef AX56U_COMPAT_VALIDATION_H
#define AX56U_COMPAT_VALIDATION_H

#include <arpa/inet.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static inline int ax56u_ascii_alnum(unsigned char c)
{
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
	       (c >= '0' && c <= '9');
}

/* Decimal only: no signs, whitespace, partial conversions or overflow. */
static inline int ax56u_uint(const char *s, unsigned int max, unsigned int *out)
{
	unsigned int n = 0, d;
	if (!s || !*s) return 0;
	for (; *s; ++s) {
		if (*s < '0' || *s > '9') return 0;
		d = (unsigned int)(*s - '0');
		if (d > max || n > (max - d) / 10) return 0;
		n = n * 10 + d;
	}
	if (out) *out = n;
	return 1;
}

static inline int ax56u_ipv4(const char *s)
{
	struct in_addr ip;
	return s && inet_pton(AF_INET, s, &ip) == 1;
}

/* Linux interface names used as single shell tokens, not arbitrary options. */
static inline int ax56u_ifname(const char *s)
{
	size_t i, n;
	if (!s || !(n = strlen(s)) || n >= 16 || !ax56u_ascii_alnum(s[0])) return 0;
	for (i = 1; i < n; ++i)
		if (!ax56u_ascii_alnum(s[i]) && s[i] != '_' && s[i] != '-' && s[i] != '.') return 0;
	return 1;
}

/* tc accepts fractional kbit values produced by the UI's Mb/s * 1024.
 * Bound to the existing 10240000kbit parent; avoid locale-sensitive strtod.
 */
static inline int ax56u_qos_rate(const char *s)
{
	unsigned int whole = 0;
	size_t n = 0;
	int fraction_nonzero = 0;
	if (!s || *s < '0' || *s > '9' || strlen(s) > 32) return 0;
	while (*s >= '0' && *s <= '9') {
		unsigned int d = (unsigned int)(*s++ - '0');
		if (whole > (10240000U - d) / 10) return 0;
		whole = whole * 10 + d;
	}
	if (*s == '.') {
		++s;
		while (*s >= '0' && *s <= '9') {
			fraction_nonzero |= (*s++ != '0');
			++n;
		}
		if (!n) return 0;
	}
	return !*s && whole >= 1 && whole <= 10240000U &&
	       (whole < 10240000U || !fraction_nonzero);
}

enum ax56u_qos_addr_type {
	AX56U_QOS_INVALID, AX56U_QOS_IP, AX56U_QOS_MAC,
	AX56U_QOS_RANGE, AX56U_QOS_INTERFACE
};

/* Normalize only supported address grammars, before the legacy range parser
 * (which assumes short octets) or a shell/iptables-restore sees the value.
 */
static inline int ax56u_qos_address(const char *s, char *out, size_t size)
{
	char a[40], b[16], *sep, *last;
	struct in_addr first, end;
	unsigned int n, unit;
	uint32_t lo, hi, mask;
	size_t i, len;
	int kind = AX56U_QOS_INVALID, written;
	if (!s || !(len = strlen(s)) || len >= sizeof(a) || !out || !size) return kind;
	memcpy(a, s, len + 1);
	if (ax56u_ipv4(a)) kind = AX56U_QOS_IP;
	else if (len == 17) {
		for (i = 0; i < 17; ++i) {
			unsigned char c = a[i];
			if (i % 3 == 2 ? c != ':' : !((c >= '0' && c <= '9') ||
			    (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) break;
		}
		if (i == 17) kind = AX56U_QOS_MAC;
	}
	if (kind) {
		if (len >= size) return AX56U_QOS_INVALID;
		memcpy(out, a, len + 1);
		return kind;
	}
	if (!strncmp(a, "wl", 2) && (sep = strchr(a + 2, '.')) != NULL) {
		*sep++ = '\0';
		if (!ax56u_uint(a + 2, 15, &unit) || !ax56u_uint(sep, 15, &n) || !n || len >= size)
			return AX56U_QOS_INVALID;
		memcpy(out, s, len + 1);
		return AX56U_QOS_INTERFACE;
	}
	if ((sep = strchr(a, '-')) != NULL) {
		*sep++ = '\0';
		if (inet_pton(AF_INET, a, &first) != 1) return AX56U_QOS_INVALID;
		if (strchr(sep, '.')) {
			if (inet_pton(AF_INET, sep, &end) != 1) return AX56U_QOS_INVALID;
		} else {
			if (!ax56u_uint(sep, 255, &n)) return AX56U_QOS_INVALID;
			end.s_addr = htonl((ntohl(first.s_addr) & 0xffffff00U) | n);
		}
		lo = ntohl(first.s_addr);
		hi = ntohl(end.s_addr);
	} else if ((sep = strchr(a, '/')) != NULL) {
		*sep++ = '\0';
		if (inet_pton(AF_INET, a, &first) != 1 || !ax56u_uint(sep, 30, &n) || !n)
			return AX56U_QOS_INVALID;
		mask = UINT32_MAX << (32 - n);
		lo = (ntohl(first.s_addr) & mask) + 1;
		hi = (ntohl(first.s_addr) & mask) + ~mask - 1;
	} else if ((last = strrchr(a, '.')) != NULL && !strcmp(last, ".*")) {
		last[1] = '0';
		last[2] = '\0';
		if (inet_pton(AF_INET, a, &first) != 1) return AX56U_QOS_INVALID;
		lo = ntohl(first.s_addr) + 1;
		hi = ntohl(first.s_addr) + 254;
	} else return AX56U_QOS_INVALID;
	if (lo > hi) return AX56U_QOS_INVALID;
	first.s_addr = htonl(lo);
	end.s_addr = htonl(hi);
	if (!inet_ntop(AF_INET, &first, a, sizeof(a)) || !inet_ntop(AF_INET, &end, b, sizeof(b)))
		return AX56U_QOS_INVALID;
	written = snprintf(out, size, "%s-%s", a, b);
	return written >= 0 && (size_t)written < size ? AX56U_QOS_RANGE : AX56U_QOS_INVALID;
}

static inline int ax56u_qos_rule(const char *enable, const char *addr,
	const char *download, const char *upload, const char *priority)
{
	char normalized[40];
	/* UI has 32 client slots, priority 0..31 (marks 30..61). */
	return enable && (!strcmp(enable, "0") || !strcmp(enable, "1")) &&
	       ax56u_qos_address(addr, normalized, sizeof(normalized)) != AX56U_QOS_INVALID &&
	       ax56u_qos_rate(download) && ax56u_qos_rate(upload) && ax56u_uint(priority, 31, NULL);
}

static inline int ax56u_qos_record(const char *record)
{
	char copy[160], *fields[5], *p;
	size_t i;
	if (!record || strlen(record) >= sizeof(copy)) return 0;
	strcpy(copy, record);
	fields[0] = copy;
	for (i = 1; i < 5; ++i) {
		p = strchr(fields[i - 1], '>');
		if (!p) return 0;
		*p = '\0';
		fields[i] = p + 1;
	}
	return !strchr(fields[4], '>') && ax56u_qos_rule(fields[0], fields[1], fields[2], fields[3], fields[4]);
}

/* ASCII DNS labels; excludes shell substitutions and DN separators. */
static inline int ax56u_dns_name(const char *s)
{
	size_t i, label = 0, n;
	if (!s || !(n = strlen(s)) || n > 253) return 0;
	for (i = 0; i < n; ++i) {
		unsigned char c = s[i];
		if (c == '.') {
			if (!label || s[i - 1] == '-') return 0;
			label = 0;
		} else {
			if ((!ax56u_ascii_alnum(c) && c != '-') || (!label && c == '-') || ++label > 63)
				return 0;
		}
	}
	return s[n - 1] != '-'; /* A final DNS root dot is valid. */
}

static inline int ax56u_device_cn(const char *s)
{
	size_t i, n;
	if (!s || !(n = strlen(s)) || n > 63 || !ax56u_ascii_alnum(s[0])) return 0;
	for (i = 1; i < n; ++i)
		if (!ax56u_ascii_alnum(s[i]) && s[i] != '-' && s[i] != '_' && s[i] != '.' && s[i] != ' ')
			return 0;
	return s[n - 1] != ' ';
}

/* Observed 12_2 RT-AX58U web_hook.o behavior: exact page match plus
 * is_noFwManual(). This is a capability gate, NOT a generic URL sanitizer.
 * The caller keeps the available AX56U is_noFwManual() implementation.
 */
static inline int ax56u_reject_url(const char *url, int no_manual_firmware)
{
	return !url || (no_manual_firmware && !strcmp(url, "AiMesh_Node_FirmwareUpgrade.asp"));
}

#endif
