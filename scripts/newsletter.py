#!/usr/bin/env python3
"""
Newsletter Caffè in cuffia.

Ogni domenica:
  1. sceglie la prossima playlist (si parte da 10 prima dell'ultima e si va avanti di una);
  2. compone l'email (copertina, testo, uscite della settimana);
  3. la manda subito come ANTEPRIMA a chi ha l'etichetta "anteprima" su Kit;
  4. programma l'invio vero a tutti per lunedì alle 7:30 (ora italiana).

Uso:
  python scripts/newsletter.py              -> anteprima + programmazione del lunedì
  python scripts/newsletter.py --prova      -> solo anteprima, non programma e non avanza
  python scripts/newsletter.py --html x.html -> scrive l'email in un file, senza Kit

Testi: scripts/testi/caffe/<numero>.md contiene solo gli stili musicali
(es. "dal neo soul al jazz elettronico, passando per il lo-fi");
scripts/testi/album/<id_album>.md contiene due righe sull'album.
Se un testo manca, l'email parte con una riga automatica e l'anteprima lo segnala.
"""
import html
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
STATE_FILE = ROOT / "scripts" / "newsletter_stato.json"
TESTI = ROOT / "scripts" / "testi"
SITO = "https://music.estefaniazappatore.it"
ROMA = ZoneInfo("Europe/Rome")
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
e = html.escape


# ---------------------------------------------------------------- scelta contenuti
def stato():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    nums = [p["num"] for p in DATA["playlists"] if p.get("num")]
    return {"prossimo": max(nums) - 10, "ultimo_invio": None}


def playlist_della_settimana(st):
    per_num = {p["num"]: p for p in DATA["playlists"] if p.get("num")}
    n = st["prossimo"]
    while n not in per_num and n <= max(per_num):
        n += 1  # salta numeri mancanti
    return per_num.get(n)


def uscite_della_settimana(st):
    da = st.get("ultimo_invio") or (date.today() - timedelta(days=7)).isoformat()
    limite_uscita = (date.today() - timedelta(days=60)).isoformat()
    nuovi = [a for a in DATA["albums"]
             if (a.get("aggiunto") or "") > da and (a.get("date") or "") >= limite_uscita]
    return sorted(nuovi, key=lambda a: a.get("date") or "", reverse=True)


def leggi_testo(tipo, chiave):
    f = TESTI / tipo / f"{chiave}.md"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def data_it(iso):
    if not iso:
        return ""
    parti = iso.split("-")
    if len(parti) == 3:
        return f"{int(parti[2])} {MESI[int(parti[1]) - 1]} {parti[0]}"
    return parti[0]


def artisti_principali(tracks, n=4):
    conta = {}
    for t in tracks:
        for a in t["a"].split(", "):
            conta[a] = conta.get(a, 0) + 1
    return [a for a, _ in sorted(conta.items(), key=lambda x: -x[1])][:n]


# ---------------------------------------------------------------- email
def paragrafi(testo):
    return "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;color:#3a393f">{e(par)}</p>'
        for par in testo.split("\n\n") if par.strip())


def componi(p, uscite):
    mancanti = []
    art = artisti_principali(p["tracks"], 4)
    elenco = art[0] if len(art) == 1 else ", ".join(art[:-1]) + " e " + art[-1]
    testo = f"La playlist di questa settimana contiene {len(p['tracks'])} brani di artisti come {elenco}."
    stili = leggi_testo("caffe", p["num"])  # es: "dal neo soul al jazz elettronico, passando per il lo-fi"
    if stili:
        testo += f" Questa playlist spazia {stili.rstrip('.')}."
    else:
        mancanti.append(f"Caffè in cuffia #{p['num']} (stili musicali)")
    testo += " Scommetto che aggiungerai almeno un brano tra i tuoi preferiti!"
    minuti = round(sum(t["ms"] for t in p["tracks"]) / 60000)
    cover = f"{SITO}/covers/{p['num']}.jpg"
    blocco_uscite = ""
    if uscite:
        voci = ""
        for a in uscite:
            ta = leggi_testo("album", a["id"])
            if not ta:
                mancanti.append(f"{a['artist']} · {a['title']}")
                ta = f"Uscito il {data_it(a['date'])}, {len(a['tracks'])} brani."
            voci += (
                f'<tr><td style="padding:0 0 18px;width:88px;vertical-align:top">'
                f'<a href="{a["url"]}"><img src="{a["img"]}" width="72" height="72" alt="" '
                f'style="display:block;border-radius:10px;border:0"></a></td>'
                f'<td style="padding:0 0 18px;vertical-align:top">'
                f'<a href="{a["url"]}" style="color:#17161a;text-decoration:none;font-weight:600;font-size:15px">{e(a["title"])}</a>'
                f'<br><span style="color:#6f6e75;font-size:14px">{e(a["artist"])}</span>'
                f'<p style="margin:6px 0 0;font-size:14px;line-height:1.5;color:#3a393f">{e(ta)}</p></td></tr>')
        blocco_uscite = (
            '<tr><td style="padding:34px 32px 8px">'
            '<p style="margin:0 0 6px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#d46aa8">Uscite della settimana</p>'
            '<p style="margin:0 0 18px;font-size:22px;font-weight:600;color:#17161a;letter-spacing:-.02em">Entrati tra i miei album dell\'anno</p>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{voci}</table></td></tr>')

    corpo = f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@500;600&family=Inter:wght@400;500&display=swap" rel="stylesheet"></head>
