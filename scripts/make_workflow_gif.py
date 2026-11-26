#!/usr/bin/env python3
"""Usage: python3 -I scripts/make_workflow_gif.py  (needs Pillow, ffmpeg, Roboto + JetBrains Mono fonts)

Generate an animated workflow GIF for 9070FpgaIAWorkflow: RustingStrata (Qwen3.6-35B-A3B) + Hermes + Codewhale + Claude,
plus a benchmark scene against the previous Strata + Inkling-2-Mini SQ-15 minion."""
import math
import os
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

OUT_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "assets", "strata-hybrid-workflow.gif")
PREVIEW_DIR = os.environ.get("GIF_PREVIEW_DIR")  # optional: one PNG per scene for checking
W, H = 1200, 680
S = 2  # 2x supersampling for crisp anti-aliased rendering

FONT_BOLD = "/usr/share/fonts/TTF/Roboto-Bold.ttf"
FONT_REG = "/usr/share/fonts/TTF/Roboto-Medium.ttf"
FONT_LIGHT = "/usr/share/fonts/TTF/Roboto-Regular.ttf"
FONT_MONO = "/home/danimanx/.local/share/fonts/fonts/JetBrains-Mono-Nerd-Font-Complete.ttf"
if not os.path.exists(FONT_REG):
    FONT_REG = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"
if not os.path.exists(FONT_LIGHT):
    FONT_LIGHT = "/usr/share/fonts/liberation/LiberationSans-Regular.ttf"

def fnt(path, size):
    return ImageFont.truetype(path, size * S)

BG = "#0d1117"
CARD_BG = "#161b22"
CARD_BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"

ACCENT_CLAUDE = "#d2a8ff"
ACCENT_HERMES = "#79c0ff"
ACCENT_STRATA = "#3fb950"
ACCENT_CW = "#f0883e"
ACCENT_TOOLS = "#58a6ff"
ACCENT_WARN = "#f85149"


def rrect(draw, box, r, fill, outline=None, width=2):
    x0, y0, x1, y1 = [v * S for v in box]
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r * S, fill=fill, outline=outline, width=width * S)


def text(draw, pos, txt, font, fill=TEXT, anchor="la"):
    draw.text((pos[0] * S, pos[1] * S), txt, font=font, fill=fill, anchor=anchor)


def arrow(draw, p1, p2, color, width=3, dashed=False, pulse_t=None):
    x1, y1 = p1[0] * S, p1[1] * S
    x2, y2 = p2[0] * S, p2[1] * S
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    ux, uy = dx / dist, dy / dist
    if dashed:
        seg = 10 * S
        gap = 8 * S
        cur = 0
        while cur < dist - 10 * S:
            nxt = min(cur + seg, dist - 10 * S)
            draw.line([x1 + ux * cur, y1 + uy * cur, x1 + ux * nxt, y1 + uy * nxt], fill=color, width=width * S)
            cur += seg + gap
    else:
        draw.line([x1, y1, x2 - ux * 8 * S, y2 - uy * 8 * S], fill=color, width=width * S)

    # Arrowhead
    ah = 11 * S
    aw = 6 * S
    px, py = -uy, ux
    tip = (x2, y2)
    left = (x2 - ux * ah + px * aw, y2 - uy * ah + py * aw)
    right = (x2 - ux * ah - px * aw, y2 - uy * ah - py * aw)
    draw.polygon([tip, left, right], fill=color)

    # Animated pulse dot
    if pulse_t is not None:
        t = pulse_t % 1.0
        bx = x1 + dx * t
        by = y1 + dy * t
        r = 6 * S
        draw.ellipse([bx - r * 1.6, by - r * 1.6, bx + r * 1.6, by + r * 1.6], fill=color + "55")
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill="#ffffff")


