// Cloudflare Pages Function: /api/now
// Restituisce il brano che Estefania sta ascoltando (o l'ultimo ascoltato).
// Variabili da impostare su Cloudflare (Settings → Variables and Secrets):
//   SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
const CACHE_SECONDS = 45; // una sola richiesta a Spotify ogni 45 secondi, qualunque sia il traffico

async function accessToken(env) {
  const cache = caches.default;
  const key = new Request("https://cache.local/spotify-token");
  const hit = await cache.match(key);
  if (hit) return (await hit.json()).token;
  const r = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: "Basic " + btoa(`${env.SPOTIFY_CLIENT_ID}:${env.SPOTIFY_CLIENT_SECRET}`),
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: env.SPOTIFY_REFRESH_TOKEN }),
  });
  if (!r.ok) throw new Error("token " + r.status);
  const j = await r.json();
  await cache.put(key, new Response(JSON.stringify({ token: j.access_token }), {
    headers: { "Cache-Control": `max-age=${(j.expires_in || 3600) - 300}` },
  }));
  return j.access_token;
}

const brano = (t, extra) => t && t.type === "track" ? {
  t: t.name,
  a: t.artists.map(a => a.name).join(", "),
  img: (t.album.images[2] || t.album.images[0] || {}).url || null,
  url: t.external_urls.spotify,
  id: t.id,
  ...extra,
} : null;

export async function onRequestGet({ env }) {
  const cache = caches.default;
  const key = new Request("https://cache.local/now");
  const hit = await cache.match(key);
  if (hit) return hit;

  let out = { playing: false, track: null };
  try {
    const token = await accessToken(env);
    const h = { Authorization: `Bearer ${token}` };
    const now = await fetch("https://api.spotify.com/v1/me/player/currently-playing", { headers: h });
    if (now.status === 200) {
      const j = await now.json();
      if (j && j.item && j.is_playing) out = { playing: true, track: brano(j.item) };
    }
    if (!out.playing) {
      const rec = await fetch("https://api.spotify.com/v1/me/player/recently-played?limit=1", { headers: h });
      if (rec.ok) {
        const j = await rec.json();
        const it = j.items && j.items[0];
        if (it) out = { playing: false, track: brano(it.track, { played_at: it.played_at }) };
      }
    }
  } catch (e) {
    out = { playing: false, track: null, error: true };
  }
  const res = new Response(JSON.stringify(out), {
    headers: { "Content-Type": "application/json", "Cache-Control": `public, max-age=${CACHE_SECONDS}` },
  });
  await cache.put(key, res.clone());
  return res;
}
