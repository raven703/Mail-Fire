"""Assert actual Docker runtime boundaries and real parser escape attempts."""

import json
import subprocess


def execute(args):
    return subprocess.check_output(args, text=True).strip()


container = execute(["docker", "compose", "ps", "-q", "parser"])
state = json.loads(execute(["docker", "inspect", container]))[0]
assert not state["Mounts"], "Parser must not have host or persistent mounts"
assert state["HostConfig"]["ReadonlyRootfs"]
assert not state["HostConfig"]["Privileged"]
assert state["HostConfig"]["CapDrop"] == ["ALL"]
assert state["Config"]["User"] == "app"
assert not state["NetworkSettings"]["Ports"], "Parser must not expose host ports"
environment = dict(item.split("=", 1) for item in state["Config"]["Env"])
assert not any(key in environment for key in ["DATABASE_URL", "ADMIN_PASSWORD", "POSTGRES_PASSWORD"])
networks = state["NetworkSettings"]["Networks"]
assert len(networks) == 1
network = json.loads(execute(["docker", "network", "inspect", next(iter(networks))]))[0]
assert network["Internal"]
assert "mailfire-db-1" not in {c["Name"] for c in network["Containers"].values()}
code = """
import json,socket
from pathlib import Path
from app.sandbox import local_call
r=local_call('probe',b'')
assert r['network_denied'] and r['database_secret'] is None
assert not any(r['sensitive_paths'].values())
assert r['uid']!=0
try:
 Path('/app/escape-test').write_text('must fail')
except OSError:
 r['rootfs_readonly']=True
else:
 raise AssertionError('Root filesystem writable')
try:
 socket.create_connection(('db',5432),timeout=2)
except OSError:
 r['postgres_unreachable']=True
else:
 raise AssertionError('PostgreSQL reachable')
print(json.dumps(r))
"""
print(execute(["docker", "compose", "exec", "-T", "parser", "python", "-c", code]))
