"""No-model smoke: one OpenCode server, multiple project-scoped sessions.

Session metadata separation does not prove filesystem/tool isolation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(base, path, directory=None, data=None, delete=False):
    q = "?" + urlencode({"directory": str(directory)}) if directory else ""
    payload = json.dumps(data).encode() if data is not None else None
    req = Request(base + path + q, data=payload,
                  headers={"Content-Type": "application/json"},
                  method="DELETE" if delete else ("POST" if data is not None else "GET"))
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def run(n):
    executable = shutil.which("opencode")
    git = shutil.which("git")
    if not executable or not git:
        print(json.dumps({"outcome": "SKIP", "reason": "git/opencode unavailable"}))
        return 2
    if os.name == "nt":
        executable = str(Path(executable).with_suffix(".cmd"))
    with tempfile.TemporaryDirectory(prefix="ahp-oc-smoke-") as tmp:
        root = Path(tmp)
        projects = [root / "a", root / "b"]
        for index, path in enumerate(projects):
            path.mkdir()
            subprocess.run([git, "init", "-q", str(path)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([git, "-C", str(path), "-c", "user.name=POC",
                            "-c", "user.email=poc@example.invalid", "commit",
                            "--allow-empty", "-q", "-m", f"baseline-{index}"],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        with (root / "server.log").open("wb") as log:
            proc = subprocess.Popen(
                [executable, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
                cwd=projects[0], stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "1"},
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            created = []
            try:
                deadline = time.monotonic() + 55
                while True:
                    if proc.poll() is not None:
                        raise RuntimeError("OpenCode exited during bootstrap")
                    try:
                        request(base, "/global/health")
                        break
                    except (OSError, TimeoutError):
                        if time.monotonic() > deadline:
                            raise TimeoutError("health deadline")
                        time.sleep(0.3)
                def create(pair):
                    index, seq = pair
                    session = request(base, "/session", projects[index],
                                      {"title": f"ahp-{index}-{seq}"})
                    return (index, session["id"], session["projectID"], session["directory"])
                with ThreadPoolExecutor(max_workers=6) as pool:
                    created = list(pool.map(create, [(i, j) for i in range(2) for j in range(n)]))
                for index, _, _, directory in created:
                    assert Path(directory).resolve() == projects[index].resolve()
                for index, path in enumerate(projects):
                    mine = {x[1] for x in created if x[0] == index}
                    others = {x[1] for x in created if x[0] != index}
                    listing = {x["id"] for x in request(base, "/session", path)}
                    assert mine <= listing and not (others & listing), "cross-project listing"
                ids = [{x[2] for x in created if x[0] == i} for i in (0, 1)]
                assert len(ids[0]) == len(ids[1]) == 1 and ids[0] != ids[1]
                print(json.dumps({"outcome": "PASS", "server_instances_started": 1,
                                  "sessions": len(created), "projects": 2,
                                  "project_session_listing_isolated": True,
                                  "tool_execution_isolated": "NOT_TESTED",
                                  "model_calls": 0}, sort_keys=True))
                return 0
            finally:
                for index, sid, _, _ in created:
                    try:
                        request(base, "/session/" + sid, projects[index], delete=True)
                    except Exception:
                        pass
                if proc.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                       capture_output=True, timeout=15)
                    else:
                        proc.terminate()
                        try:
                            proc.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=8)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sessions-per-project", type=int, default=3)
    a = p.parse_args()
    if not 1 <= a.sessions_per_project <= 100:
        p.error("sessions-per-project must be in 1..100")
    raise SystemExit(run(a.sessions_per_project))