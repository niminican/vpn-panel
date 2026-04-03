"""
Device detection from User-Agent strings.

Parses User-Agent headers to extract device type, OS, and browser info.
"""
import re


def parse_user_agent(ua: str | None) -> dict:
    """Parse User-Agent string into device info.

    Returns dict with keys: device_type, os, browser, raw
    """
    if not ua:
        return {"device_type": "Unknown", "os": "Unknown", "browser": "Unknown", "raw": ""}

    result = {"device_type": "Desktop", "os": "Unknown", "browser": "Unknown", "raw": ua}

    # OS detection
    if "iPhone" in ua or "iPad" in ua:
        result["os"] = "iOS"
        result["device_type"] = "iPhone" if "iPhone" in ua else "iPad"
        # Extract iOS version
        m = re.search(r'OS (\d+[_\.]\d+)', ua)
        if m:
            result["os"] = f"iOS {m.group(1).replace('_', '.')}"
    elif "Android" in ua:
        result["os"] = "Android"
        result["device_type"] = "Mobile"
        m = re.search(r'Android (\d+\.?\d*)', ua)
        if m:
            result["os"] = f"Android {m.group(1)}"
        # Check for tablet
        if "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
            result["device_type"] = "Tablet"
    elif "Windows" in ua:
        result["os"] = "Windows"
        if "Windows NT 10" in ua:
            result["os"] = "Windows 10/11"
        elif "Windows NT 6.3" in ua:
            result["os"] = "Windows 8.1"
        elif "Windows NT 6.1" in ua:
            result["os"] = "Windows 7"
    elif "Mac OS X" in ua or "macOS" in ua:
        result["os"] = "macOS"
        m = re.search(r'Mac OS X (\d+[_\.]\d+)', ua)
        if m:
            result["os"] = f"macOS {m.group(1).replace('_', '.')}"
    elif "Linux" in ua:
        result["os"] = "Linux"
    elif "CrOS" in ua:
        result["os"] = "Chrome OS"

    # Browser detection
    if "Edg/" in ua:
        result["browser"] = "Edge"
    elif "Chrome/" in ua and "Chromium" not in ua:
        result["browser"] = "Chrome"
    elif "Firefox/" in ua:
        result["browser"] = "Firefox"
    elif "Safari/" in ua and "Chrome" not in ua:
        result["browser"] = "Safari"
    elif "OPR/" in ua or "Opera" in ua:
        result["browser"] = "Opera"

    # WireGuard client detection
    if "WireGuard" in ua:
        result["browser"] = "WireGuard Client"
        result["device_type"] = "VPN Client"

    return result


def format_device_info(ua: str | None) -> str:
    """Format User-Agent into a human-readable device string.

    Returns e.g. "iPhone (iOS 17.2) Safari" or "Desktop (Windows 10/11) Chrome"
    """
    info = parse_user_agent(ua)
    if info["device_type"] == "Unknown":
        return "Unknown"
    return f"{info['device_type']} ({info['os']}) {info['browser']}"
