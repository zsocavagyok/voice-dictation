// Native launcher for "Voice Dictation.app".
//
// macOS grants Microphone / Input Monitoring permissions to the app that
// launched a process. A shell-script launcher that exec()s Python makes macOS
// see "python" instead of this app, so we spawn Python as a child process and
// stay alive as its parent. PYTHON_PATH and SCRIPT_PATH are set at build time.
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>

extern char **environ;
static pid_t child = 0;

static void forward(int sig) {
    if (child > 0) kill(child, sig);
}

int main(void) {
    char log_path[1024];
    const char *home = getenv("HOME");
    snprintf(log_path, sizeof log_path, "%s/Library/Logs/VoiceDictation.log",
             home ? home : "/tmp");

    posix_spawn_file_actions_t fa;
    posix_spawn_file_actions_init(&fa);
    posix_spawn_file_actions_addopen(&fa, 1, log_path,
                                     O_WRONLY | O_CREAT | O_APPEND, 0644);
    posix_spawn_file_actions_adddup2(&fa, 1, 2);

    setenv("PYTHONUNBUFFERED", "1", 1);
    char *argv[] = {PYTHON_PATH, SCRIPT_PATH, NULL};
    int err = posix_spawn(&child, PYTHON_PATH, &fa, NULL, argv, environ);
    posix_spawn_file_actions_destroy(&fa);
    if (err != 0) {
        fprintf(stderr, "Voice Dictation: cannot start %s (error %d)\n",
                PYTHON_PATH, err);
        return 1;
    }

    signal(SIGTERM, forward);
    signal(SIGINT, forward);
    signal(SIGHUP, forward);

    int status = 0;
    while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