def draw_card(draw, box, title, subtitle, lines, accent, active=False, badge=None):
    border = accent if active else CARD_BORDER
    bw = 3 if active else 2
    rrect(draw, box, 12, CARD_BG, outline=border, width=bw)
    x0, y0, x1, y1 = box
    # Top accent bar
    rrect(draw, (x0 + 1, y0 + 1, x1 - 1, y0 + 8), 4, accent if active else CARD_BORDER)
    text(draw, (x0 + 16, y0 + 20), title, fnt(FONT_BOLD, 17), fill=TEXT)
    if badge:
        bx1 = x1 - 14
        bx0 = bx1 - len(badge) * 8 - 18
        rrect(draw, (bx0, y0 + 18, bx1, y0 + 40), 6, accent)
        text(draw, ((bx0 + bx1) / 2, y0 + 29), badge, fnt(FONT_BOLD, 11), fill=BG, anchor="mm")
    text(draw, (x0 + 16, y0 + 44), subtitle, fnt(FONT_MONO, 12), fill=accent)
    cy = y0 + 68
    for ln in lines:
        text(draw, (x0 + 16, cy), ln, fnt(FONT_LIGHT, 13), fill=MUTED if not active else TEXT)
        cy += 20


SCENES = [
    {
        "step": "STEP 1 / 5 — ARCHITECT & ROUTING",
        "caption": "Claude Code evaluates task scope: bounded/structural tasks go local (0 cloud tokens); timing & multi-file >128K escalate.",
        "active": {"claude"},
        "pulses": [("dev_claude", ACCENT_CLAUDE)],
    },
    {
        "step": "STEP 2 / 5 — LOCAL FAST PATH (RUSTINGSTRATA, VULKAN)",
        "caption": "RustingStrata serves Qwen3.6-35B-A3B (:8080/v1, 128K ctx, ~110-120 tok/s) to Claude (ask) & Hermes (oneshot).",
        "active": {"claude", "hermes", "strata"},
        "pulses": [("claude_strata", ACCENT_STRATA), ("hermes_strata", ACCENT_HERMES), ("dev_hermes", ACCENT_HERMES)],
    },
    {
        "step": "STEP 3 / 5 — REMOTE ESCALATION (DEEPSEEK-FLASH)",
        "caption": "Cycle-accurate timing, CDC, .sdc/.sta.rpt closure, and autonomous multi-file edits route to codewhale (deepseek-flash).",
        "active": {"claude", "cw"},
        "pulses": [("claude_cw", ACCENT_CW)],
    },
    {
        "step": "STEP 4 / 5 — VERIFY & BUILD GATES",
        "caption": "Every draft is verified with real tools (Verilator, terraform validate, cargo clippy). Stop the minion before Quartus.",
        "active": {"claude", "cw", "tools"},
        "pulses": [("claude_tools", ACCENT_TOOLS), ("cw_tools", ACCENT_TOOLS)],
    },
    {
        "step": "STEP 5 / 5 — WHY RUSTINGSTRATA (MEASURED 2026-11-26, SAME SCRIPT)",
        "caption": None,
        "active": {"strata"},
        "pulses": [],
    },
]

BENCH = [  # (label, before Inkling SQ-15, after RustingStrata Vulkan) in tok/s
    ("Decode, short prompt", 71, 129),
    ("Decode after ~7.5k-token prompt", 51, 122),
]
BENCH_MAX = 140.0


def draw_bench(draw, t):
    grow = min(1.0, t / 0.6)
    x_lab, x_bar, bar_w = 58, 340, 560
    y = 548
    for label, before, after in BENCH:
        text(draw, (x_lab, y + 2), label, fnt(FONT_REG, 13), fill=TEXT)
        for j, (val, col, name) in enumerate(((before, MUTED, "Inkling SQ-15 (Strata)"), (after, ACCENT_STRATA, "Qwen3.6 (RustingStrata)"))):
            yy = y + j * 17
            w = bar_w * (val / BENCH_MAX) * grow
            rrect(draw, (x_bar, yy, x_bar + max(w, 6), yy + 12), 4, col)
            text(draw, (x_bar + max(w, 6) + 8, yy - 1), f"{val * grow:.0f} tok/s  {name}", fnt(FONT_MONO, 11), fill=col)
        y += 44


def render_frame(scene_idx, t_in_scene):
    img = Image.new("RGBA", (W * S, H * S), BG)
    draw = ImageDraw.Draw(img)

    # Header
    text(draw, (36, 24), "9070FpgaIAWorkflow — Hybrid Local & Cloud AI Architecture", fnt(FONT_BOLD, 24), fill=TEXT)
    text(draw, (36, 56), "AMD RX 9070 XT (16 GB VRAM) + 64 GB DDR5  |  RustingStrata Qwen3.6-35B-A3B + Hermes + Codewhale + Claude Code", fnt(FONT_REG, 13), fill=MUTED)

    sc = SCENES[scene_idx]
    act = sc["active"]

    # Step progress pills top-right
    for i in range(len(SCENES)):
        px = 932 + i * 48
        col = ACCENT_STRATA if i == scene_idx else CARD_BORDER
        rrect(draw, (px, 28, px + 38, 42), 7, col)

    # Nodes coordinates
    dev_box = (36, 115, 216, 205)
    claude_box = (290, 100, 620, 235)
    hermes_box = (36, 275, 250, 415)
    strata_box = (310, 275, 760, 455)
    cw_box = (830, 100, 1164, 260)
    tools_box = (830, 310, 1164, 465)

    # Draw cards
    rrect(draw, dev_box, 12, CARD_BG, outline=ACCENT_CLAUDE if "claude" in act else CARD_BORDER, width=2)
    text(draw, (126, 145), "Developer", fnt(FONT_BOLD, 16), fill=TEXT, anchor="mm")
    text(draw, (126, 172), "Prompt / Objective", fnt(FONT_MONO, 11), fill=MUTED, anchor="mm")

    draw_card(
        draw, claude_box,
        "Claude Code", "Lead Architect",
        [
            "• Plans, routes & verifies all output",
            "• Owns CDC, .sdc, .sta.rpt, DSP math",
            "• Calls strata-local ask (0 cloud tok)",
        ],
        ACCENT_CLAUDE, active=("claude" in act), badge="ARCHITECT"
    )

    draw_card(
        draw, hermes_box,
        "Hermes Agent", "hermes chat --oneshot",
        [
            "• Tool-calling loop (:8080)",
            "• reasoning_effort: low",
            "• 128K ctx · 1 task at a time",
        ],
        ACCENT_HERMES, active=("hermes" in act), badge="AGENT"
    )

    draw_card(
        draw, strata_box,
        "RustingStrata 1.3.7", "Qwen3.6-35B-A3B Q4_K_XL  ·  :8080/v1",
        [
            "• ~6.5k/10.2k experts in VRAM + CPU experts · 0.2 GB RAM",
            "• ~110–120 tok/s · 128K ctx (KV q8) · prompt cache",
            "• --sum / --rtl / --iac / --rust / --review",
            "• thinking off (ask) | low (Hermes/CW), max_tok>=4096",
        ],
        ACCENT_STRATA, active=("strata" in act), badge="VULKAN"
    )

    draw_card(
        draw, cw_box,
        "codewhale", "deepseek-flash (Remote API)",
        [
            "• Cycle timing, bus protocols, CDC",
            "• Autonomous multi-file edits",
            "• >128K context & complex debug",
        ],
        ACCENT_CW, active=("cw" in act), badge="REMOTE"
    )

    draw_card(
        draw, tools_box,
        "Verification Gates", "Verilator / Quartus / Cargo / TF",
        [
            "• FPGA: verilator --lint-only, quartus_sh",
            "• IaC: terraform fmt + validate, tflint",
            "• Rust: cargo clippy -D warnings, test",
        ],
        ACCENT_TOOLS, active=("tools" in act), badge="MANDATORY"
    )

    # Arrows
    edges = {
        "dev_claude": ((216, 160), (290, 160), ACCENT_CLAUDE, False),
        "dev_hermes": ((126, 205), (126, 275), ACCENT_HERMES, False),
        "claude_strata": ((455, 235), (455, 275), ACCENT_STRATA, False),
        "hermes_strata": ((250, 345), (310, 345), ACCENT_HERMES, False),
        "claude_cw": ((620, 165), (830, 165), ACCENT_CW, False),
        "cw_strata": ((830, 235), (760, 305), MUTED, True),
        "claude_tools": ((620, 215), (830, 345), ACCENT_TOOLS, False),
        "cw_tools": ((997, 260), (997, 310), ACCENT_TOOLS, False),
    }

    pulse_map = {k: col for k, col in sc["pulses"]}
    for name, (p1, p2, col, dashed) in edges.items():
        active_col = pulse_map.get(name, col if name in pulse_map else "#3b434d")
        is_active = name in pulse_map
        arrow(draw, p1, p2, active_col, width=4 if is_active else 2, dashed=dashed, pulse_t=t_in_scene if is_active else None)

    # Edge labels
    text(draw, (640, 145), "Timing / Multi-file / >128K", fnt(FONT_MONO, 11), fill=ACCENT_CW if "cw" in act else MUTED)
    text(draw, (466, 248), "strata-local ask", fnt(FONT_MONO, 11), fill=ACCENT_STRATA if "strata" in act else MUTED)
    text(draw, (725, 250), "--profile strata", fnt(FONT_MONO, 10), fill=MUTED)

    # Bottom narrative banner
    rrect(draw, (36, 495, 1164, 645), 12, "#11161d", outline=CARD_BORDER, width=2)
    text(draw, (58, 518), sc["step"], fnt(FONT_MONO, 14), fill=ACCENT_STRATA)
    if sc["caption"]:
        text(draw, (58, 548), sc["caption"], fnt(FONT_BOLD, 16), fill=TEXT)
    else:
        draw_bench(draw, t_in_scene)

    # Footer hardware rule bar
    if not sc["caption"]:
        text(draw, (58, 636), "A/B at 32K. Now 128K ctx (KV q8): ~110-120 tok/s, 81 tok/s after a 120K-token prompt. Fallback: STRATA_ENGINE=inkling", fnt(FONT_MONO, 11), fill=MUTED, anchor="ls")
        return img.resize((W, H), Image.Resampling.LANCZOS).convert("RGB")
    text(draw, (58, 592), "SAFETY RULE:  strata-local stop before Quartus compiles  |  --parallel 1 (1 local request at a time)  |  Never trust unverified local drafts", fnt(FONT_MONO, 12), fill=ACCENT_CW)
    text(draw, (58, 616), "MEASURED 2026-11-26:  RustingStrata Vulkan 92-129 tok/s vs Inkling SQ-15 69-73 tok/s (same script); no GPU resets, clean dmesg.", fnt(FONT_MONO, 11), fill=MUTED)

    return img.resize((W, H), Image.Resampling.LANCZOS).convert("RGB")


def main():
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        idx = 0
        frames_per_scene = 20  # 2.0s per scene at 10 fps -> 8.0s total loop
        for s_idx in range(len(SCENES)):
            for f in range(frames_per_scene):
                t = f / frames_per_scene
                im = render_frame(s_idx, t)
                im.save(os.path.join(td, f"frame_{idx:04d}.png"))
                idx += 1

        palette = os.path.join(td, "palette.png")
        subprocess.run([
            "ffmpeg", "-y", "-framerate", "10", "-i", os.path.join(td, "frame_%04d.png"),
            "-vf", "palettegen=stats_mode=diff", palette
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([
            "ffmpeg", "-y", "-framerate", "10", "-i", os.path.join(td, "frame_%04d.png"),
            "-i", palette,
            "-lavfi", "paletteuse=dither=bayer:bayer_scale=3",
            "-loop", "0", OUT_GIF
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Save one preview PNG to verify visually
        if PREVIEW_DIR:
            for i in range(len(SCENES)):
                render_frame(i, 0.9).save(os.path.join(PREVIEW_DIR, f"preview_{i}.png"))
    print(f"Generated {OUT_GIF} ({os.path.getsize(OUT_GIF)} bytes)")


if __name__ == "__main__":
    main()
