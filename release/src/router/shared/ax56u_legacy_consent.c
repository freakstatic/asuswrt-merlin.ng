/* Compatibility for the AX56U legacy consent/service stack. */
#include <string.h>
#include <bcmnvram.h>

#if defined(RTAX56U)
/*
 * The newer, precompiled Notification Center calls this exported boolean
 * gate. AX56U has only legacy ASUS consent, not PPv2 feature/version state.
 * Read the real legacy setting on every call, including after withdrawal.
 * Do not turn this into unconditional approval or a fabricated PPv2 state.
 */
int get_ASUS_privacy_policy(void)
{
	return nvram_match("ASUS_EULA", "1");
}
#endif
