"""
Polite Scraper, Archival Ingestion Engine & Master Catalog Harvester for Erowid.
Includes disk caching, automatic Wayback Machine fallback, parallel batch scraping, and full-site indexing.
"""

import os
import re
import time
import json
import gzip
import random
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Callable, Dict, Any

from erowid_safedb.models import (
    ExperienceReport,
    CatalogEntry,
    ReportIndexItem,
)
from erowid_safedb.parsers import ErowidExperienceParser
from erowid_safedb.db import Database


def decode_http_response(raw_bytes: bytes) -> str:
    """Decompresses gzip/deflate if needed and decodes with robust encoding fallback."""
    if not raw_bytes:
        return ""
    if raw_bytes.startswith(b"\x1f\x8b"):
        try:
            raw_bytes = gzip.decompress(raw_bytes)
        except Exception:
            pass
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin1", errors="ignore")


class ErowidScraper:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "(ErowidHarmReductionDatabase/2.0; Non-commercial harm-reduction research)"
    )

    def __init__(self, cache_dir: str = "data/cache/experiences"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, exp_id: int) -> str:
        return os.path.join(self.cache_dir, f"{exp_id}.html")

    def fetch_url(self, url: str, prefer_wayback: bool = True, timeout: int = 15) -> Optional[str]:
        """
        Fetches an arbitrary Erowid URL.
        Falls back to Wayback Machine snapshot if direct fetch hits Cloudflare or fails.
        """
        # Ensure full URL
        if url.startswith("/"):
            url = f"https://www.erowid.org{url}"
        elif not url.startswith("http"):
            url = f"https://www.erowid.org/experiences/{url}"

        # If prefer_wayback, attempt Wayback first
        if prefer_wayback:
            content = self._fetch_url_wayback(url, timeout=timeout)
            if content:
                return content
            return self._fetch_url_direct(url, timeout=timeout)
        else:
            content = self._fetch_url_direct(url, timeout=timeout)
            if content:
                return content
            return self._fetch_url_wayback(url, timeout=timeout)

    def _fetch_url_direct(self, url: str, timeout: int = 12) -> Optional[str]:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.erowid.org/",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return decode_http_response(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return None
        except Exception:
            return None
        return None

    def _fetch_url_wayback(self, url: str, timeout: int = 15) -> Optional[str]:
        # Direct raw snapshot prefix
        wb_url = f"http://web.archive.org/web/2id_/{url}"
        req = urllib.request.Request(
            wb_url,
            headers={"User-Agent": self.DEFAULT_USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return decode_http_response(resp.read())
        except Exception:
            pass

        # Fallback to Wayback Availability API
        try:
            api_url = f"https://archive.org/wayback/available?url={urllib.request.quote(url, safe='')}"
            api_req = urllib.request.Request(api_url, headers={"User-Agent": self.DEFAULT_USER_AGENT})
            with urllib.request.urlopen(api_req, timeout=8) as a_resp:
                data = json.loads(a_resp.read().decode())
                snap_url = data.get("archived_snapshots", {}).get("closest", {}).get("url")
                if snap_url:
                    parts = snap_url.split("/web/")
                    if len(parts) == 2:
                        ts, rest = parts[1].split("/", 1)
                        raw_url = f"{parts[0]}/web/{ts}id_/{rest}"
                        with urllib.request.urlopen(raw_url, timeout=timeout) as r_resp:
                            return decode_http_response(r_resp.read())
        except Exception:
            pass

        return None

    def fetch_experience_html(
        self,
        exp_id: int,
        use_cache: bool = True,
        prefer_wayback: bool = True
    ) -> Optional[str]:
        """
        Fetches the HTML of an experience report.
        Checks local disk cache first, then attempts Wayback Machine or direct Erowid.
        """
        cache_path = self._get_cache_path(exp_id)
        if use_cache and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        target_url = f"https://www.erowid.org/experiences/exp.php?ID={exp_id}"
        html_content = self.fetch_url(target_url, prefer_wayback=prefer_wayback, timeout=15)

        # Save to disk cache if found
        if html_content and len(html_content) > 300 and "not found" not in html_content.lower()[:300]:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
            except Exception as e:
                print(f"[Warning] Failed to write cache for {exp_id}: {e}")

        return html_content

    def fetch_and_save_experience(
        self,
        exp_id: int,
        db: Database,
        use_cache: bool = True
    ) -> Optional[ExperienceReport]:
        """Fetches, parses, and saves a single experience report to the database."""
        html_content = self.fetch_experience_html(exp_id, use_cache=use_cache)
        if not html_content:
            return None

        # Validate that the HTML actually has content and is not an error page
        if len(html_content) < 300 or "not found" in html_content.lower()[:300]:
            return None

        report = ErowidExperienceParser.parse_html(html_content, fallback_id=exp_id)
        if report and report.id:
            db.save_experience(report)
            db.mark_report_scraped(report.id)
            return report
        return None

    def index_catalog(self, db: Database, exp_list_path: str = "data/cache/exp_list.shtml") -> int:
        """
        Parses all substances and their category index links from exp_list.shtml
        and saves them into the erowid_catalog database table.
        """
        if not os.path.exists(exp_list_path):
            # Fetch from archive
            print("Downloading master substance directory (exp_list.shtml)...")
            content = self.fetch_url("https://www.erowid.org/experiences/exp_list.shtml", prefer_wayback=True, timeout=20)
            if not content:
                raise RuntimeError("Failed to fetch exp_list.shtml from Erowid or Wayback Machine.")
            os.makedirs(os.path.dirname(exp_list_path), exist_ok=True)
            with open(exp_list_path, "w", encoding="latin1") as f:
                f.write(content)

        with open(exp_list_path, "r", encoding="latin1") as f:
            text = f.read()

        chunks = text.split("<A NAME=")[1:]
        entries: List[CatalogEntry] = []

        for c in chunks:
            m = re.match(r'[\"\']?([^\"\' >]+)[\"\']?>', c)
            if not m:
                continue
            raw_name = m.group(1).replace('"', '').strip()
            # Skip A-Z letter anchors
            if len(raw_name) == 1 and raw_name.isalpha():
                continue

            # Master link
            master_m = re.search(r'href=[\"\'](subs/exp_([A-Za-z0-9_]+)\.shtml)[\"\']', c, re.I)
            master_url = master_m.group(1) if master_m else ""
            slug = master_m.group(2).lower() if master_m else re.sub(r'[^a-zA-Z0-9]', '', raw_name).lower()

            # Description / synonyms
            desc_m = re.search(r'-\s*\(([^)]+)\)', c)
            desc = desc_m.group(1).strip() if desc_m else ""
            synonyms = [s.strip() for s in desc.split(",") if s.strip() and not s.strip().startswith("see also")]

            # Category links
            cat_links: Dict[str, str] = {}
            for curl, cname in re.findall(r'<A\s+HREF=[\"\'](subs/exp_[^\"\']+)[\"\']>([^<]+)</A>', c, re.I):
                cname_clean = cname.strip()
                if cname_clean and cname_clean.lower() not in ["u", raw_name.lower()]:
                    cat_links[cname_clean] = curl

            if master_url and not cat_links.get("Master"):
                cat_links["Master"] = master_url

            entries.append(CatalogEntry(
                slug=slug,
                name=raw_name,
                description=desc,
                synonyms=synonyms,
                master_url=master_url,
                categories=cat_links,
                vault_url=f"/chemicals/{slug}/{slug}.shtml" if slug else None,
                total_reports=0
            ))

        db.bulk_save_catalog_entries(entries)
        return len(entries)

    def harvest_substance_reports(
        self,
        substance_slug_or_name: str,
        db: Database,
        callback: Optional[Callable[[str, int], None]] = None
    ) -> int:
        """
        Discovers all individual Experience Report IDs for a substance by parsing its
        category index pages and saving them into erowid_report_index.
        """
        cat_entry = db.get_catalog_entry(substance_slug_or_name)
        if not cat_entry:
            # Try to index catalog if empty
            if db.get_catalog_stats()["total_catalog_substances"] == 0:
                self.index_catalog(db)
                cat_entry = db.get_catalog_entry(substance_slug_or_name)

        if not cat_entry:
            return 0

        total_harvested = 0
        items_to_save: List[ReportIndexItem] = []

        # Pages to inspect: all categories plus master
        pages_to_fetch = list(cat_entry.categories.items())
        if not pages_to_fetch and cat_entry.master_url:
            pages_to_fetch.append(("Master", cat_entry.master_url))

        for cat_name, page_url in pages_to_fetch:
            html = self.fetch_url(page_url, prefer_wayback=True, timeout=15)
            if not html:
                continue

            # Look for experience links: exp.php?ID=(\d+)
            found_ids = set()
            for m in re.finditer(r'exp\.php\?ID=(\d+)', html):
                eid = int(m.group(1))
                if eid not in found_ids:
                    found_ids.add(eid)
                    items_to_save.append(ReportIndexItem(
                        id=eid,
                        substance_slug=cat_entry.slug,
                        category=cat_name,
                        title="",
                        author="",
                        status="pending"
                    ))

            if callback:
                callback(cat_name, len(found_ids))

        if items_to_save:
            total_harvested = db.save_report_index_items(items_to_save)
            cat_entry.total_reports = total_harvested
            db.save_catalog_entry(cat_entry)

        return total_harvested

    def harvest_priority_reports(
        self,
        db: Database,
        max_substances: int = 50,
        callback: Optional[Callable[[str, str, int], None]] = None
    ) -> int:
        """
        Harvests safety-critical experience report IDs (Health Problems, Bad Trips,
        Train Wrecks, Combinations) across substances into erowid_report_index.
        """
        if db.get_catalog_stats()["total_catalog_substances"] == 0:
            self.index_catalog(db)

        catalog = db.get_all_catalog_entries()
        priority_keywords = ["health", "bad", "train", "wreck", "disaster", "combo", "combination", "difficult"]

        total_harvested = 0
        count = 0

        for entry in catalog:
            if count >= max_substances:
                break

            items_to_save: List[ReportIndexItem] = []
            for cat_name, cat_url in entry.categories.items():
                if any(k in cat_name.lower() for k in priority_keywords):
                    html = self.fetch_url(cat_url, prefer_wayback=True, timeout=12)
                    if not html:
                        continue
                    found = set(re.findall(r'exp\.php\?ID=(\d+)', html))
                    for eid_str in found:
                        eid = int(eid_str)
                        items_to_save.append(ReportIndexItem(
                            id=eid,
                            substance_slug=entry.slug,
                            category=cat_name,
                            status="pending"
                        ))
                    if callback:
                        callback(entry.name, cat_name, len(found))

            if items_to_save:
                total_harvested += db.save_report_index_items(items_to_save)
                count += 1

        return total_harvested

    def scrape_harvested_batch(
        self,
        db: Database,
        substance_slug: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
        max_workers: int = 3,
        delay: float = 1.0,
        callback: Optional[Callable[[int, bool, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Pulls unscraped reports from erowid_report_index and downloads them
        in parallel with a worker pool and rate limits.
        """
        unscraped = db.get_unscraped_reports(substance_slug=substance_slug, category=category, limit=limit)
        results = {"success": 0, "failed": 0, "total": len(unscraped)}

        if not unscraped:
            return results

        def _worker(item: ReportIndexItem) -> Tuple[int, bool, str]:
            try:
                time.sleep(random.uniform(0.1, delay))
                rep = self.fetch_and_save_experience(item.id, db, use_cache=True)
                if rep:
                    return (item.id, True, f"Saved: {rep.title} ({rep.substance_summary})")
                else:
                    return (item.id, False, "Report empty or not archived")
            except Exception as e:
                return (item.id, False, str(e))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(_worker, it): it.id for it in unscraped}
            for future in as_completed(future_to_id):
                eid, ok, msg = future.result()
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                if callback:
                    callback(eid, ok, msg)

        return results

    def batch_scrape(
        self,
        exp_ids: List[int],
        db: Database,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        callback: Optional[Callable[[int, bool, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Politely scrapes a batch of experience IDs sequentially with randomized delays.
        """
        results = {"success": 0, "failed": 0, "skipped_cached": 0}

        for i, exp_id in enumerate(exp_ids):
            cache_path = self._get_cache_path(exp_id)
            is_cached = os.path.exists(cache_path)

            try:
                report = self.fetch_and_save_experience(exp_id, db, use_cache=True)
                if report:
                    results["success"] += 1
                    if is_cached:
                        results["skipped_cached"] += 1
                    if callback:
                        callback(exp_id, True, f"Saved: {report.title} ({report.substance_summary})")
                else:
                    results["failed"] += 1
                    if callback:
                        callback(exp_id, False, "Report not available or empty")
            except Exception as e:
                results["failed"] += 1
                if callback:
                    callback(exp_id, False, f"Error: {e}")

            if not is_cached and i < len(exp_ids) - 1:
                sleep_time = random.uniform(min_delay, max_delay)
                time.sleep(sleep_time)

        return results

    def import_local_html(
        self,
        file_path: str,
        db: Database,
        fallback_id: Optional[int] = None
    ) -> Optional[ExperienceReport]:
        """Imports an experience report from a local HTML file."""
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        if fallback_id is None:
            base = os.path.basename(file_path)
            digits = "".join([c for c in base if c.isdigit()])
            if digits:
                fallback_id = int(digits)

        report = ErowidExperienceParser.parse_html(html_content, fallback_id=fallback_id)
        if report and report.id:
            db.save_experience(report)
            db.mark_report_scraped(report.id)
            return report
        return None

    def import_local_directory(
        self,
        dir_path: str,
        db: Database,
        callback: Optional[Callable[[str, bool, str], None]] = None
    ) -> int:
        """Batch imports all .html / .htm files from a local directory."""
        if not os.path.exists(dir_path):
            return 0

        imported_count = 0
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith((".html", ".htm")):
                    path = os.path.join(root, file)
                    try:
                        report = self.import_local_html(path, db)
                        if report:
                            imported_count += 1
                            if callback:
                                callback(file, True, f"Imported Exp #{report.id}: {report.title}")
                        else:
                            if callback:
                                callback(file, False, "Could not parse report")
                    except Exception as e:
                        if callback:
                            callback(file, False, f"Failed: {e}")
        return imported_count
