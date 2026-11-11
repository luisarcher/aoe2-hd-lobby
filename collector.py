"""Keeps a Steam session open and writes the AoE2 HD lobby list to data/lobbies.json.

Started automatically by app.py; can also be run on its own. Only one collector may
run per token: two sessions on the same account and login id keep kicking each other
off, and the resulting burst of logons makes Steam refuse the token for a while.
"""
import errno
import json
import os
import sys
import time
import traceback

from steam.enums import EResult
from steam.enums.emsg import EMsg

from aoe2lobby.steam_session import DATA_DIR, LogonError, connect

INTERVAL = float(os.environ.get("AOE_REFRESH_SECONDS", "15"))
OUT = DATA_DIR / "lobbies.json"
LOCK = DATA_DIR / "collector.lock"
LOG = DATA_DIR / "collector.log"

# Waits between reconnect attempts (seconds). Logon refusals wait longer, since
# Steam answers too many token logons with InvalidPassword/RateLimitExceeded for a while.
NETWORK_BACKOFF = (5, 10, 30, 60, 120, 300)
LOGON_BACKOFF = (60, 120, 300, 600, 900)


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [collector] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def write(payload: dict) -> None:
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OUT)


def write_error(msg: str) -> None:
    """Keep the last good lobby list, mark it with the error."""
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        prev = {"lobbies": [], "updated": None}
    prev["error"] = msg
    write(prev)


def acquire_lock():
    """Exclusive lock held for the life of the process; returns None if another holds it.

    Only guards collectors sharing this data folder on the same OS: a local run and a
    Docker container using the same token don't see each other's lock, so run one or the other.
    """
    f = open(LOCK, "a+")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK):
            f.close()
            return None
        log(f"file locking not supported here ({e}); running without the single-instance lock")
    return f


def run_session() -> None:
    client = connect()
    kicked = {}
    client.on(EMsg.ClientLoggedOff, lambda msg: kicked.setdefault("why", EResult(msg.body.eresult)))
    log(f"logged on as {client.steam_id}")
    try:
        while client.logged_on:
            lobbies = client.get_lobbies()
            write({"updated": time.time(), "error": None, "lobbies": lobbies})
            client.sleep(INTERVAL)
        why = kicked.get("why")
        raise ConnectionError(f"Steam session ended ({why.name if why else 'disconnected'})")
    finally:
        try:
            client.logout()
        except Exception:
            pass


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    lock = acquire_lock()
    if lock is None:
        log("another collector is already running for this data folder; exiting")
        return
    log(f"started (pid {os.getpid()}, refresh every {INTERVAL:g}s)")
    net_fail = logon_fail = 0
    while True:
        started = time.time()
        try:
            run_session()
        except LogonError as e:
            wait = LOGON_BACKOFF[min(logon_fail, len(LOGON_BACKOFF) - 1)]
            logon_fail += 1
            net_fail = 0
            hint = " If this keeps happening, run `python login.py` again." if logon_fail >= 3 else ""
            log(f"{e}; retrying in {wait}s.{hint}")
            write_error(f"{e} — retrying in {wait}s.{hint}")
        except SystemExit as e:   # no token file
            log(str(e))
            write_error(str(e))
            wait = 30
        except Exception as e:
            if time.time() - started > 300:   # it had been working: start the waits over
                net_fail = 0
            wait = NETWORK_BACKOFF[min(net_fail, len(NETWORK_BACKOFF) - 1)]
            net_fail += 1
            logon_fail = 0
            log(f"{type(e).__name__}: {e}; reconnecting in {wait}s")
            if not isinstance(e, (ConnectionError, TimeoutError)):
                traceback.print_exc()
            write_error(f"{type(e).__name__}: {e} — reconnecting in {wait}s")
        else:
            wait = 5
        time.sleep(wait)


if __name__ == "__main__":
    main()
