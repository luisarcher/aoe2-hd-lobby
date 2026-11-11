"""Log on with the saved token and dump one raw lobby list to data/probe.json."""
import json
import sys

from aoe2lobby.steam_session import DATA_DIR, connect

client = connect()
print("logged on as", client.steam_id)
lobbies = client.get_lobbies()
client.logout()
out = DATA_DIR / "probe.json"
out.write_text(json.dumps(lobbies, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{len(lobbies)} lobbies -> {out}")
for lob in lobbies[:5]:
    print(json.dumps(lob, ensure_ascii=False)[:600], file=sys.stdout)
