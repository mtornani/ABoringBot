"""Polite fetcher with an on-disk raw cache.

Every response is stored under data/raw/<run-date>/<source>/<key>.<ext> and indexed in
data/raw/<run-date>/index.jsonl with URL, retrieval timestamp (UTC) and HTTP status.
A URL already in today's cache is never fetched twice (re-runs are free and reproducible).
"""
import hashlib, json, time, urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124 Safari/537.36")


class Cache:
    def __init__(self, root, run_date):
        self.dir = Path(root) / run_date
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index = self.dir / "index.jsonl"
        self._known = {}
        if self.index.exists():
            for line in self.index.read_text().splitlines():
                r = json.loads(line)
                self._known[r["url"]] = r

    def path_for(self, source, url, ext):
        return self.dir / source / (hashlib.sha1(url.encode()).hexdigest()[:16] + "." + ext)

    def get(self, url):
        r = self._known.get(url)
        if r and r["status"] == 200 and (self.dir / r["file"]).exists():
            return (self.dir / r["file"]).read_text()
        return None

    def status(self, url):
        r = self._known.get(url)
        return r["status"] if r else None

    def put(self, source, url, text, status, ext):
        p = self.path_for(source, url, ext)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        rec = dict(url=url, source=source, file=str(p.relative_to(self.dir)), status=status,
                   retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self._known[url] = rec
        with self.index.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec


class Fetcher:
    """HTTP (requests) fetcher with per-host delay and robots.txt check."""

    def __init__(self, cache, source, delay, check_robots=True):
        self.cache, self.source, self.delay = cache, source, delay
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
        self._last = 0.0
        self._robots = {}
        self.check_robots = check_robots
        self.stats = dict(fetched=0, cached=0, failed=0)

    def allowed(self, url):
        if not self.check_robots:
            return True
        host = urlparse(url).scheme + "://" + urlparse(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self.s.get(host + "/robots.txt", timeout=30).text.splitlines())
            except requests.RequestException:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return rp is None or rp.can_fetch("*", url)

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.time()

    def get(self, url, ext="html", retries=3):
        hit = self.cache.get(url)
        if hit is not None:
            self.stats["cached"] += 1
            return hit
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        for k in range(retries):
            self._wait()
            try:
                r = self.s.get(url, timeout=90)
            except requests.RequestException:
                time.sleep(5 * (k + 1)); continue
            if r.status_code == 200:
                self.stats["fetched"] += 1
                self.cache.put(self.source, url, r.text, 200, ext)
                return r.text
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(10 * (k + 1)); continue
            break
        self.stats["failed"] += 1
        raise RuntimeError(f"fetch failed {url}")


class BrowserFetcher(Fetcher):
    """Same contract, but loads the URL in headless system Chrome (Playwright).

    Used for SofaScore, whose public JSON is only served to browser clients.
    robots.txt is checked through the same browser.
    """

    def __init__(self, cache, source, delay, chrome="/usr/bin/google-chrome"):
        super().__init__(cache, source, delay, check_robots=False)
        self.chrome = chrome
        self._pw = self._b = self._pg = None
        self._disallow = None

    def _page(self):
        if self._pg is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._b = self._pw.chromium.launch(executable_path=self.chrome, headless=True)
            self._pg = self._b.new_page()
        return self._pg

    def allowed(self, url):
        if self._disallow is None:
            pg = self._page()
            u = urlparse(url)
            pg.goto(f"{u.scheme}://{u.netloc}/robots.txt", timeout=60000)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(pg.inner_text("body").splitlines())
            self._disallow = rp
        return self._disallow.can_fetch("*", url)

    def get(self, url, ext="json", retries=3):
        hit = self.cache.get(url)
        if hit is not None:
            self.stats["cached"] += 1
            return hit
        if self.cache.status(url) == 404:
            raise RuntimeError(f"not found (cached 404) {url}")
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        pg = self._page()
        for k in range(retries):
            self._wait()
            try:
                r = pg.goto(url, timeout=60000)
                body = pg.inner_text("body")
            except Exception:
                time.sleep(5 * (k + 1)); continue
            if r and r.status == 200:
                self.stats["fetched"] += 1
                self.cache.put(self.source, url, body, 200, ext)
                return body
            if r and r.status == 404:
                self.cache.put(self.source, url, body, 404, ext)
                break
            time.sleep(10 * (k + 1))
        self.stats["failed"] += 1
        raise RuntimeError(f"fetch failed {url}")

    def close(self):
        if self._b:
            self._b.close(); self._pw.stop()
