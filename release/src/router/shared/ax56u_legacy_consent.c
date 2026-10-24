/* Compatibility for the AX56U legacy consent/service stack. */
#include <bcmnvram.h>

#if defined(RTAX56U)
/* The AX56U Notification Center expects this boolean gate. It has legacy
 * ASUS consent, not PPv2 feature/version state. Read the real setting every
 * time, including after withdrawal; never fabricate an approval.
 */
int get_ASUS_privacy_policy(void)
{
	return nvram_match("ASUS_EULA", "1");
}
#endif
