"""Filesystem confinement for concurrently running mail sandboxes (Linux Landlock).

Fail closed when the host or container policy does not support ABI 3.
No sibling request directory, broker socket path, or arbitrary /proc access.
"""
import ctypes
import errno
import os
import platform
import stat

# Linux generic syscall numbers on the supported container architectures.
CREATE, ADD, RESTRICT = 444, 445, 446
EXECUTE, WRITE, READ, READ_DIR, REMOVE_DIR, REMOVE_FILE = (1 << n for n in range(6))
MAKE_DIR, MAKE_REG = 1 << 7, 1 << 8
REFER, TRUNCATE = 1 << 13, 1 << 14
HANDLED = (1 << 15) - 1
RO = EXECUTE | READ | READ_DIR
RW = RO | WRITE | REMOVE_DIR | REMOVE_FILE | MAKE_DIR | MAKE_REG | REFER | TRUNCATE


class Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def confine(directory):
    if platform.machine() not in {"x86_64", "aarch64"}:
        raise RuntimeError("Unsupported Landlock architecture")
    lib = ctypes.CDLL(None, use_errno=True)
    lib.syscall.restype = ctypes.c_long

    def syscall(number, *args):
        result = lib.syscall(ctypes.c_long(number), *args)
        if result < 0:
            raise OSError(ctypes.get_errno(), "Landlock syscall failed")
        return result

    abi = syscall(CREATE, ctypes.c_void_p(), ctypes.c_size_t(0), ctypes.c_uint(1))
    if abi < 3:
        raise RuntimeError("Landlock ABI 3 required")
    attr = Ruleset(HANDLED)
    ruleset = syscall(CREATE, ctypes.byref(attr), ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint(0))
    try:
        def allow(path, rights, optional=False):
            try:
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except FileNotFoundError:
                if optional:
                    return
                raise
            try:
                if not stat.S_ISDIR(os.fstat(fd).st_mode):
                    rights &= EXECUTE | WRITE | READ | TRUNCATE
                rule = PathRule(rights, fd)
                syscall(ADD, ctypes.c_int(ruleset), ctypes.c_int(1), ctypes.byref(rule), ctypes.c_uint(0))
            finally:
                os.close(fd)

        # Immutable parser image, not the broker's working directory or /tmp.
        for path in ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/app", "/opt"):
            allow(path, RO, optional=True)
        allow("/dev/null", READ | WRITE)
        allow("/dev/urandom", READ)
        allow("/dev/random", READ, optional=True)
        allow("/proc/self", READ | READ_DIR)
        allow("/sys/devices/system/cpu", READ | READ_DIR, optional=True)
        allow(directory, RW)
        if lib.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            raise OSError(ctypes.get_errno() or errno.EPERM, "Cannot set no-new-privileges")
        syscall(RESTRICT, ctypes.c_int(ruleset), ctypes.c_uint(0))
    finally:
        os.close(ruleset)
