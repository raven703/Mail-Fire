"""Single-threaded fork supervisor; the parent never parses an email."""
import ctypes
import os
import shutil
import signal
import socket
import sys
import tempfile
import time

from app.analysis_ipc import receive, send, request_ocr


def nondumpable():
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
        raise RuntimeError("Cannot protect launcher process")


def child(connection, listener, directory):
    listener.close()
    os.setsid()
    parent = os.getppid()
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise RuntimeError("Cannot install parent death signal")
    if os.getppid() != parent:
        os._exit(1)
    nondumpable()
    os.chdir(directory)
    os.environ["HOME"] = directory
    os.environ["TMPDIR"] = directory
    tempfile.tempdir = directory
    from app.analysis_isolation import confine
    from app.sandbox import restrict
    confine(directory)
    restrict(scan=True, unified=True)
    from app import analysis_ipc
    def helper(operation, data, name=""):
        send(connection, {"type": "helper", "operation": operation,
                          "data": __import__('base64').b64encode(data).decode(), "name": name})
        answer = receive(connection)
        if answer.get('type') != 'helper_result':
            raise RuntimeError('Invalid helper response')
        if answer.get('timeout'):
            raise __import__('subprocess').TimeoutExpired(operation, 2 if operation == 'regex' else 35)
        return answer['result']
    analysis_ipc.helper_gateway = helper
    try:
        from app.unified_analysis import analyze_message
        request = receive(connection)
        result = analyze_message(request, lambda data, name: request_ocr(connection, data, name))
        send(connection, {"type": "result", "result": result})
    except Exception as exc:
        try:
            send(connection, {"type": "error", "error": type(exc).__name__})
        except Exception:
            pass
    finally:
        connection.close()


def reap(children, timeout):
    for pid, (started, directory) in list(children.items()):
        info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if info is None and time.monotonic() - started < timeout:
            continue
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            if info is None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        os.waitpid(pid, 0)
        shutil.rmtree(directory, ignore_errors=True)
        del children[pid]


def preflight():
    # Verify the actual kernel and Docker policy before admitting any mail.
    with tempfile.TemporaryDirectory(prefix="mice-isolation-check-") as directory:
        pid = os.fork()
        if pid == 0:
            try:
                os.chdir(directory)
                os.environ["TMPDIR"] = directory
                tempfile.tempdir = directory
                from app.analysis_isolation import confine
                from app.sandbox import restrict
                confine(directory)
                restrict(scan=True, unified=True)
                os._exit(0)
            except BaseException:
                os._exit(1)
        _, status = os.waitpid(pid, 0)
        if os.waitstatus_to_exitcode(status) != 0:
            raise RuntimeError("Unified sandbox isolation preflight failed")


def main():
    nondumpable()
    from app.text_match import _morph
    from app import mail, categories, detection_evidence, unified_analysis
    _morph()
    if len(os.listdir("/proc/self/task")) != 1:
        raise RuntimeError("Fork supervisor must remain single-threaded")
    preflight()
    listener = socket.socket(fileno=int(sys.argv[1]))
    listener.settimeout(0.2)
    maximum = int(os.environ.get("MICE_PARSER_CONCURRENCY", "2"))
    timeout = int(os.environ.get("MICE_ANALYSIS_WALL_TIMEOUT", "600"))
    if not 1 <= maximum <= 32 or not 1 <= timeout <= 3600:
        raise ValueError("Invalid analysis supervisor limits")
    children = {}
    def shutdown(*_args):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as ready:
        ready.connect(listener.getsockname())
        send(ready, {'type': 'ready'})
        ready.settimeout(30)
        if receive(ready) != {'type': 'accepted'}:
            raise RuntimeError('Launcher readiness not acknowledged')
    try:
        while True:
            reap(children, timeout)
            if len(children) >= maximum:
                time.sleep(0.05)
                continue
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            connection.settimeout(timeout)
            directory = tempfile.mkdtemp(prefix="mice-mail-")
            try:
                pid = os.fork()
            except OSError:
                connection.close()
                shutil.rmtree(directory, ignore_errors=True)
                continue
            if pid == 0:
                try:
                    child(connection, listener, directory)
                finally:
                    os._exit(0)
            connection.close()
            children[pid] = (time.monotonic(), directory)
    finally:
        listener.close()
        reap(children, 0)


if __name__ == "__main__":
    main()
