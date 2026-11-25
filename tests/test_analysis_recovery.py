"""Disposable-container tests; no bulk mail or production state."""
import os
import signal
import time
from unittest.mock import patch

from app.analysis_broker import AnalysisBroker, AnalysisUnavailable


def test_launcher_restart():
    broker = AnalysisBroker()
    try:
        first = broker.process.pid
        orphan = os.path.join(broker.directory.name, 'mice-mail-orphan')
        os.mkdir(orphan)
        os.kill(first, signal.SIGKILL)
        broker.process.wait(timeout=10)
        until = time.monotonic() + 3
        while os.path.exists(orphan) and time.monotonic() < until:
            time.sleep(.05)
        assert not os.path.exists(orphan), 'Cleanup must not require a new request'
        try:
            broker.analyze({})
        except AnalysisUnavailable:
            pass
        else:
            raise AssertionError('Restart must defer the interrupted request')
        assert broker.process.pid != first
        assert not os.path.exists(orphan)
    finally:
        broker.close()
    assert not os.path.exists(broker.directory.name)


def test_ocr_unavailable():
    import httpx
    broker = AnalysisBroker()
    try:
        with patch('app.analysis_broker.httpx.AsyncClient', side_effect=httpx.ConnectError('private-data')):
            try:
                broker.ocr({'data': 'eA==', 'name': 'test.png'}, 1)
            except AnalysisUnavailable as error:
                assert 'private-data' not in str(error)
            else:
                raise AssertionError('OCR outage must propagate temporary unavailability')
    finally:
        broker.close()


def test_real_ocr_transport_unavailable():
    broker = AnalysisBroker()
    broker.ocr_url = 'http://127.0.0.1:1/parse'
    try:
        try:
            broker.ocr({'data': 'eA==', 'name': 'test.png'}, 1)
        except AnalysisUnavailable:
            pass
        else:
            raise AssertionError('Refused connection must be retryable')
    finally:
        broker.close()


def test_helper_timeout_kills_group_and_reaps():
    import subprocess
    from app.sandbox import local_call
    for operation in ('regex', 'gitleaks'):
        with patch('app.sandbox.subprocess.Popen') as launch, patch('app.sandbox.os.killpg') as kill:
            process = launch.return_value
            process.pid = 123456
            process.communicate.side_effect = subprocess.TimeoutExpired(operation, 2)
            try:
                local_call(operation, b'abc', 'abc', isolated=True)
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError('Timeout must propagate')
            kill.assert_called_once_with(123456, signal.SIGKILL)
            process.wait.assert_called_once()


def test_real_helper_deadlines():
    import subprocess
    from app.sandbox import local_call
    for operation, data, name, timeout in (
        ('regex', b'a' * 100000 + b'!', 'a{0,32}' * 12 + 'b', 2),
        ('gitleaks', b'no secrets', '', .001),
    ):
        started = time.monotonic()
        try:
            local_call(operation, data, name, isolated=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise AssertionError('Expected real helper timeout')
        assert time.monotonic() - started < timeout + 5
    assert local_call('regex', b'abc', 'abc', isolated=True) == [[0, 3]]


def test_resource_failure_reaping():
    import resource
    import tempfile
    from app.analysis_launcher import reap
    with tempfile.TemporaryDirectory() as root:
        for mode in ('memory', 'descendant'):
            directory = os.path.join(root, mode)
            os.mkdir(directory)
            pid = os.fork()
            if pid == 0:
                os.setsid()
                if mode == 'memory':
                    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2,) * 2)
                    try:
                        bytearray(512 * 1024**2)
                    except MemoryError:
                        os._exit(0)
                    os._exit(42)
                child = os.fork()
                if child == 0:
                    time.sleep(30)
                    os._exit(0)
                time.sleep(30)
                os._exit(0)
            time.sleep(.2)
            children = {pid: (time.monotonic(), directory)}
            reap(children, 0)
            assert not children
            assert not os.path.exists(directory)
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            else:
                raise AssertionError('Root child was not reaped')


def test_pid_exhaustion_recovers():
    """Only run inside a disposable container with --pids-limit 96."""
    import errno
    children = []
    try:
        for _ in range(128):
            try:
                pid = os.fork()
            except OSError as error:
                assert error.errno == errno.EAGAIN
                break
            if pid == 0:
                time.sleep(30)
                os._exit(0)
            children.append(pid)
        else:
            raise AssertionError('Expected container PID limit')
    finally:
        for pid in children:
            os.kill(pid, signal.SIGKILL)
        for pid in children:
            os.waitpid(pid, 0)
    test_launcher_restart()


def test_ipc_rejects_invalid_frames():
    import socket
    import struct
    from app.analysis_ipc import MAX_FRAME, receive
    for data in (struct.pack('!I', MAX_FRAME + 1), struct.pack('!I', 0),
                 struct.pack('!I', 2) + b'[]', struct.pack('!I', 1) + b'{'):
        left, right = socket.socketpair()
        try:
            left.sendall(data)
            left.shutdown(socket.SHUT_WR)
            try:
                receive(right)
            except (ValueError, EOFError):
                pass
            else:
                raise AssertionError('Invalid frame accepted')
        finally:
            left.close()
            right.close()


def test_ocr_absolute_deadline_slow_stream():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Slow(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.end_headers()
            try:
                for _ in range(100):
                    self.wfile.write(b' ')
                    self.wfile.flush()
                    time.sleep(.05)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Slow)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    broker = AnalysisBroker()
    broker.ocr_url = 'http://127.0.0.1:%d/parse' % server.server_port
    try:
        started = time.monotonic()
        try:
            broker.ocr({'data': 'eA==', 'name': 'test.png'}, .4)
        except AnalysisUnavailable:
            pass
        else:
            raise AssertionError('Slow stream extended absolute deadline')
        assert time.monotonic() - started < 1.5
    finally:
        broker.close()
        server.shutdown()
        server.server_close()


def test_guardian_kills_descendants_on_owner_death():
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        script = '''import os,time
from app.sandbox import local_call
local_call('regex', b'a'*100000+b'!', 'a{0,32}'*12+'b', isolated=True)
'''
        owner = subprocess.Popen([sys.executable, '-c', script])
        try:
            guardian = None
            until = time.monotonic() + 5
            while time.monotonic() < until:
                path = '/proc/%d/task/%d/children' % (owner.pid, owner.pid)
                with open(path) as stream:
                    children = stream.read().split()
                if children:
                    guardian = int(children[0])
                    break
                time.sleep(.01)
            assert guardian is not None
            descendant = None
            until = time.monotonic() + 1
            while time.monotonic() < until:
                try:
                    with open('/proc/%d/task/%d/children' % (guardian, guardian)) as stream:
                        descendants = stream.read().split()
                    if descendants:
                        descendant = int(descendants[0])
                        break
                except FileNotFoundError:
                    pass
                time.sleep(.01)
            assert descendant is not None, 'Must exercise an actual helper descendant'
            owner.kill()
            owner.wait(timeout=5)
            until = time.monotonic() + 5
            while time.monotonic() < until:
                try:
                    os.killpg(guardian, 0)
                except ProcessLookupError:
                    break
                time.sleep(.05)
            else:
                raise AssertionError('Helper group survived broker death')
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait()