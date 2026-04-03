#!/usr/bin/env python3
"""Generate VPN Panel Architecture Diagram PDF using ReportLab drawing primitives."""

from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Group, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# ── Color Palette ─────────────────────────────────────────────
C = {
    'bg':           HexColor('#f8fafc'),
    'title':        HexColor('#0f172a'),
    'subtitle':     HexColor('#475569'),
    # Boxes
    'client_bg':    HexColor('#dbeafe'),
    'client_bd':    HexColor('#3b82f6'),
    'client_hd':    HexColor('#1d4ed8'),
    'fe_bg':        HexColor('#e0e7ff'),
    'fe_bd':        HexColor('#6366f1'),
    'fe_hd':        HexColor('#4338ca'),
    'api_bg':       HexColor('#fef3c7'),
    'api_bd':       HexColor('#f59e0b'),
    'api_hd':       HexColor('#d97706'),
    'svc_bg':       HexColor('#d1fae5'),
    'svc_bd':       HexColor('#10b981'),
    'svc_hd':       HexColor('#059669'),
    'sys_bg':       HexColor('#fce7f3'),
    'sys_bd':       HexColor('#ec4899'),
    'sys_hd':       HexColor('#db2777'),
    'db_bg':        HexColor('#e0f2fe'),
    'db_bd':        HexColor('#0ea5e9'),
    'db_hd':        HexColor('#0284c7'),
    'sched_bg':     HexColor('#faf5ff'),
    'sched_bd':     HexColor('#a855f7'),
    'sched_hd':     HexColor('#7e22ce'),
    'ext_bg':       HexColor('#fff7ed'),
    'ext_bd':       HexColor('#f97316'),
    'ext_hd':       HexColor('#ea580c'),
    'sec_bg':       HexColor('#fef2f2'),
    'sec_bd':       HexColor('#ef4444'),
    'sec_hd':       HexColor('#dc2626'),
    'model_bg':     HexColor('#f0fdf4'),
    'model_bd':     HexColor('#22c55e'),
    'model_hd':     HexColor('#16a34a'),
    # Arrows
    'arrow_blue':   HexColor('#3b82f6'),
    'arrow_green':  HexColor('#10b981'),
    'arrow_orange': HexColor('#f97316'),
    'arrow_purple': HexColor('#a855f7'),
    'arrow_red':    HexColor('#ef4444'),
    'arrow_gray':   HexColor('#94a3b8'),
    # Text
    'text_dark':    HexColor('#1e293b'),
    'text_light':   HexColor('#64748b'),
    'text_white':   white,
}


def draw_rounded_box(c, x, y, w, h, header_text, items, bg, bd, hd, header_h=18, font_size=7.5, item_font_size=6.8):
    """Draw a rounded box with colored header and item list."""
    r = 6
    # Shadow
    c.setFillColor(HexColor('#00000015'))
    c.roundRect(x+2, y-2, w, h, r, fill=1, stroke=0)
    # Body
    c.setStrokeColor(bd)
    c.setLineWidth(1.2)
    c.setFillColor(bg)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)
    # Header bar
    c.setFillColor(hd)
    c.roundRect(x, y + h - header_h, w, header_h, r, fill=1, stroke=0)
    # Fix bottom corners of header
    c.rect(x, y + h - header_h, w, r, fill=1, stroke=0)
    # Header text
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(x + w/2, y + h - header_h + 5, header_text)
    # Items
    c.setFillColor(C['text_dark'])
    c.setFont("Helvetica", item_font_size)
    line_y = y + h - header_h - 12
    for item in items:
        if line_y < y + 4:
            break
        c.drawString(x + 8, line_y, f"  {item}")
        line_y -= 10


def draw_arrow(c, x1, y1, x2, y2, color, dashed=False, label=None, label_offset=0):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    c.setStrokeColor(color)
    c.setLineWidth(1.5)
    if dashed:
        c.setDash(4, 3)
    else:
        c.setDash()

    c.line(x1, y1, x2, y2)
    c.setDash()

    # Arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 8
    arrow_angle = 0.45
    ax1 = x2 - arrow_len * math.cos(angle - arrow_angle)
    ay1 = y2 - arrow_len * math.sin(angle - arrow_angle)
    ax2 = x2 - arrow_len * math.cos(angle + arrow_angle)
    ay2 = y2 - arrow_len * math.sin(angle + arrow_angle)

    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(ax1, ay1)
    p.lineTo(ax2, ay2)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    if label:
        c.setFillColor(C['text_light'])
        c.setFont("Helvetica", 5.5)
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2 + label_offset
        c.drawCentredString(mid_x, mid_y, label)


def draw_bidi_arrow(c, x1, y1, x2, y2, color, label=None, label_offset=0):
    """Draw a bidirectional arrow."""
    c.setStrokeColor(color)
    c.setLineWidth(1.5)
    c.setDash()
    c.line(x1, y1, x2, y2)

    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 7
    arrow_angle = 0.4

    # Arrow at end
    c.setFillColor(color)
    for (px, py, a) in [(x2, y2, angle), (x1, y1, angle + math.pi)]:
        ax1 = px - arrow_len * math.cos(a - arrow_angle)
        ay1 = py - arrow_len * math.sin(a - arrow_angle)
        ax2 = px - arrow_len * math.cos(a + arrow_angle)
        ay2 = py - arrow_len * math.sin(a + arrow_angle)
        p = c.beginPath()
        p.moveTo(px, py)
        p.lineTo(ax1, ay1)
        p.lineTo(ax2, ay2)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    if label:
        c.setFillColor(C['text_light'])
        c.setFont("Helvetica", 5.5)
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2 + label_offset
        c.drawCentredString(mid_x, mid_y, label)


def draw_section_label(c, x, y, text, color):
    """Draw a section label with underline."""
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, text)
    c.setStrokeColor(color)
    c.setLineWidth(1)
    tw = c.stringWidth(text, "Helvetica-Bold", 9)
    c.line(x, y - 2, x + tw, y - 2)


def generate_architecture_pdf():
    output_path = "/Users/nimini/Projects/VPN Panel/docs/VPN-Panel-Architecture-v1.2.0.pdf"

    # Use landscape A3 for more space
    page_w, page_h = landscape(A3)
    c = canvas.Canvas(output_path, pagesize=landscape(A3))

    # Background
    c.setFillColor(C['bg'])
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # ══════════════════════════════════════════════════════════
    # PAGE 1: HIGH-LEVEL ARCHITECTURE
    # ══════════════════════════════════════════════════════════

    # Title
    c.setFillColor(C['title'])
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w/2, page_h - 35, "VPN Panel - System Architecture")
    c.setFont("Helvetica", 11)
    c.setFillColor(C['subtitle'])
    c.drawCentredString(page_w/2, page_h - 52, "Version 1.2.0  |  High-Level Architecture Overview  |  April 2026")

    # ── Section Labels ────────────────────────────────────────
    draw_section_label(c, 30, page_h - 85, "CLIENTS", C['client_hd'])
    draw_section_label(c, 200, page_h - 85, "FRONTEND", C['fe_hd'])
    draw_section_label(c, 420, page_h - 85, "API LAYER (FastAPI)", C['api_hd'])
    draw_section_label(c, 720, page_h - 85, "SERVICES", C['svc_hd'])
    draw_section_label(c, 990, page_h - 85, "SYSTEM / OS", C['sys_hd'])

    # ── Row 1: Client Boxes ──────────────────────────────────
    y_row1 = page_h - 180

    # Admin Browser
    draw_rounded_box(c, 30, y_row1, 130, 75,
        "Admin Browser", [
            "Login / Dashboard",
            "User Management",
            "Config / Audit Log",
        ], C['client_bg'], C['client_bd'], C['client_hd'])

    # VPN User Device
    draw_rounded_box(c, 30, y_row1 - 100, 130, 75,
        "VPN User Device", [
            "WireGuard Client",
            "iPhone / Android / PC",
            "Config via QR Code",
        ], C['client_bg'], C['client_bd'], C['client_hd'])

    # Telegram Bot User
    draw_rounded_box(c, 30, y_row1 - 200, 130, 75,
        "Telegram User", [
            "Link Account",
            "Check Usage",
            "View Packages",
        ], C['client_bg'], C['client_bd'], C['client_hd'])

    # ── Frontend Box ─────────────────────────────────────────
    draw_rounded_box(c, 200, y_row1 - 50, 170, 125,
        "React 18 + TypeScript", [
            "Vite + Tailwind CSS",
            "Zustand Auth Store",
            "Axios HTTP Client",
            "---",
            "11 Pages:",
            "  Dashboard, Users, UserDetail",
            "  Destinations, Logs, Alerts",
            "  Settings, Packages",
            "  AdminMgmt, AuditLog, Login",
        ], C['fe_bg'], C['fe_bd'], C['fe_hd'])

    # ── API Layer ────────────────────────────────────────────
    api_x = 420
    api_w = 255
    router_h = 60

    draw_rounded_box(c, api_x, y_row1 + 10, api_w, router_h,
        "Auth Router (/api/auth)", [
            "POST /login  |  POST /refresh  |  POST /change-password",
            "Rate Limiting (5 attempts -> 15min lockout)",
        ], C['api_bg'], C['api_bd'], C['api_hd'])

    draw_rounded_box(c, api_x, y_row1 - 60, api_w, router_h,
        "Users Router (/api/users)", [
            "CRUD + Toggle + Reset Bandwidth",
            "GET/PUT config  |  Sessions  |  Whitelist  |  Schedules",
        ], C['api_bg'], C['api_bd'], C['api_hd'])

    draw_rounded_box(c, api_x, y_row1 - 130, api_w, router_h,
        "Destinations Router (/api/destinations)", [
            "CRUD + Start/Stop VPN",
            "Health Check  |  Speed Test  |  Users per Dest",
        ], C['api_bg'], C['api_bd'], C['api_hd'])

    draw_rounded_box(c, api_x, y_row1 - 200, api_w, router_h,
        "Other Routers", [
            "/api/logs  |  /api/alerts  |  /api/packages",
            "/api/settings  |  /api/admins  |  /api/dashboard",
        ], C['api_bg'], C['api_bd'], C['api_hd'])

    # ── Services Layer ───────────────────────────────────────
    svc_x = 720
    svc_w = 230

    draw_rounded_box(c, svc_x, y_row1 + 10, svc_w, 55,
        "WireGuard Service", [
            "Key generation  |  Peer add/remove",
            "Config generation  |  Peer status (wg show dump)",
        ], C['svc_bg'], C['svc_bd'], C['svc_hd'])

    draw_rounded_box(c, svc_x, y_row1 - 55, svc_w, 55,
        "iptables Service", [
            "Whitelist chains  |  Time schedules  |  LOG rules",
            "Block/unblock  |  Destination fwmark routing",
        ], C['svc_bg'], C['svc_bd'], C['svc_hd'])

    draw_rounded_box(c, svc_x, y_row1 - 120, svc_w, 55,
        "Traffic Control Service", [
            "HTB qdiscs on wg0 + IFB",
            "Per-user speed limits (tc class/filter)",
        ], C['svc_bg'], C['svc_bd'], C['svc_hd'])

    draw_rounded_box(c, svc_x, y_row1 - 185, svc_w, 55,
        "Session & Bandwidth Tracker", [
            "Poll WG peers every 60s  |  Track sessions",
            "Monthly reset  |  Hourly snapshots  |  Limit check",
        ], C['svc_bg'], C['svc_bd'], C['svc_hd'])

    # ── System / OS Layer ────────────────────────────────────
    sys_x = 990
    sys_w = 180

    draw_rounded_box(c, sys_x, y_row1 + 10, sys_w, 55,
        "WireGuard (wg0)", [
            "wg  |  wg-quick  |  wg show",
            "UDP :51820  |  Kernel module",
        ], C['sys_bg'], C['sys_bd'], C['sys_hd'])

    draw_rounded_box(c, sys_x, y_row1 - 55, sys_w, 55,
        "iptables / netfilter", [
            "FORWARD chain  |  Per-user chains",
            "LOG target  |  TIME match  |  MARK",
        ], C['sys_bg'], C['sys_bd'], C['sys_hd'])

    draw_rounded_box(c, sys_x, y_row1 - 120, sys_w, 55,
        "tc / IFB (traffic control)", [
            "HTB root qdisc  |  FQ-CoDel leaf",
            "IFB ingress mirror device",
        ], C['sys_bg'], C['sys_bd'], C['sys_hd'])

    draw_rounded_box(c, sys_x, y_row1 - 185, sys_w, 55,
        "Linux Networking", [
            "ip rule / ip route  |  ip link",
            "Policy routing tables  |  fwmark",
        ], C['sys_bg'], C['sys_bd'], C['sys_hd'])

    # ── Bottom Row: Database, Scheduler, External ────────────
    y_bottom = y_row1 - 330

    # Database
    draw_rounded_box(c, 420, y_bottom, 200, 100,
        "SQLite (WAL Mode)", [
            "13 Tables:",
            "  Admin, User, Package, DestinationVPN",
            "  UserWhitelist, UserSchedule",
            "  BandwidthHistory, ConnectionLog",
            "  ActiveSession, UserSession",
            "  Alert, AdminAuditLog, Setting",
        ], C['db_bg'], C['db_bd'], C['db_hd'])

    # Scheduler
    draw_rounded_box(c, 650, y_bottom, 200, 100,
        "APScheduler (Background)", [
            "Every 5s:   flush connection logs",
            "Every 60s:  poll bandwidth, sessions",
            "Every 5m:   check alerts, expiry",
            "Every 60s:  destination health check",
            "Hourly:     bandwidth snapshots",
            "Daily 00:05: monthly bandwidth reset",
            "Daily 03:00: DB cleanup (old records)",
        ], C['sched_bg'], C['sched_bd'], C['sched_hd'])

    # External
    draw_rounded_box(c, 880, y_bottom, 170, 100,
        "External Integrations", [
            "Telegram Bot (aiogram 3.x)",
            "  Webhook mode",
            "  Account linking",
            "",
            "SMTP Email Alerts",
            "  aiosmtplib",
            "",
            "DNS Sniffer (tcpdump)",
        ], C['ext_bg'], C['ext_bd'], C['ext_hd'])

    # Security box
    draw_rounded_box(c, 30, y_bottom, 170, 100,
        "Security Layer", [
            "JWT Auth (HS256, 30min/7d)",
            "Bcrypt password hashing",
            "Fernet key encryption (AES)",
            "Input validation (validators.py)",
            "Rate limiting (login)",
            "Security headers (X-Frame, etc.)",
            "RBAC (10 granular permissions)",
        ], C['sec_bg'], C['sec_bd'], C['sec_hd'])

    # Audit & Monitoring
    draw_rounded_box(c, 220, y_bottom, 170, 100,
        "Audit & Monitoring", [
            "Admin Audit Log:",
            "  Action, IP, User-Agent, Device",
            "Connection Logger:",
            "  journalctl -k (iptables LOG)",
            "  tcpdump DNS sniffer",
            "Device Detector:",
            "  User-Agent -> device info",
        ], C['model_bg'], C['model_bd'], C['model_hd'])

    # ── Arrows ───────────────────────────────────────────────
    # Client -> Frontend
    draw_bidi_arrow(c, 160, y_row1 - 10, 200, y_row1 - 10, C['arrow_blue'], "HTTPS", 5)

    # VPN User -> System (WireGuard)
    draw_arrow(c, 160, y_row1 - 155, 990, y_row1 + 30, C['arrow_green'], label="WireGuard UDP :51820", label_offset=8)

    # Telegram -> API
    draw_arrow(c, 160, y_row1 - 165, 420, y_row1 - 195, C['arrow_orange'], label="Webhook", label_offset=5)

    # Frontend -> API
    draw_bidi_arrow(c, 370, y_row1 + 20, 420, y_row1 + 20, C['arrow_blue'], "REST API", 6)
    draw_bidi_arrow(c, 370, y_row1 - 40, 420, y_row1 - 40, C['arrow_blue'])
    draw_bidi_arrow(c, 370, y_row1 - 105, 420, y_row1 - 105, C['arrow_blue'])
    draw_bidi_arrow(c, 370, y_row1 - 175, 420, y_row1 - 175, C['arrow_blue'])

    # API -> Services
    draw_arrow(c, 675, y_row1 + 30, 720, y_row1 + 30, C['arrow_green'])
    draw_arrow(c, 675, y_row1 - 35, 720, y_row1 - 35, C['arrow_green'])
    draw_arrow(c, 675, y_row1 - 100, 720, y_row1 - 100, C['arrow_green'])
    draw_arrow(c, 675, y_row1 - 165, 720, y_row1 - 165, C['arrow_green'])

    # Services -> System
    draw_arrow(c, 950, y_row1 + 30, 990, y_row1 + 30, C['arrow_red'], label="subprocess")
    draw_arrow(c, 950, y_row1 - 35, 990, y_row1 - 35, C['arrow_red'])
    draw_arrow(c, 950, y_row1 - 100, 990, y_row1 - 100, C['arrow_red'])
    draw_arrow(c, 950, y_row1 - 165, 990, y_row1 - 165, C['arrow_red'])

    # API -> Database
    draw_bidi_arrow(c, 520, y_row1 - 210, 520, y_bottom + 100, C['arrow_purple'], "SQLAlchemy ORM", -8)

    # Scheduler -> Services
    draw_arrow(c, 750, y_bottom + 100, 750, y_row1 - 195, C['sched_hd'], dashed=True, label="Scheduled Tasks", label_offset=-8)

    # Scheduler -> Database
    draw_bidi_arrow(c, 650, y_bottom + 50, 620, y_bottom + 50, C['arrow_purple'])

    # External -> API
    draw_arrow(c, 940, y_bottom + 100, 600, y_row1 - 210, C['arrow_orange'], dashed=True, label="Alerts", label_offset=5)

    # Security -> API (conceptual)
    draw_arrow(c, 200, y_bottom + 80, 420, y_row1 - 200, C['arrow_red'], dashed=True, label="Middleware", label_offset=8)

    # Audit -> Database
    draw_bidi_arrow(c, 390, y_bottom + 50, 420, y_bottom + 50, C['arrow_purple'])

    # ── Legend ───────────────────────────────────────────────
    legend_x = 30
    legend_y = y_bottom - 40

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C['text_dark'])
    c.drawString(legend_x, legend_y, "LEGEND:")

    items = [
        (C['arrow_blue'], "HTTP/REST"),
        (C['arrow_green'], "Service Call / WireGuard"),
        (C['arrow_red'], "Subprocess / System"),
        (C['arrow_purple'], "Database"),
        (C['arrow_orange'], "External / Webhook"),
    ]
    lx = legend_x + 55
    for color, label in items:
        c.setStrokeColor(color)
        c.setLineWidth(2)
        c.line(lx, legend_y + 3, lx + 25, legend_y + 3)
        c.setFillColor(C['text_dark'])
        c.setFont("Helvetica", 7)
        c.drawString(lx + 30, legend_y, label)
        lx += 115

    c.setFont("Helvetica", 7)
    c.setFillColor(C['text_light'])
    c.drawString(lx + 30, legend_y, "(Dashed = background / periodic)")

    # ══════════════════════════════════════════════════════════
    # PAGE 2: DATA MODELS & RELATIONSHIPS
    # ══════════════════════════════════════════════════════════
    c.showPage()
    c.setFillColor(C['bg'])
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setFillColor(C['title'])
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w/2, page_h - 35, "VPN Panel - Data Model & Entity Relationships")
    c.setFont("Helvetica", 11)
    c.setFillColor(C['subtitle'])
    c.drawCentredString(page_w/2, page_h - 52, "Version 1.2.0  |  SQLite Database Schema (13 Tables)  |  April 2026")

    # ── Central: User Model ──────────────────────────────────
    ux, uy = 420, page_h - 280
    draw_rounded_box(c, ux, uy, 250, 195,
        "User (Central Entity)", [
            "id (PK)  |  username  |  note  |  enabled",
            "wg_private_key (encrypted)  |  wg_public_key",
            "wg_preshared_key (encrypted)  |  assigned_ip",
            "bandwidth_limit_up/down  |  bandwidth_used_up/down",
            "speed_limit_up/down (kbps)  |  bandwidth_reset_day",
            "max_connections  |  expiry_date",
            "destination_vpn_id (FK -> DestinationVPN)",
            "alert_enabled  |  alert_threshold",
            "telegram_chat_id  |  telegram_username",
            "config_dns  |  config_allowed_ips",
            "config_endpoint  |  config_mtu  |  config_keepalive",
            "created_at  |  updated_at",
            "",
            "Relations: whitelist[], schedules[],",
            "   sessions[], destination_vpn",
        ], C['svc_bg'], C['svc_bd'], C['svc_hd'], header_h=20, font_size=8, item_font_size=6.5)

    # ── Left Column ──────────────────────────────────────────
    # Admin
    draw_rounded_box(c, 30, page_h - 160, 180, 85,
        "Admin", [
            "id (PK)  |  username  |  password_hash",
            "totp_secret  |  role (super_admin/admin)",
            "permissions (JSON array)",
            "created_at",
            "",
            "Roles: super_admin (all) / admin (limited)",
        ], C['sec_bg'], C['sec_bd'], C['sec_hd'], item_font_size=6.5)

    # AdminAuditLog
    draw_rounded_box(c, 30, page_h - 290, 180, 110,
        "AdminAuditLog", [
            "id (PK)  |  admin_id (FK -> Admin)",
            "admin_username  |  action",
            "resource_type  |  resource_id",
            "details (Text/JSON)",
            "ip_address  |  user_agent (Text)",
            "device_info (parsed UA)",
            "created_at",
            "",
            "Actions: login, create_user, delete_user,",
            "   toggle_user, change_password, update_config",
        ], C['model_bg'], C['model_bd'], C['model_hd'], item_font_size=6.5)

    # DestinationVPN
    draw_rounded_box(c, 30, page_h - 430, 180, 120,
        "DestinationVPN", [
            "id (PK)  |  name  |  protocol (wg/ovpn)",
            "interface_name  |  config_text",
            "config_file_path  |  enabled  |  is_running",
            "routing_table (ip rule table #)",
            "fwmark (iptables mark)",
            "created_at  |  updated_at",
            "",
            "Relations: users[]",
            "",
            "Routing: fwmark -> policy routing table",
            "  ip rule add fwmark X table Y",
        ], C['api_bg'], C['api_bd'], C['api_hd'], item_font_size=6.5)

    # Setting
    draw_rounded_box(c, 30, page_h - 540, 180, 90,
        "Setting", [
            "id (PK)  |  key (unique)  |  value",
            "",
            "Keys:",
            "  global_alerts_enabled",
            "  bandwidth_poll_interval",
            "  connection_logging_enabled",
            "  panel_language",
        ], C['db_bg'], C['db_bd'], C['db_hd'], item_font_size=6.5)

    # ── Right Column ─────────────────────────────────────────
    rx = page_w - 280

    # UserWhitelist
    draw_rounded_box(c, rx, page_h - 150, 240, 75,
        "UserWhitelist", [
            "id (PK)  |  user_id (FK -> User)",
            "address (IP/CIDR/domain)  |  port",
            "protocol (tcp/udp/any)  |  description",
            "Unique: (user_id, address, port, protocol)",
        ], C['fe_bg'], C['fe_bd'], C['fe_hd'], item_font_size=6.5)

    # UserSchedule
    draw_rounded_box(c, rx, page_h - 240, 240, 75,
        "UserSchedule", [
            "id (PK)  |  user_id (FK -> User)",
            "day_of_week (0=Mon..6=Sun)",
            "start_time  |  end_time  |  enabled",
            "-> iptables TIME match module",
        ], C['fe_bg'], C['fe_bd'], C['fe_hd'], item_font_size=6.5)

    # UserSession
    draw_rounded_box(c, rx, page_h - 340, 240, 85,
        "UserSession (Historical)", [
            "id (PK)  |  user_id (FK -> User)",
            "endpoint (IP:port)  |  client_ip",
            "connected_at  |  disconnected_at",
            "bytes_sent  |  bytes_received",
            "duration_seconds (computed)",
            "Index: (user_id, connected_at)",
        ], C['client_bg'], C['client_bd'], C['client_hd'], item_font_size=6.5)

    # ActiveSession
    draw_rounded_box(c, rx, page_h - 430, 240, 75,
        "ActiveSession (Live)", [
            "id (PK)  |  user_id (FK -> User)",
            "endpoint (IP:port)  |  last_handshake",
            "bytes_sent  |  bytes_received",
            "Updated every 60s from wg show dump",
        ], C['client_bg'], C['client_bd'], C['client_hd'], item_font_size=6.5)

    # ── Middle Bottom ────────────────────────────────────────
    # ConnectionLog
    draw_rounded_box(c, 300, page_h - 460, 210, 95,
        "ConnectionLog", [
            "id (PK)  |  user_id (FK -> User)",
            "source_ip  |  dest_ip  |  dest_hostname",
            "dest_port  |  protocol (TCP/UDP/ICMP)",
            "bytes_sent  |  bytes_received",
            "started_at  |  ended_at",
            "Index: (user_id, started_at)",
            "Hostname: from DNS sniffer (tcpdump)",
        ], C['model_bg'], C['model_bd'], C['model_hd'], item_font_size=6.5)

    # BandwidthHistory
    draw_rounded_box(c, 540, page_h - 460, 210, 95,
        "BandwidthHistory", [
            "id (PK)  |  user_id (FK -> User)",
            "timestamp  |  bytes_up  |  bytes_down",
            "Index: (user_id, timestamp)",
            "",
            "Recorded hourly at :00",
            "Retention: 90 days",
        ], C['sched_bg'], C['sched_bd'], C['sched_hd'], item_font_size=6.5)

    # Alert
    draw_rounded_box(c, 300, page_h - 570, 210, 95,
        "Alert", [
            "id (PK)  |  user_id (FK -> User, nullable)",
            "type: bandwidth_warning, expired,",
            "   expiry_warning, dest_vpn_down",
            "message  |  channel (panel/email/telegram)",
            "sent_at  |  acknowledged (bool)",
            "Sent via: panel, email (SMTP), Telegram",
        ], C['ext_bg'], C['ext_bd'], C['ext_hd'], item_font_size=6.5)

    # Package
    draw_rounded_box(c, 540, page_h - 570, 210, 95,
        "Package", [
            "id (PK)  |  name  |  description",
            "bandwidth_limit  |  speed_limit",
            "duration_days  |  max_connections",
            "price  |  currency  |  enabled",
            "",
            "Displayed in Telegram bot",
        ], C['api_bg'], C['api_bd'], C['api_hd'], item_font_size=6.5)

    # ── Relationship Arrows ──────────────────────────────────
    # Admin -> AuditLog (1:N)
    draw_arrow(c, 120, page_h - 160, 120, page_h - 180, C['arrow_red'], label="1:N")

    # User -> Whitelist
    draw_arrow(c, 670, uy + 170, rx, page_h - 115, C['arrow_blue'], label="1:N", label_offset=5)
    # User -> Schedule
    draw_arrow(c, 670, uy + 130, rx, page_h - 200, C['arrow_blue'], label="1:N", label_offset=5)
    # User -> UserSession
    draw_arrow(c, 670, uy + 90, rx, page_h - 295, C['arrow_blue'], label="1:N", label_offset=5)
    # User -> ActiveSession
    draw_arrow(c, 670, uy + 50, rx, page_h - 395, C['arrow_blue'], label="1:N", label_offset=5)

    # User -> ConnectionLog
    draw_arrow(c, ux + 50, uy, 400, page_h - 365, C['arrow_green'], label="1:N", label_offset=-8)
    # User -> BandwidthHistory
    draw_arrow(c, ux + 180, uy, 640, page_h - 365, C['arrow_purple'], label="1:N", label_offset=-8)
    # User -> Alert
    draw_arrow(c, ux + 50, uy - 5, 400, page_h - 465, C['arrow_orange'], label="1:N", label_offset=-8)

    # DestinationVPN -> User (1:N)
    draw_arrow(c, 210, page_h - 370, ux, uy + 60, C['arrow_orange'], label="1:N (destination_vpn_id)", label_offset=8)

    # ── Retention Info Box ───────────────────────────────────
    draw_rounded_box(c, rx, page_h - 570, 240, 120,
        "Data Retention & Cleanup", [
            "Automated daily at 03:00 AM:",
            "",
            "  Connection Logs:     30 days",
            "  Bandwidth History:   90 days",
            "  User Sessions:       90 days",
            "  Admin Audit Logs:   180 days",
            "",
            "SQLite WAL mode for concurrent R/W",
        ], C['db_bg'], C['db_bd'], C['db_hd'], item_font_size=6.5)

    # ══════════════════════════════════════════════════════════
    # PAGE 3: DATA FLOW DIAGRAMS
    # ══════════════════════════════════════════════════════════
    c.showPage()
    c.setFillColor(C['bg'])
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    c.setFillColor(C['title'])
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w/2, page_h - 35, "VPN Panel - Data Flow & Process Diagrams")
    c.setFont("Helvetica", 11)
    c.setFillColor(C['subtitle'])
    c.drawCentredString(page_w/2, page_h - 52, "Version 1.2.0  |  Key Process Flows  |  April 2026")

    # ── Flow 1: User Creation ────────────────────────────────
    flow1_y = page_h - 90
    draw_section_label(c, 30, flow1_y, "FLOW 1: User Creation", C['svc_hd'])

    steps1 = [
        ("Admin", "POST /api/users\n{username, limits}", C['client_bg'], C['client_bd'], C['client_hd']),
        ("API Router", "Validate input\nCheck RBAC perms", C['api_bg'], C['api_bd'], C['api_hd']),
        ("WG Service", "generate_keypair()\nget_next_ip()\nencrypt_private_key()", C['svc_bg'], C['svc_bd'], C['svc_hd']),
        ("Database", "INSERT User\nw/ keys, IP, limits", C['db_bg'], C['db_bd'], C['db_hd']),
        ("WG Service", "add_peer(pubkey, ip)\nwg set wg0 peer ...", C['svc_bg'], C['svc_bd'], C['svc_hd']),
        ("iptables", "setup logging\nsetup routing\n(if dest VPN set)", C['sys_bg'], C['sys_bd'], C['sys_hd']),
        ("Audit Log", "log_action(\n  create_user,\n  IP, User-Agent)", C['model_bg'], C['model_bd'], C['model_hd']),
    ]

    sx = 30
    sw = 145
    sh = 68
    sy = flow1_y - 85
    for idx, (title, desc, bg, bd, hd) in enumerate(steps1):
        x = sx + idx * (sw + 20)
        # Step number
        c.setFillColor(hd)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x + sw/2, sy + sh + 8, str(idx + 1))

        draw_rounded_box(c, x, sy, sw, sh, title,
            desc.split('\n'), bg, bd, hd, header_h=16, font_size=7, item_font_size=6.5)

        if idx < len(steps1) - 1:
            draw_arrow(c, x + sw, sy + sh/2, x + sw + 20, sy + sh/2, C['arrow_green'])

    # ── Flow 2: VPN Connection & Monitoring ──────────────────
    flow2_y = flow1_y - 175
    draw_section_label(c, 30, flow2_y, "FLOW 2: VPN Connection & Bandwidth Monitoring", C['api_hd'])

    steps2 = [
        ("VPN Client", "WireGuard handshake\nUDP :51820\nw/ public key + PSK", C['client_bg'], C['client_bd'], C['client_hd']),
        ("wg0 Interface", "Peer authenticated\nEndpoint recorded\nTraffic flows", C['sys_bg'], C['sys_bd'], C['sys_hd']),
        ("iptables", "FORWARD chain:\nLOG (conn logging)\nWhitelist check\nSchedule check", C['sys_bg'], C['sys_bd'], C['sys_hd']),
        ("tc (QoS)", "HTB rate limiting\nEgress: wg0 class\nIngress: IFB class", C['sys_bg'], C['sys_bd'], C['sys_hd']),
        ("Dest VPN", "Policy routing:\nfwmark -> table\nip route via dest", C['ext_bg'], C['ext_bd'], C['ext_hd']),
        ("Tracker (60s)", "wg show dump\nDelta calc\nUpdate user BW\nTrack sessions", C['sched_bg'], C['sched_bd'], C['sched_hd']),
        ("Alert Check", "Threshold check\nExpiry check\nPanel/Email/TG", C['sec_bg'], C['sec_bd'], C['sec_hd']),
    ]

    sy2 = flow2_y - 85
    for idx, (title, desc, bg, bd, hd) in enumerate(steps2):
        x = sx + idx * (sw + 20)
        c.setFillColor(hd)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x + sw/2, sy2 + sh + 8, str(idx + 1))

        draw_rounded_box(c, x, sy2, sw, sh, title,
            desc.split('\n'), bg, bd, hd, header_h=16, font_size=7, item_font_size=6.5)

        if idx < len(steps2) - 1:
            draw_arrow(c, x + sw, sy2 + sh/2, x + sw + 20, sy2 + sh/2, C['arrow_orange'])

    # ── Flow 3: Connection Logging ───────────────────────────
    flow3_y = flow2_y - 175
    draw_section_label(c, 30, flow3_y, "FLOW 3: Connection Logging & DNS Resolution", C['sched_hd'])

    steps3 = [
        ("iptables LOG", "FORWARD chain\nLOG prefix:\n  'user:ID:'", C['sys_bg'], C['sys_bd'], C['sys_hd']),
        ("journalctl -k", "Background thread\nReads kernel log\nReal-time stream", C['svc_bg'], C['svc_bd'], C['svc_hd']),
        ("Log Parser", "Extract:\n  user_id, src, dst\n  proto, port", C['svc_bg'], C['svc_bd'], C['svc_hd']),
        ("DNS Sniffer", "tcpdump -i wg0\nudp src port 53\nCapture responses", C['ext_bg'], C['ext_bd'], C['ext_hd']),
        ("Hostname Map", "IP -> hostname\nThread-safe deque\nPassive DNS cache", C['sched_bg'], C['sched_bd'], C['sched_hd']),
        ("Buffer (5s)", "Batch insert\nConnectionLog table\nw/ hostname if known", C['db_bg'], C['db_bd'], C['db_hd']),
    ]

    sy3 = flow3_y - 85
    sw3 = 170
    for idx, (title, desc, bg, bd, hd) in enumerate(steps3):
        x = sx + idx * (sw3 + 20)
        c.setFillColor(hd)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x + sw3/2, sy3 + sh + 8, str(idx + 1))

        draw_rounded_box(c, x, sy3, sw3, sh, title,
            desc.split('\n'), bg, bd, hd, header_h=16, font_size=7, item_font_size=6.5)

        if idx < len(steps3) - 1:
            draw_arrow(c, x + sw3, sy3 + sh/2, x + sw3 + 20, sy3 + sh/2, C['arrow_purple'])

    # Merge arrow from DNS Sniffer to Hostname Map
    # Already connected linearly; add a label
    c.setFillColor(C['text_light'])
    c.setFont("Helvetica", 5.5)

    # ── Flow 4: RBAC & Security ──────────────────────────────
    flow4_y = flow3_y - 175
    draw_section_label(c, 30, flow4_y, "FLOW 4: Authentication & RBAC Enforcement", C['sec_hd'])

    steps4 = [
        ("Admin Login", "POST /api/auth/login\nUsername + Password\nRate limit check", C['client_bg'], C['client_bd'], C['client_hd']),
        ("Rate Limiter", "Check IP attempts\n5 fails -> 15min lock\nIn-memory tracking", C['sec_bg'], C['sec_bd'], C['sec_hd']),
        ("Auth Check", "Verify bcrypt hash\nGenerate JWT tokens\nAccess: 30min\nRefresh: 7 days", C['api_bg'], C['api_bd'], C['api_hd']),
        ("Device Detect", "Parse User-Agent\nExtract: device,\n  OS, browser\nStore in audit log", C['model_bg'], C['model_bd'], C['model_hd']),
        ("API Request", "Bearer token in header\nJWT decode + verify\nExtract admin_id", C['api_bg'], C['api_bd'], C['api_hd']),
        ("RBAC Check", "require_permission()\nCheck admin.role\nVerify permission\nin JSON array", C['sec_bg'], C['sec_bd'], C['sec_hd']),
    ]

    sy4 = flow4_y - 85
    sw4 = 170
    for idx, (title, desc, bg, bd, hd) in enumerate(steps4):
        x = sx + idx * (sw4 + 20)
        c.setFillColor(hd)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x + sw4/2, sy4 + sh + 8, str(idx + 1))

        draw_rounded_box(c, x, sy4, sw4, sh, title,
            desc.split('\n'), bg, bd, hd, header_h=16, font_size=7, item_font_size=6.5)

        if idx < len(steps4) - 1:
            draw_arrow(c, x + sw4, sy4 + sh/2, x + sw4 + 20, sy4 + sh/2, C['arrow_red'])

    # ── RBAC Permissions Table ───────────────────────────────
    perm_y = sy4 - 30
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C['text_dark'])
    c.drawString(30, perm_y, "RBAC Permissions (10 Total):")

    perms = [
        "users.view", "users.create", "users.edit", "users.delete", "users.delete",
        "destinations.view", "destinations.manage", "logs.view",
        "packages.manage", "settings.manage", "alerts.view"
    ]
    c.setFont("Courier", 7)
    c.setFillColor(C['text_light'])
    perm_text = "  |  ".join(perms[:5])
    c.drawString(30, perm_y - 12, perm_text)
    perm_text2 = "  |  ".join(perms[5:])
    c.drawString(30, perm_y - 23, perm_text2)

    # ── Footer ───────────────────────────────────────────────
    c.setFont("Helvetica", 7)
    c.setFillColor(C['text_light'])
    c.drawCentredString(page_w/2, 15, "VPN Panel Architecture v1.2.0 - Generated April 2026")

    # Add page numbers to all pages
    c.save()

    print(f"Architecture PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    path = generate_architecture_pdf()
    print(f"\nDone! Architecture PDF saved to:\n  {path}")
