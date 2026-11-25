"""Trusted helper lifetime guard: broker pipe EOF kills the entire session group."""
import os
import signal
import subprocess
import sys
import threading


def main():
    lifetime = int(sys.argv[1])

    def watch():
        while os.read(lifetime, 1):
            pass
        os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=watch, daemon=True).start()
    process = subprocess.Popen([sys.executable, '-m', 'app.sandbox'], close_fds=True)
    sys.exit(process.wait())


if __name__ == '__main__':
    main()