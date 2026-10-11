// LiteLecture service worker — makes the app fully usable offline.
const CACHE = "litelecture-v3";
const PRECACHE = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icon.svg",
  "/demos/limits-intro.litelec",
  "/demos/algebra.litelec",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// Strategy:
//  * NETWORK-FIRST for things that change between deploys (page navigations
//    and the published-lectures manifest) — falls back to cache offline.
//  * CACHE-FIRST for everything else (app assets, .litelec lecture files) —
//    fast and fully offline once seen.
function networkFirst(req) {
  return fetch(req)
    .then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((cache) => cache.put(req, copy));
      return res;
    })
    .catch(() =>
      caches.match(req).then((cached) => {
        if (cached) return cached;
        if (req.mode === "navigate") return caches.match("/index.html");
      })
    );
}

function cacheFirst(req) {
  return caches.match(req).then((cached) => {
    if (cached) return cached;
    return fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy));
        return res;
      })
      .catch(() => {
        if (req.mode === "navigate") return caches.match("/index.html");
      });
  });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  const fresh = req.mode === "navigate" || url.pathname === "/demos/index.json";
  event.respondWith(fresh ? networkFirst(req) : cacheFirst(req));
});
