"""Adversarial signal probe. Run only in disposable parser container."""
import os
import signal
import tempfile
import time
import ctypes
import ctypes.util

from app.analysis_isolation import confine
from app.sandbox import restrict


def main():
    victim = os.fork()
    if victim == 0:
        time.sleep(30)
        os._exit(0)
    try:
        with tempfile.TemporaryDirectory(prefix='signal-probe-') as directory:
            attacker = os.fork()
            if attacker == 0:
                try:
                    os.chdir(directory)
                    confine(directory)
                    restrict(scan=True, unified=True)
                    for target in (victim, os.getppid()):
                        try:
                            os.kill(target, 0)
                        except PermissionError:
                            continue
                        os._exit(42)
                    lib = ctypes.CDLL(None, use_errno=True)
                    seccomp = ctypes.CDLL(ctypes.util.find_library('seccomp'))
                    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
                    for name in (
                        'pidfd_open', 'pidfd_getfd', 'pidfd_send_signal',
                        'io_uring_setup', 'io_uring_enter', 'io_uring_register',
                        'rt_sigqueueinfo', 'rt_tgsigqueueinfo', 'process_madvise',
                        'process_mrelease', 'kcmp', 'prlimit64', 'ptrace',
                        'process_vm_readv', 'process_vm_writev', 'setpriority',
                        'sched_setparam', 'sched_setscheduler', 'sched_setaffinity',
                        'sched_setattr', 'migrate_pages', 'move_pages', 'bpf',
                        'perf_event_open', 'reboot', 'kexec_load', 'kexec_file_load',
                    ):
                        number = seccomp.seccomp_syscall_resolve_name(name.encode())
                        if number < 0:
                            continue  # syscall absent on this architecture
                        ctypes.set_errno(0)
                        result = lib.syscall(ctypes.c_long(number), victim, 0, 0, 0, 0, 0)
                        if result != -1 or ctypes.get_errno() != 1:
                            os._exit(45)
                    # libc wrappers exercise alternate targeting interfaces.
                    for name, args in (
                        ('kill', (victim, signal.SIGTERM)),
                        ('tgkill', (victim, victim, 0)),
                        ('tkill', (victim, 0)),
                        ('setsid', ()),
                        ('setpgid', (0, 0)),
                    ):
                        function = getattr(lib, name, None)
                        if function is not None:
                            ctypes.set_errno(0)
                            if function(*args) != -1 or ctypes.get_errno() != 1:
                                os._exit(44)
                    os._exit(0)
                except BaseException:
                    os._exit(43)
            _, result = os.waitpid(attacker, 0)
            code = os.waitstatus_to_exitcode(result)
            print('signal_probe_exit=', code, flush=True)
            assert code == 0, 'Sandbox can signal a same-UID sibling outside its process group'
    finally:
        try:
            os.kill(victim, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(victim, 0)


if __name__ == '__main__':
    main()