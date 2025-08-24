
import os, sys, time, signal, subprocess

def spawn(cmd, env=None):
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env or os.environ.copy(),
        text=True,
    )

def stream(name, proc):
    for line in iter(proc.stdout.readline, ""):
        print(f"[{name}] {line.rstrip()}")
        if proc.poll() is not None:
            break

def terminate_group(proc, timeout=5):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    waited = 0
    while proc.poll() is None and waited < timeout:
        time.sleep(0.2); waited += 0.2
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGKILL)

def run_both():
    api = spawn([sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"])
    svc = spawn([sys.executable, "server.py"])
    import threading
    threads = [
        threading.Thread(target=stream, args=("api", api), daemon=True),
        threading.Thread(target=stream, args=("svc", svc), daemon=True),
    ]
    for t in threads:
        t.start()
    try:
        while True:
            if api.poll() is not None or svc.poll() is not None:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        terminate_group(api)
        terminate_group(svc)
        for t in threads:
            t.join(timeout=0.2)


if __name__ == "__main__":
    run_both()
