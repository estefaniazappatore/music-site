#!/usr/bin/env python3
"""
Carica su Spotify le copertine generate in site/covers/ (una volta per playlist).
Funziona solo se in config.json "carica_copertine_su_spotify" è true
e se il refresh token ha il permesso ugc-image-upload.
"""
import base64, json, os, sys, time
from pathlib import Path
import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text(encoding="utf-8"))
DONE = ROOT / "scripts" / "copertine_caricate.json"
MAX_PER_NOTTE = CONFIG.get("copertine_per_notte", 40)
SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public ugc-image-upload"

if not CONFIG.get("carica_copertine_su_spotify"):
    print("Caricamento copertine disattivato in config.json")
    sys.exit(0)

token = {"access_token": "", "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"], "expires_at": 0, "scope": SCOPE, "token_type": "Bearer"}
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.environ["SPOTIFY_CLIENT_ID"], client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
    redirect_uri="http://127.0.0.1:8888/callback", scope=SCOPE, open_browser=False,
    cache_handler=MemoryCacheHandler(token_info=token)), retries=0, status_retries=0, requests_timeout=20)

done = json.loads(DONE.read_text()) if DONE.exists() else {}
data = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
caricate = 0
for p in sorted(data["playlists"], key=lambda x: -(x.get("num") or 0)):
    f = ROOT / "site" / "covers" / f"{p.get('num')}.jpg"
    if not p.get("num") or not f.exists() or done.get(p["id"]) == p["num"]:
        continue
    if caricate >= MAX_PER_NOTTE:
        break
    try:
        sp.playlist_upload_cover_image(p["id"], base64.b64encode(f.read_bytes()).decode())
    except Exception as e:
        print(f"Stop: {e}")
        break
    done[p["id"]] = p["num"]
    caricate += 1
    time.sleep(1.5)
DONE.write_text(json.dumps(done))
print(f"Copertine caricate su Spotify: {caricate}")
