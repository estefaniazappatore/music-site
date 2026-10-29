#!/usr/bin/env python3
"""
Unisce tutte le playlist-album del 2026 in un'unica playlist Spotify.

Uso:
  1) python3 unisci_album_2026.py scan    -> trova le playlist-album e le scrive in playlist_trovate.txt
  2) controlla il file (cancella le righe che NON vuoi includere)
  3) python3 unisci_album_2026.py merge   -> crea la playlist unica con i brani di quelle playlist

Requisiti: pip3 install spotipy
Variabili d'ambiente (dalla tua app su developer.spotify.com):
  SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET
  SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
"""

import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth

ANNO = "2026"
NOME_PLAYLIST_UNICA = "2026 BEST ALBUMS · Tutti i brani"
FILE_LISTA = "playlist_trovate.txt"
SOGLIA_STESSO_ALBUM = 0.8  # almeno l'80% dei brani dallo stesso album

SCOPE = "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE, open_browser=False, cache_path=".spcache"), retries=10, status_retries=10, backoff_factor=1)


def tutte_le_mie_playlist():
    me = sp.current_user()["id"]
    offset = 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        for p in page["items"]:
            if p and p["owner"]["id"] == me:
                yield p
        if not page["next"]:
            break
        offset += 50


def brani_di(playlist_id):
    """Restituisce [(uri, album_id, added_at)] per tutti i brani della playlist."""
    risultati = []
    page = sp.playlist_items(playlist_id, limit=100, additional_types=["track"])
    while page:
        for it in page["items"]:
            t = it.get("track") or it.get("item")
            if not t or t.get("type") != "track" or not t.get("uri") or t.get("is_local"):
                continue
            album_id = (t.get("album") or {}).get("id")
            risultati.append((t["uri"], album_id, it.get("added_at") or ""))
        page = sp.next(page) if page.get("next") else None
    return risultati


def scan():
    import json, os
    cache = {}
    if os.path.exists("scan_cache.json"):
        cache = json.load(open("scan_cache.json", encoding="utf-8"))
    for p in tutte_le_mie_playlist():
        if p["name"] == NOME_PLAYLIST_UNICA or p["id"] in cache:
            continue
        try:
            brani = brani_di(p["id"])
        except Exception as e:
            print(f"  ! saltata {p['name']}: {e}")
            continue
        voce = {"nome": p["name"], "album": False, "uris": []}
        album = [b[1] for b in brani if b[1]]
        if len(brani) >= 2 and album:
            piu_frequente = max(set(album), key=album.count)
            quota = album.count(piu_frequente) / len(brani)
            if quota >= SOGLIA_STESSO_ALBUM and min(b[2] for b in brani).startswith(ANNO):
                voce = {"nome": p["name"], "album": True, "uris": [b[0] for b in brani]}
                print(f"  \u2713 {p['name']} ({len(brani)} brani)")
        cache[p["id"]] = voce
        json.dump(cache, open("scan_cache.json", "w", encoding="utf-8"), ensure_ascii=False)

    trovate = [(pid, v["nome"], len(v["uris"])) for pid, v in cache.items() if v["album"]]
    with open(FILE_LISTA, "w", encoding="utf-8") as f:
        for pid, nome, n in trovate:
            f.write(f"{pid}\t{nome}\t{n}\n")
    print(f"\nTrovate {len(trovate)} playlist-album del {ANNO}. Lista salvata in {FILE_LISTA}.")


def merge():
    with open(FILE_LISTA, encoding="utf-8") as f:
        ids = [riga.split("\t")[0] for riga in f if riga.strip()]

    import json
    cache = json.load(open("scan_cache.json", encoding="utf-8"))
    uris, visti = [], set()
    for i, pid in enumerate(ids, 1):
        for uri in cache[pid]["uris"]:
            if uri not in visti:
                visti.add(uri)
                uris.append(uri)
        print(f"  letta {i}/{len(ids)}", end="\r")

    me = sp.current_user()["id"]
    nuova = sp.user_playlist_create(
        me, NOME_PLAYLIST_UNICA, public=False,
        description=f"Tutti i brani dei miei migliori album del {ANNO}",
    )
    for start in range(0, len(uris), 100):
        sp.playlist_add_items(nuova["id"], uris[start:start + 100])

    print(f"\nFatto! '{NOME_PLAYLIST_UNICA}': {len(uris)} brani da {len(ids)} album.")
    print(nuova["external_urls"]["spotify"])


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "scan":
        scan()
    elif comando == "merge":
        merge()
    else:
        print(__doc__)
