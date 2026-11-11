"""Steam's current login flow (IAuthenticationService over HTTPS).

The old password-in-ClientLogon method no longer works, so we get a long-lived
refresh token here once and then log on to the Steam CM servers with it.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Callable

import requests
from Cryptodome.Cipher import PKCS1_v1_5
from Cryptodome.PublicKey import RSA
from steam.protobufs import steammessages_auth_pb2 as A

API = "https://api.steampowered.com/IAuthenticationService/{}/v1"
PLATFORM_STEAM_CLIENT = A.k_EAuthTokenPlatformType_SteamClient
OS_WINDOWS_10 = 16


class AuthError(RuntimeError):
    pass


@dataclass
class Token:
    account_name: str
    steamid: int
    refresh_token: str
    guard_data: str = ""


def _call(method: str, req, resp_cls, http: str = "POST"):
    data = {"input_protobuf_encoded": base64.b64encode(req.SerializeToString()).decode()}
    url = API.format(method)
    r = (requests.post(url, data=data, timeout=20) if http == "POST"
         else requests.get(url, params=data, timeout=20))
    eresult = int(r.headers.get("x-eresult", "1"))
    if r.status_code != 200 or eresult != 1:
        raise AuthError(f"{method} failed: HTTP {r.status_code}, eresult {eresult}, "
                        f"{r.headers.get('x-error_message', '')}")
    out = resp_cls()
    out.ParseFromString(r.content)
    return out


def _encrypt_password(account_name: str, password: str) -> tuple[str, int]:
    req = A.CAuthentication_GetPasswordRSAPublicKey_Request(account_name=account_name)
    key = _call("GetPasswordRSAPublicKey", req, A.CAuthentication_GetPasswordRSAPublicKey_Response, "GET")
    pub = RSA.construct((int(key.publickey_mod, 16), int(key.publickey_exp, 16)))
    enc = PKCS1_v1_5.new(pub).encrypt(password.encode())
    return base64.b64encode(enc).decode(), key.timestamp


def login_with_credentials(
    account_name: str,
    password: str,
    ask_code: Callable[[str], str],
    notify: Callable[[str], None] = print,
    guard_data: str = "",
) -> Token:
    """Run the interactive login. ``ask_code(kind)`` must return a Steam Guard code."""
    enc_pw, ts = _encrypt_password(account_name, password)
    req = A.CAuthentication_BeginAuthSessionViaCredentials_Request(
        account_name=account_name,
        encrypted_password=enc_pw,
        encryption_timestamp=ts,
        remember_login=True,
        platform_type=PLATFORM_STEAM_CLIENT,
        persistence=1,  # k_ESessionPersistence_Persistent
        website_id="Client",
        device_details=A.CAuthentication_DeviceDetails(
            device_friendly_name="aoe2-hd-lobby", platform_type=PLATFORM_STEAM_CLIENT,
            os_type=OS_WINDOWS_10),
    )
    if guard_data:
        req.guard_data = guard_data
    sess = _call("BeginAuthSessionViaCredentials", req,
                 A.CAuthentication_BeginAuthSessionViaCredentials_Response)

    kinds = {c.confirmation_type for c in sess.allowed_confirmations}
    code_type, label = None, "Press Enter once approved"
    if A.k_EAuthSessionGuardType_DeviceCode in kinds:
        code_type, label = A.k_EAuthSessionGuardType_DeviceCode, "Steam Guard mobile authenticator code"
    elif A.k_EAuthSessionGuardType_EmailCode in kinds:
        code_type, label = A.k_EAuthSessionGuardType_EmailCode, "Steam Guard code sent to your email"
    can_approve = bool(kinds & {A.k_EAuthSessionGuardType_DeviceConfirmation,
                                A.k_EAuthSessionGuardType_EmailConfirmation})
    if can_approve:
        notify("Approve this login in the Steam mobile app (or by email), then press Enter here.")
        if code_type is not None:
            label += " (or just press Enter after approving)"

    code = ask_code(label).strip() if code_type is not None or can_approve else ""
    if code and code_type is not None:
        _call("UpdateAuthSessionWithSteamGuardCode",
              A.CAuthentication_UpdateAuthSessionWithSteamGuardCode_Request(
                  client_id=sess.client_id, steamid=sess.steamid, code=code, code_type=code_type),
              A.CAuthentication_UpdateAuthSessionWithSteamGuardCode_Response)

    poll_req = A.CAuthentication_PollAuthSessionStatus_Request(
        client_id=sess.client_id, request_id=sess.request_id)
    deadline = time.time() + 120
    while time.time() < deadline:
        st = _call("PollAuthSessionStatus", poll_req, A.CAuthentication_PollAuthSessionStatus_Response)
        if st.new_client_id:
            poll_req.client_id = st.new_client_id
        if st.refresh_token:
            return Token(st.account_name or account_name, sess.steamid,
                         st.refresh_token, st.new_guard_data or guard_data)
        time.sleep(max(sess.interval, 1.0))
    raise AuthError("Timed out waiting for Steam to approve the login")
