// Native launcher for "Voice Dictation.app".
//
// Makes Voice Dictation behave like a normal Mac app: it shows in the Dock,
// quits with Cmd+Q / Dock > Quit, and clicking the Dock icon shows a small
// "running" dialog with a Quit button.
//
// The dictation itself runs in Python as a child process. Spawning it (rather
// than exec'ing) keeps this app as the "responsible" process, so macOS grants
// Microphone / Input Monitoring permissions to "Voice Dictation", not Python.
// PYTHON_PATH and SCRIPT_PATH are set at build time by install.sh.
#import <Cocoa/Cocoa.h>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>

extern char **environ;

@interface AppDelegate : NSObject <NSApplicationDelegate>
@end

@implementation AppDelegate {
    pid_t _child;
    dispatch_source_t _exitWatcher;
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    NSString *log = [NSHomeDirectory()
        stringByAppendingPathComponent:@"Library/Logs/VoiceDictation.log"];

    posix_spawn_file_actions_t fa;
    posix_spawn_file_actions_init(&fa);
    posix_spawn_file_actions_addopen(&fa, 1, log.fileSystemRepresentation,
                                     O_WRONLY | O_CREAT | O_APPEND, 0644);
    posix_spawn_file_actions_adddup2(&fa, 1, 2);

    setenv("PYTHONUNBUFFERED", "1", 1);
    char *argv[] = {PYTHON_PATH, SCRIPT_PATH, NULL};
    int err = posix_spawn(&_child, PYTHON_PATH, &fa, NULL, argv, environ);
    posix_spawn_file_actions_destroy(&fa);

    if (err != 0) {
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = @"Voice Dictation could not start";
        alert.informativeText = [NSString stringWithFormat:
            @"Could not run %s (error %d). Try running ./install.sh again.",
            PYTHON_PATH, err];
        [alert runModal];
        [NSApp terminate:nil];
        return;
    }

    // When the Python side exits (e.g. Quit from its menu-bar icon), quit too.
    _exitWatcher = dispatch_source_create(DISPATCH_SOURCE_TYPE_PROC, _child,
                                          DISPATCH_PROC_EXIT,
                                          dispatch_get_main_queue());
    dispatch_source_set_event_handler(_exitWatcher, ^{
        self->_child = 0;
        [NSApp terminate:nil];
    });
    dispatch_resume(_exitWatcher);
}

// Clicking the Dock icon while running.
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender
                    hasVisibleWindows:(BOOL)flag {
    [NSApp activateIgnoringOtherApps:YES];
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"Voice Dictation is running";
    alert.informativeText =
        @"Hold Right ⌥ (Option) for English or Right ⌘ (Command) "
        @"for Hungarian, speak, then release. The text is copied to your "
        @"clipboard — paste it with ⌘V.";
    [alert addButtonWithTitle:@"OK"];
    [alert addButtonWithTitle:@"Quit Voice Dictation"];
    if ([alert runModal] == NSAlertSecondButtonReturn) {
        [NSApp terminate:nil];
    }
    return NO;
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (_child > 0) {
        kill(_child, SIGTERM);
    }
    return NSTerminateNow;
}

@end

int main(void) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        app.delegate = delegate;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        [app run];
    }
    return 0;
}
