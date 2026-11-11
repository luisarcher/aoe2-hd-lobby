"""Token logon to Steam's CM servers and AoE2 HD lobby-list requests.

Runs on gevent (via the ``steam`` library), so keep it out of the asyncio
process: the FastAPI app talks to it through ``collector.py``.
"""
from __future__ import annotations

import json
import random
from io import BytesIO
from pathlib import Path

import vdf
from steam.client import SteamClient
from steam.core.msg import MsgProto
from steam.enums import EResult
from steam.enums.common import EOSType
from steam.enums.emsg import EMsg
from steam.steamid import SteamID

AOE2HD_APPID = 221380

# ELobbyFilterType / ELobbyComparison / ELobbyDistanceFilter (Steamworks)
FILTER_STRING, FILTER_NUMERICAL, FILTER_SLOTS, FILTER_NEAR, FILTER_DISTANCE = range(5)
CMP_EQUAL = 0
DISTANCE_WORLDWIDE = 3

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TOKEN_FILE = DATA_DIR / "steam_token.json"


def load_token() -> dict:
    if not TOKEN_FILE.exists():
        raise SystemExit(f"No Steam token at {TOKEN_FILE}. Run `uv run login.py` first "
                         "(Docker: `docker compose run --rm lobby python login.py`).")
    return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))


def save_token(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    data.setdefault("login_id", random.getrandbits(31))
    TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class LobbyClient(SteamClient):
    def token_login(self, account_name: str, refresh_token: str, login_id: int) -> EResult:
        eresult = self._pre_login()
        if eresult != EResult.OK:
            return eresult
        self.username = account_name
        m = MsgProto(EMsg.ClientLogon)
        m.header.steamid = SteamID(type="Individual", universe="Public")
        b = m.body
        b.protocol_version = 65580
        b.client_package_version = 1771
        b.client_os_type = EOSType.Windows10
        b.client_language = "english"
        b.should_remember_password = True
        b.supports_rate_limit_response = True
        b.chat_mode = 2
        b.account_name = account_name
        b.access_token = refresh_token
        # distinct from the desktop Steam client's value, so we don't replace its session
        b.obfuscated_private_ip.v4 = login_id
        b.machine_name = "aoe2-hd-lobby"
        self.send(m)
        resp = self.wait_msg(EMsg.ClientLogOnResponse, timeout=30)
        return EResult(resp.body.eresult) if resp else EResult.Fail

    def get_lobbies(self, max_lobbies: int = 200, extra_filters: list[tuple] = ()) -> list[dict]:
        m = MsgProto(EMsg.ClientMMSGetLobbyList)
        m.header.routing_appid = AOE2HD_APPID
        m.body.app_id = AOE2HD_APPID
        m.body.num_lobbies_requested = max_lobbies
        m.body.cell_id = self.cell_id or 0
        f = m.body.filters.add()
        f.key, f.value, f.comparision, f.filter_type = "", str(DISTANCE_WORLDWIDE), CMP_EQUAL, FILTER_DISTANCE
        for key, value, cmp, ftype in extra_filters:
            f = m.body.filters.add()
            f.key, f.value, f.comparision, f.filter_type = key, str(value), cmp, ftype
        resp = self.send_message_and_wait(m, EMsg.ClientMMSGetLobbyListResponse, timeout=20)
        if resp is None:
            raise TimeoutError("Steam did not answer the lobby list request")
        if resp.eresult != EResult.OK:
            raise RuntimeError(f"Lobby list failed: {EResult(resp.eresult)!r}")
        return [
            {
                "steam_id": lob.steam_id,
                "num_members": lob.num_members,
                "max_members": lob.max_members,
                "lobby_type": lob.lobby_type,
                "lobby_flags": lob.lobby_flags,
                "distance": lob.distance,
                "metadata": decode_metadata(lob.metadata),
            }
            for lob in resp.lobbies
        ]


def decode_metadata(raw: bytes) -> dict:
    if not raw:
        return {}
    try:
        data = vdf.binary_load(BytesIO(raw))
    except Exception:
        return {"_raw_hex": raw.hex()}
    # lobby metadata comes wrapped in one unnamed root key
    if len(data) == 1 and isinstance(next(iter(data.values())), dict):
        data = next(iter(data.values()))
    return {k: (v.hex() if isinstance(v, bytes) else v) for k, v in data.items()}


class LogonError(RuntimeError):
    def __init__(self, result: EResult):
        self.result = result
        super().__init__(f"Steam logon failed: {result.name} ({int(result)})")


def connect() -> LobbyClient:
    tok = load_token()   # re-read every time, so a new `login.py` run is picked up
    client = LobbyClient()
    result = client.token_login(tok["account_name"], tok["refresh_token"], tok["login_id"])
    if result != EResult.OK:
        try:
            client.disconnect()
        except Exception:
            pass
        raise LogonError(result)
    return client
