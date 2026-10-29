// Genera site/covers/<numero>.jpg per ogni playlist Caffè in cuffia e aggiorna data.json.
// Crea solo le copertine che mancano.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DATA = path.join(ROOT, "site", "data.json");
const OUT = path.join(ROOT, "site", "covers");
const TPL = "file://" + path.join(__dirname, "copertina", "cover.html");

(async () => {
  const data = JSON.parse(fs.readFileSync(DATA, "utf8"));
  fs.mkdirSync(OUT, { recursive: true });
  const da_fare = data.playlists.filter(p => p.num && !fs.existsSync(path.join(OUT, `${p.num}.jpg`)));
  if (da_fare.length) {
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 640, height: 640 } });
    for (const p of da_fare) {
      await page.goto(`${TPL}?n=${p.num}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(200);
      await page.screenshot({ path: path.join(OUT, `${p.num}.jpg`), type: "jpeg", quality: 86 });
    }
    await browser.close();
  }
  for (const p of data.playlists) {
    if (p.num && fs.existsSync(path.join(OUT, `${p.num}.jpg`))) {
      p.spotify_img = p.spotify_img || p.img;
      p.img = `/covers/${p.num}.jpg`;
    }
  }
  fs.writeFileSync(DATA, JSON.stringify(data));
  console.log(`Copertine nuove: ${da_fare.length}`);
})();
