"""One-time interactive Steam login. Saves a refresh token to data/steam_token.json.

Run it in your own terminal:  uv run login.py
In Docker:                    docker compose run --rm lobby python login.py
"""
import getpass
import json

from aoe2lobby.auth import login_with_credentials
from aoe2lobby.steam_session import TOKEN_FILE, save_token


def main() -> None:
    old = json.loads(TOKEN_FILE.read_text(encoding="utf-8")) if TOKEN_FILE.exists() else {}
    user = input(f"Steam account name [{old.get('account_name', '')}]: ").strip() or old.get("account_name", "")
    password = getpass.getpass("Steam password (not shown): ")
    tok = login_with_credentials(
        user, password,
        ask_code=lambda label: input(f"{label}: "),
        guard_data=old.get("guard_data", ""),
    )
    data = {"account_name": tok.account_name, "steamid": tok.steamid,
            "refresh_token": tok.refresh_token, "guard_data": tok.guard_data}
    if "login_id" in old:
        data["login_id"] = old["login_id"]
    save_token(data)
    print(f"Logged in as {tok.account_name} ({tok.steamid}). Token saved to {TOKEN_FILE}")
    print("Keep that file private: it lets anyone log in to this Steam account.")


if __name__ == "__main__":
    main()
