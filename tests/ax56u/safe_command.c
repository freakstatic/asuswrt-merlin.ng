#define _XOPEN_SOURCE 700
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int safe_do_system(const char *fmt, ...);
int safe_do_system_to_file(const char *outfile, int append, const char *fmt, ...);

int main(int argc, char **argv)
{
	const char *name = strrchr(argv[0], '/');
	const char *path;
	char result[64] = {0};
	FILE *file;

	/* The harness puts this host binary on PATH as a fake switch utility. */
	name = name ? name + 1 : argv[0];
	if (!strcmp(name, "ethswctl")) {
		assert(argc == 7);
		assert(!strcmp(argv[1], "-c") && !strcmp(argv[2], "pause"));
		assert(!strcmp(argv[3], "-p") && !strcmp(argv[4], "3"));
		assert(!strcmp(argv[5], "-v") && !strcmp(argv[6], "2"));
		puts("pause configured");
		return 0;
	}
	assert(argc == 2);
	path = argv[1];
	assert(safe_do_system("/bin/true") == 0);
	assert(safe_do_system("/bin/false") == 1);
	assert(safe_do_system("/bin/true; /bin/false") == -1);
	assert(safe_do_system("/bin/sh -c 'echo unsafe'") == -1);
	assert(safe_do_system("/bin/sh -ec 'echo unsafe'") == -1);
	assert(safe_do_system("/bin/busybox sh -c 'echo unsafe'") == -1);
	assert(safe_do_system("/bin/busybox /bin/ash -ec 'echo unsafe'") == -1);
	assert(safe_do_system("env /bin/sh -ec 'echo unsafe'") == -1);
	assert(safe_do_system_to_file(path, 0,
		"ethswctl -c pause -p %d -v 2", 3) == 0);
	file = fopen(path, "r");
	assert(file != NULL);
	assert(fgets(result, sizeof(result), file) != NULL);
	assert(fclose(file) == 0);
	assert(!strcmp(result, "pause configured\n"));
	assert(safe_do_system_to_file(path, 0,
		"/usr/bin/printf \"%%s\" \"hello world\"") == 0);

	file = fopen(path, "r");
	assert(file != NULL);
	assert(fgets(result, sizeof(result), file) != NULL);
	assert(fclose(file) == 0);
	assert(!strcmp(result, "hello world"));
	assert(unlink(path) == 0);
	puts("AX56U safe command compatibility tests passed");
	return 0;
}
