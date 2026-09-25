"""
Polite Scraper & Archive Ingestion Engine for Erowid Experience Reports.
Includes disk caching, automatic Wayback Machine fallback, and local file import.
"""

import os
import time
import random
import urllib.request
import urllib.error
from typing import Optional, List, Callable, Dict, Any
from erowid_safedb.models import ExperienceReport
from erowid_safedb.parsers import ErowidExperienceParser
from erowid_safedb.db import Database


class ErowidScraper:
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "(ErowidHarmReductionDatabase/1.0; Non-commercial harm-reduction research)"
    )

    def __init__(self, cache_dir: str = "data/cache/experiences"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, exp_id: int) -> str:
        return os.path.join(self.cache_dir, f"{exp_id}.html")

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

        html_content = None

        # If prefer_wayback is True (recommended because Erowid blocks automated bots with Cloudflare)
        if prefer_wayback:
            html_content = self._fetch_from_wayback(exp_id)
            if not html_content:
                html_content = self._fetch_from_direct(exp_id)
        else:
            html_content = self._fetch_from_direct(exp_id)
            if not html_content:
                html_content = self._fetch_from_wayback(exp_id)

        # Save to disk cache if found
        if html_content:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
            except Exception as e:
                print(f"[Warning] Failed to write cache for {exp_id}: {e}")

        return html_content

    def _fetch_from_direct(self, exp_id: int) -> Optional[str]:
        """Attempts direct fetch from erowid.org with polite headers."""
        url = f"https://www.erowid.org/experiences/exp.php?ID={exp_id}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.erowid.org/experiences/",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Cloudflare challenge triggered
                return None
            print(f"[Direct Fetch] HTTP Error {e.code} for ID {exp_id}")
        except Exception as e:
            print(f"[Direct Fetch] Connection error for ID {exp_id}: {e}")
        return None

    def _fetch_from_wayback(self, exp_id: int) -> Optional[str]:
        """Fetches unmodified raw snapshot from the Internet Archive Wayback Machine."""
        url = f"http://web.archive.org/web/2id_/https://www.erowid.org/experiences/exp.php?ID={exp_id}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.DEFAULT_USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            # Report might not exist or snapshot missing
            return None
        return None

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
        if len(html_content) < 500 or "not found" in html_content.lower()[:300]:
            return None

        report = ErowidExperienceParser.parse_html(html_content, fallback_id=exp_id)
        if report and report.id:
            db.save_experience(report)
            return report
        return None

    def batch_scrape(
        self,
        exp_ids: List[int],
        db: Database,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        callback: Optional[Callable[[int, bool, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Politely scrapes a batch of experience IDs with randomized delays.
        callback signature: callback(exp_id, success, message)
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

            # Only sleep if we actually performed a network request
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
            # Try to derive from filename (e.g. 71809.html)
            base = os.path.basename(file_path)
            digits = "".join([c for c in base if c.isdigit()])
            if digits:
                fallback_id = int(digits)

        report = ErowidExperienceParser.parse_html(html_content, fallback_id=fallback_id)
        if report and report.id:
            db.save_experience(report)
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
