(() => {
  const PAGE = "https://www.intercity.pl/pl/site/dla-pasazera/kup-bilet/wyszukiwarka-kas-i-biletomatow.html";
  const DELAY_MS = 1500;
  const ptext = el => el ? [...el.children].filter(c => c.tagName === "P").map(p => p.innerText.replace(/\s+/g, " ").trim()).filter(Boolean) : [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const sha = async s => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))].map(b => b.toString(16).padStart(2, "0")).join("");

  async function cityRows(city) {
    const u = new URL(PAGE);
    u.searchParams.set("city", city);
    u.searchParams.append("type[0]", "local");
    u.searchParams.append("type[1]", "international");
    const r = await fetch(u);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = new DOMParser().parseFromString(await r.text(), "text/html");
    const rows = [];
    for (const t of d.querySelectorAll("table")) {
      const hdr = [...t.querySelectorAll("th")].map(x => x.innerText.trim());
      if (hdr[0] !== "Adres" || !/Godziny/.test(hdr[1] || "")) continue;
      for (const tr of t.querySelectorAll("tr")) {
        const td = k => tr.querySelector(`td[headers="ic-location-kasy-${k}"]`);
        if (!td(0)) continue;
        const g = ptext(td(1));
        rows.push({ m: city, a: ptext(td(0)), g: g.length ? g : [td(1).innerText.trim()], k: td(2)?.innerText.trim(), i: td(3)?.innerText.trim(), c: td(4)?.innerText.trim(), o: td(6)?.innerText.trim() });
      }
    }
    return rows;
  }

  window.__ic = { done: {}, rows: [], errors: [], finished: false, started: new Date().toISOString() };
  window.__icRun = (async () => {
    const cities = (window.locationData || []).map(c => c.n);
    window.__ic.total = cities.length;
    for (const city of cities) {
      try {
        window.__ic.rows.push(...await cityRows(city));
        window.__ic.done[city] = 1;
      } catch (e) {
        window.__ic.errors.push(city + ": " + e.message);
      }
      await sleep(DELAY_MS);
    }
    const seen = new Set();
    window.__ic.uniq = window.__ic.rows.filter(r => { const k = JSON.stringify(r); if (seen.has(k)) return false; seen.add(k); return true; });
    window.__ic.hashes = [];
    for (const r of window.__ic.uniq) window.__ic.hashes.push((await sha(JSON.stringify(r))).slice(0, 8));
    window.__ic.hashAll = (await sha(JSON.stringify(window.__ic.uniq))).slice(0, 16);
    window.__ic.finished = true;
  })();

  window.__icStatus = () => ({
    finished: window.__ic.finished, done: Object.keys(window.__ic.done).length, total: window.__ic.total,
    rows: (window.__ic.uniq || window.__ic.rows).length, errors: window.__ic.errors, hashAll: window.__ic.hashAll,
  });
  window.__icRowsByHash = list => JSON.stringify(window.__ic.uniq.filter((r, i) => list.includes(window.__ic.hashes[i])));
  window.__icSlice = (a, b) => JSON.stringify(window.__ic.uniq.slice(a, b));
  return "started";
})();