<body style="margin:0;padding:0;background:#f4f1ea">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1ea;font-family:Inter,Helvetica,Arial,sans-serif">
<tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fbf8f3;border-radius:20px;overflow:hidden">
<tr><td style="padding:26px 32px 0;font-size:14px;color:#6f6e75">
<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f08bc8;margin-right:8px"></span>Caffè in Cuffia: la playlist per iniziare bene la settimana</td></tr>
<tr><td style="padding:18px 32px 0">
<a href="{p['url']}"><img src="{cover}" width="496" alt="Caffè in cuffia #{p['num']}" style="display:block;width:100%;height:auto;border-radius:16px;border:0"></a></td></tr>
<tr><td style="padding:26px 32px 0;font-family:'DM Sans',Helvetica,Arial,sans-serif">
<p style="margin:0 0 4px;font-size:15px;color:#3a393f">Ciao{{% if subscriber.first_name != blank %}} {{{{ subscriber.first_name }}}}{{% endif %}},</p>
<p style="margin:0 0 16px;font-size:30px;line-height:1.1;font-weight:600;letter-spacing:-.03em;color:#17161a">Caffè in cuffia #{p['num']}</p>
{paragrafi(testo)}
<p style="margin:0 0 22px;font-size:13px;color:#8a8990">{len(p['tracks'])} brani · {minuti} minuti</p>
<a href="{p['url']}" style="display:inline-block;background:#17161a;color:#fbf8f3;text-decoration:none;font-weight:500;font-size:15px;padding:14px 26px;border-radius:14px">Ascolta su Spotify</a>
</td></tr>
{blocco_uscite}
<tr><td style="padding:30px 32px 34px;border-top:1px solid #e7e3da">
<a href="{SITO}/caffeincuffia" style="color:#17161a;font-weight:600;font-size:15px;text-decoration:underline">Ascolta tutte le playlist</a>
<p style="margin:6px 0 0;font-size:15px;color:#3a393f">Le trovi tutte, dalla prima all'ultima, sul sito.</p>
<p style="margin:22px 0 0;font-size:15px;color:#3a393f">Buon inizio settimana,<br>Estefania</p>
</td></tr></table></td></tr></table></body></html>"""
    oggetto = f"Caffè in cuffia #{p['num']}"
    if uscite:
        oggetto += f" · e {len(uscite)} {'album nuovo' if len(uscite) == 1 else 'album nuovi'}"
    anteprima = testo.split(".")[0][:120]
    return oggetto, anteprima, corpo, mancanti


# ---------------------------------------------------------------- Kit
def kit(metodo, percorso, corpo=None):
    req = urllib.request.Request(
        f"https://api.kit.com/v4{percorso}", method=metodo,
        data=json.dumps(corpo).encode() if corpo is not None else None,
        headers={"X-Kit-Api-Key": os.environ["KIT_API_KEY"], "Content-Type": "application/json",
                 "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def id_etichetta(nome):
    for t in kit("GET", "/tags?per_page=500").get("tags", []):
        if t["name"].lower() == nome.lower():
            return t["id"]
    raise SystemExit(f'Etichetta "{nome}" non trovata su Kit')


def broadcast(oggetto, anteprima, corpo, send_at, filtro, pubblica):
    dati = {"subject": oggetto, "preview_text": anteprima, "description": oggetto, "content": corpo,
            "public": pubblica, "published_at": datetime.now(ROMA).isoformat(), "send_at": send_at}
    if filtro is not None:
        dati["subscriber_filter"] = filtro
    return kit("POST", "/broadcasts", dati)


def main():
    args = sys.argv[1:]
    st = stato()
    p = playlist_della_settimana(st)
    if not p:
        raise SystemExit("Nessuna playlist disponibile per questa settimana")
    uscite = uscite_della_settimana(st)
    oggetto, anteprima, corpo, mancanti = componi(p, uscite)

    if "--html" in args:
        Path(args[args.index("--html") + 1]).write_text(corpo, encoding="utf-8")
        print(oggetto, "|", "testi mancanti:", mancanti or "nessuno")
        return

    avviso = ""
    if mancanti:
        avviso = ('<div style="background:#fde8f3;padding:14px 18px;font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#17161a">'
                  "<b>Solo nell'anteprima.</b> Manca il testo per: " + e(", ".join(mancanti)) +
                  ". Lunedì partirà con una riga automatica, a meno che non lo aggiungi prima.</div>")
    tag = id_etichetta("anteprima")
    ora = datetime.now(ROMA)
    broadcast("[Anteprima] " + oggetto, anteprima, corpo.replace("<body style=\"margin:0;padding:0;background:#f4f1ea\">",
              "<body style=\"margin:0;padding:0;background:#f4f1ea\">" + avviso),
              (ora + timedelta(minutes=2)).isoformat(),
              [{"all": [{"type": "tag", "ids": [tag]}], "any": None, "none": None}], False)
    print("Anteprima inviata:", oggetto)
    if "--prova" in args:
        return

    lunedi = (ora + timedelta(days=(7 - ora.weekday()) % 7 or 7)).replace(hour=7, minute=30, second=0, microsecond=0)
    broadcast(oggetto, anteprima, corpo, lunedi.isoformat(), None, True)
    print("Programmata per", lunedi.isoformat())
    st["prossimo"] = p["num"] + 1
    st["ultimo_invio"] = date.today().isoformat()
    STATE_FILE.write_text(json.dumps(st, indent=2))


if __name__ == "__main__":
    main()
