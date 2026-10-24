/*
 * Source fallbacks for runtime helpers absent from the RT-AX56U private
 * objects. Keep command execution argv-based; never hand formatted commands
 * to a shell.
 */
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define COMMAND_MAX 4096
#define COMMAND_ARGV_MAX 64

static int command_text_is_safe(const char *command)
{
	const unsigned char *p;

	for (p = (const unsigned char *)command; *p; ++p) {
		if ((*p < 0x20 && *p != '\t') || *p == 0x7f ||
		    strchr(";|&<>$`()", *p))
			return 0;
	}
	return 1;
}

static int command_to_argv(const char *command, char *storage,
			   size_t storage_size, char **argv, size_t argv_size)
{
	size_t src = 0, dst = 0;
	int argc = 0, i;

	while (command[src]) {
		char quote = '\0';
		int started = 0;

		while (isspace((unsigned char)command[src]))
			++src;
		if (!command[src])
			break;
		if ((size_t)argc + 1 >= argv_size)
			return -1;
		argv[argc++] = storage + dst;

		while (command[src]) {
			char c = command[src];

			if (!quote && isspace((unsigned char)c))
				break;
			if (!quote && (c == '\'' || c == '"')) {
				quote = c;
				started = 1;
				++src;
				continue;
			}
			if (quote && c == quote) {
				quote = '\0';
				started = 1;
				++src;
				continue;
			}
			if (c == '\\') {
				if (!command[src + 1])
					return -1;
				c = command[++src];
			}
			if (dst + 1 >= storage_size)
				return -1;
			storage[dst++] = c;
			started = 1;
			++src;
		}
		if (quote || !started || dst >= storage_size)
			return -1;
		storage[dst++] = '\0';
	}
	if (!argc)
		return -1;
	argv[argc] = NULL;

	/* Reject shell executables/applets, including paths passed to wrappers
	 * such as busybox or env. A plain -c is a valid option for ethswctl,
	 * not evidence of shell execution.
	 */
	for (i = 0; argv[i]; ++i) {
		const char *name = strrchr(argv[i], '/');

		name = name ? name + 1 : argv[i];
		if (!strcmp(name, "sh") || !strcmp(name, "ash") ||
		    !strcmp(name, "bash") || !strcmp(name, "dash") ||
		    !strcmp(name, "hush") || !strcmp(name, "ksh") ||
		    !strcmp(name, "zsh") || !strcmp(name, "csh") ||
		    !strcmp(name, "tcsh"))
			return -1;
	}
	return argc;
}

static int run_argv(char **argv, const char *outfile, int append)
{
	int status;
	pid_t pid = fork();

	if (pid < 0)
		return -1;
	if (pid == 0) {
		if (outfile) {
			int flags = O_WRONLY | O_CREAT | (append ? O_APPEND : O_TRUNC);
			int fd = open(outfile, flags, 0600);

			if (fd < 0 || dup2(fd, STDOUT_FILENO) < 0)
				_exit(126);
			if (fd != STDOUT_FILENO)
				close(fd);
		}
		execvp(argv[0], argv);
		_exit(errno == ENOENT ? 127 : 126);
	}

	while (waitpid(pid, &status, 0) < 0) {
		if (errno != EINTR)
			return -1;
	}
	if (WIFEXITED(status))
		return WEXITSTATUS(status);
	if (WIFSIGNALED(status))
		return 128 + WTERMSIG(status);
	return -1;
}

static int safe_do_system_v(const char *outfile, int append,
			    const char *fmt, va_list ap)
{
	char command[COMMAND_MAX], storage[COMMAND_MAX];
	char *argv[COMMAND_ARGV_MAX];
	int argc, length;

	if (!fmt || (outfile && (!*outfile || !command_text_is_safe(outfile))))
		return -1;
	length = vsnprintf(command, sizeof(command), fmt, ap);
	if (length < 0 || (size_t)length >= sizeof(command) ||
	    !command_text_is_safe(command))
		return -1;
	argc = command_to_argv(command, storage, sizeof(storage), argv,
			       COMMAND_ARGV_MAX);
	if (argc < 0)
		return -1;
	return run_argv(argv, outfile, append);
}

int safe_do_system(const char *fmt, ...)
{
	va_list ap;
	int ret;

	va_start(ap, fmt);
	ret = safe_do_system_v(NULL, 0, fmt, ap);
	va_end(ap);
	return ret;
}

int safe_do_system_to_file(const char *outfile, int append, const char *fmt, ...)
{
	va_list ap;
	int ret;

	va_start(ap, fmt);
	ret = safe_do_system_v(outfile, append, fmt, ap);
	va_end(ap);
	return ret;
}
