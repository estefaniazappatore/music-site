#!/usr/bin/env python3
"""
Legge le tue playlist Spotify e scrive site/data.json per music.estefaniazappatore.it.

- Caffè in cuffia: tutte le tue playlist il cui nome contiene "Caffè in cuffia".
- Best Albums: le tue playlist fatte di un solo album (almeno l'80% dei brani dallo
  stesso album), con album uscito negli anni indicati in config.json.

Per non sprecare richieste (Spotify ha un limite giornaliero), una playlist viene
riletta solo se è cambiata da ieri (Spotify la segnala con lo "snapshot_id").
Se il limite scatta a metà, lo script salva quello che ha e riprende alla prossima esecuzione.

Variabili d'ambiente:
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text(encoding="utf-8"))
CACHE_FILE = ROOT / "scripts" / "cache.json"
OUT_FILE = ROOT / "site" / "data.json"
SCOPE = "playlist-read-private playlist-read-collaborative user-top-read"


class LimiteRaggiunto(Exception):
    pass


def client():
    token = {
        "access_token": "",
        "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
        "expires_at": 0,
        "scope": SCOPE,
        "token_type": "Bearer",
    }
    auth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri="http://127.0.0.1:8888/callback",
        scope=SCOPE,
        open_browser=False,
        cache_handler=MemoryCacheHandler(token_info=token),
    )
    # retries bassi: se Spotify ci blocca per ore non ha senso aspettare
    return spotipy.Spotify(auth_manager=auth, retries=3, status_retries=3, backoff_factor=2)


def chiama(fn, *args, **kw):
    __import__("time").sleep(0.4)
    try:
        return fn(*args, **kw)
    except SpotifyException as e:
        if e.http_status == 429 or "Max Retries" in str(e):
            raise LimiteRaggiunto() from e
        raise


def mie_playlist(sp, me):
    offset = 0
    while True:
        page = chiama(sp.current_user_playlists, limit=50, offset=offset)
        for p in page["items"]:
            if p and p["owner"]["id"] == me:
                yield p
        if not page["next"]:
            return
        offset += 50


def leggi_brani(sp, pid):
    brani = []
    page = chiama(sp.playlist_items, pid, limit=100, additional_types=["track"])
    while page:
        for it in page["items"]:
            t = it.get("item") or it.get("track")
            if not t or t.get("type") != "track" or it.get("is_local"):
                continue
            alb = t.get("album") or {}
            imgs = alb.get("images") or []
            brani.append({
                "t": t.get("name", ""),
                "a": ", ".join(a["name"] for a in t.get("artists", [])),
                "ms": t.get("duration_ms", 0),
                "added": (it.get("added_at") or "")[:10],
                "album": {
                    "id": alb.get("id"),
                    "name": alb.get("name"),
                    "artist": ", ".join(a["name"] for a in alb.get("artists", [])),
                    "date": alb.get("release_date"),
                    "img": (imgs[1] if len(imgs) > 1 else imgs[0])["url"] if imgs else None,
                    "url": (alb.get("external_urls") or {}).get("spotify"),
                },
            })
        page = chiama(sp.next, page) if page.get("next") else None
    return brani


def classifica(p, brani):
    """Restituisce ('caffe', voce) | ('album', voce) | (None, None)."""
    nome = p["name"]
    if p["id"] in CONFIG["escludi"]:
        return None, None
    tracce = [{"t": b["t"], "a": b["a"], "ms": b["ms"]} for b in brani]
    aggiunte = sorted(b["added"] for b in brani if b["added"])

    if re.search(CONFIG["caffe_pattern"], nome, re.I):
        imgs = p.get("images") or []
        num = re.search(r"(\d+)", nome)
        return "caffe", {
            "id": p["id"], "title": nome, "num": int(num.group(1)) if num else None,
            "date": aggiunte[0] if aggiunte else None,
            "img": imgs[0]["url"] if imgs else None,
            "url": p["external_urls"]["spotify"], "tracks": tracce,
        }

    if len(brani) < 2:
        return None, None
    ids = [b["album"]["id"] for b in brani if b["album"]["id"]]
    if not ids:
        return None, None
    top = max(set(ids), key=ids.count)
    if ids.count(top) / len(brani) < CONFIG["soglia_stesso_album"]:
        return None, None
    alb = next(b["album"] for b in brani if b["album"]["id"] == top)
    if p["id"] in CONFIG["forza_anno"]:
        anno = CONFIG["forza_anno"][p["id"]]
    elif CONFIG["anno_da"] == "aggiunta":
        anno = aggiunte[0][:4] if aggiunte else None
    else:
        anno = (alb["date"] or "")[:4]
    if anno not in CONFIG["anni_best_albums"]:
        return None, None
    return "album", {
        "id": alb["id"], "playlist": p["id"], "year": anno,
        "title": alb["name"], "artist": alb["artist"], "date": alb["date"],
        "img": alb["img"], "url": alb["url"], "tracks": tracce,
        "aggiunto": aggiunte[0] if aggiunte else None,
    }


def main():
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    sp = client()
    parziale = False
    lette = 0
    viste = set()
    try:
        me = chiama(sp.current_user)["id"]
        for p in mie_playlist(sp, me):
            viste.add(p["id"])
            vecchia = cache.get(p["id"])
            if vecchia and vecchia.get("snapshot") == p["snapshot_id"]:
                continue
            totale = (p.get("items") or p.get("tracks") or {}).get("total", 0)
            e_caffe = re.search(CONFIG["caffe_pattern"], p["name"], re.I)
            if not e_caffe and not (2 <= totale <= CONFIG["max_brani_album"]):
                cache[p["id"]] = {"snapshot": p["snapshot_id"], "tipo": None}
                continue
            brani = leggi_brani(sp, p["id"])
            tipo, voce = classifica(p, brani)
            cache[p["id"]] = {"snapshot": p["snapshot_id"], "tipo": tipo, "voce": voce}
            lette += 1
            if lette % 25 == 0:
                CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        # playlist cancellate da Spotify: via anche dal sito
        for pid in list(cache):
            if pid not in viste:
                del cache[pid]
    except LimiteRaggiunto:
        parziale = True
        print("Limite di Spotify raggiunto: salvo i progressi e riprendo alla prossima esecuzione.")

    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    voci = [v for v in cache.values() if v.get("tipo")]
    albums = [v["voce"] for v in voci if v["tipo"] == "album"]
    playlists = [v["voce"] for v in voci if v["tipo"] == "caffe"]
    # stesso album in due playlist: tienilo una volta sola
    unici = {}
    for a in albums:
        unici.setdefault((a["id"], a["year"]), a)
    top = []
    try:
        for t in chiama(sp.current_user_top_tracks, limit=10, time_range="short_term")["items"]:
            imgs = (t.get("album") or {}).get("images") or []
            top.append({"id": t["id"], "t": t["name"], "a": ", ".join(a["name"] for a in t["artists"]),
                        "img": (imgs[1] if len(imgs) > 1 else imgs[0])["url"] if imgs else None,
                        "url": t["external_urls"]["spotify"]})
    except Exception as e:
        print("Top 10 non disponibile:", e)
        vecchio = json.loads(OUT_FILE.read_text(encoding="utf-8")) if OUT_FILE.exists() else {}
        top = vecchio.get("top", [])
    data = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "top": top,
        "albums": list(unici.values()),
        "playlists": playlists,
    }
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    anni = {y: sum(1 for a in data["albums"] if a["year"] == y) for y in CONFIG["anni_best_albums"]}
    print(f"Playlist rilette oggi: {lette}{' (parziale)' if parziale else ''}")
    print(f"Caffè in cuffia: {len(playlists)} · Best Albums: {anni}")


if __name__ == "__main__":
    sys.exit(main())
