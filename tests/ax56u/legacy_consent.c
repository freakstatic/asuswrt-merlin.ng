#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *consent;
int get_ASUS_privacy_policy(void);

int nvram_match(const char *name, const char *value)
{
	assert(strcmp(name, "ASUS_EULA") == 0);
	return consent != NULL && strcmp(consent, value) == 0;
}

int main(void)
{
	const char *unsigned_values[] = { NULL, "", "0", "2", "1junk", "01", "-1" };
	size_t i;
	for (i = 0; i < sizeof(unsigned_values) / sizeof(unsigned_values[0]); i++) {
		consent = unsigned_values[i];
		assert(get_ASUS_privacy_policy() == 0);
	}
	consent = "1";
	assert(get_ASUS_privacy_policy() == 1);
	consent = "0";
	assert(get_ASUS_privacy_policy() == 0);
	puts("legacy consent gate: passed (including live withdrawal)");
	return 0;
}
