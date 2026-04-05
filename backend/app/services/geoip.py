"""
GeoIP Service

Resolves IP addresses to geographic location and ISP information
using MaxMind GeoLite2 databases.
"""
import logging
import os
import tarfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "geoip"
CITY_DB = DATA_DIR / "GeoLite2-City.mmdb"
ASN_DB = DATA_DIR / "GeoLite2-ASN.mmdb"

_city_reader = None
_asn_reader = None
_init_attempted = False


def _init_readers():
    """Initialize GeoIP database readers (lazy load)."""
    global _city_reader, _asn_reader, _init_attempted

    if _init_attempted:
        return
    _init_attempted = True

    try:
        import geoip2.database

        if CITY_DB.exists():
            _city_reader = geoip2.database.Reader(str(CITY_DB))
            logger.info(f"GeoIP City database loaded: {CITY_DB}")
        else:
            logger.warning(f"GeoIP City database not found at {CITY_DB}")

        if ASN_DB.exists():
            _asn_reader = geoip2.database.Reader(str(ASN_DB))
            logger.info(f"GeoIP ASN database loaded: {ASN_DB}")
        else:
            logger.warning(f"GeoIP ASN database not found at {ASN_DB}")

    except ImportError:
        logger.warning("geoip2 library not installed, GeoIP lookups disabled")
    except Exception as e:
        logger.error(f"Failed to initialize GeoIP: {e}")


def lookup_ip(ip: str) -> dict:
    """Lookup geographic and ISP info for an IP address.

    Returns dict with keys: country, country_code, city, isp, asn
    All values may be None if lookup fails.
    """
    _init_readers()

    result = {
        "country": None,
        "country_code": None,
        "city": None,
        "isp": None,
        "asn": None,
    }

    if not ip or ip.startswith(("10.", "192.168.", "172.16.", "172.17.", "127.")):
        return result  # Skip private/local IPs

    # City lookup
    if _city_reader:
        try:
            city_resp = _city_reader.city(ip)
            result["country"] = city_resp.country.name
            result["country_code"] = city_resp.country.iso_code
            result["city"] = city_resp.city.name
        except Exception:
            pass

    # ASN/ISP lookup
    if _asn_reader:
        try:
            asn_resp = _asn_reader.asn(ip)
            result["asn"] = asn_resp.autonomous_system_number
            result["isp"] = asn_resp.autonomous_system_organization
        except Exception:
            pass

    return result


def download_databases():
    """Download GeoLite2 free databases from GitHub mirror.

    Uses the public dp-ip/geoip mirror which provides up-to-date
    GeoLite2 databases without requiring a MaxMind license key.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    urls = {
        "GeoLite2-City.mmdb": "https://github.com/P3TERX/GeoLite.mmdb/releases/latest/download/GeoLite2-City.mmdb",
        "GeoLite2-ASN.mmdb": "https://github.com/P3TERX/GeoLite.mmdb/releases/latest/download/GeoLite2-ASN.mmdb",
    }

    for filename, url in urls.items():
        dest = DATA_DIR / filename
        try:
            logger.info(f"Downloading {filename}...")
            with httpx.Client(follow_redirects=True, timeout=60) as client:
                resp = client.get(url)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
            logger.info(f"Downloaded {filename} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")

    # Re-init readers with new databases
    global _init_attempted, _city_reader, _asn_reader
    _init_attempted = False
    _city_reader = None
    _asn_reader = None
    _init_readers()


def ensure_databases():
    """Download databases if they don't exist."""
    if not CITY_DB.exists() or not ASN_DB.exists():
        logger.info("GeoIP databases missing, downloading...")
        download_databases()
