# music.estefaniazappatore.it

Caffè in cuffia e Best Albums, con dati presi ogni notte dal mio Spotify.

## Com'è fatto

- `site/` è il sito: `index.html` più `data.json`. Cloudflare Pages pubblica questa cartella.
- `scripts/aggiorna_dati.py` legge Spotify e riscrive `site/data.json`.
- `.github/workflows/aggiorna.yml` lancia lo script ogni notte. Se ci sono novità le salva, e Cloudflare ripubblica da solo.
- `scripts/config.json` contiene le regole:
  - `caffe_pattern`: il testo che riconosce le playlist Caffè in cuffia;
  - `anni_best_albums`: gli anni da mostrare (per aggiungere il 2027 basta scriverlo qui);
  - `anno_da`: `"uscita"` (l'anno di uscita dell'album) oppure `"aggiunta"` (l'anno in cui ho creato la playlist);
  - `escludi`: gli ID di playlist da non mostrare mai;
  - `forza_anno`: per spostare un album di anno, nel formato `{"ID_playlist": "2026"}`.

## Messa online (una volta sola)

1. **GitHub:** crea un repository privato `music-site` e carica tutti questi file.
2. **Segreti:** in Settings → Secrets and variables → Actions aggiungi:
   `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`.
3. **Primo aggiornamento:** in Actions → "Aggiorna dati Spotify" → Run workflow.
4. **Cloudflare:** Workers & Pages → Create → Pages → collega il repository.
   Build command: vuoto. Build output directory: `site`.
5. **Dominio:** nel progetto Pages → Custom domains → `music.estefaniazappatore.it`.
   Nel DNS del dominio (Aruba) aggiungi un record CNAME:
   nome `music`, valore `<nome-progetto>.pages.dev`.

## Aggiornare a mano

Actions → "Aggiorna dati Spotify" → Run workflow.
