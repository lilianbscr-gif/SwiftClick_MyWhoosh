"""
Génère assets/icon.ico — icône futuriste SwiftClick MyWhoosh.
Design : fond bleu-noir, hexagone cyan, éclair BLE + lettres SC.
Usage   : python assets/generate_icon.py
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "icon.ico"

# ── Palette (cohérente avec l'app) ──────────────────────────
BG    = (2,   8,  16)       # #020810
CYAN  = (0, 212, 255)       # #00d4ff
CYAND = (0,  95, 119)       # #005f77
WHITE = (224, 244, 255)     # #e0f4ff

SIZES = [256, 128, 64, 48, 32, 16]


def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size * 0.44          # rayon hexagone

    # ── Fond hexagonal ───────────────────────────────────────
    hex_pts = [
        (cx + r * math.cos(math.radians(a)),
         cy + r * math.sin(math.radians(a)))
        for a in range(30, 391, 60)   # pointy-top
    ]
    # Glow (légèrement plus grand, très transparent)
    glow = [(cx + (r + size*0.04) * math.cos(math.radians(a)),
             cy + (r + size*0.04) * math.sin(math.radians(a)))
            for a in range(30, 391, 60)]
    draw.polygon(glow, fill=(0, 212, 255, 30))

    # Remplissage principal
    draw.polygon(hex_pts, fill=(*BG, 255))

    # Bordure cyan (double trait pour effet néon)
    lw = max(1, size // 40)
    draw.polygon(hex_pts, outline=(*CYAND, 180), width=lw + 2)
    draw.polygon(hex_pts, outline=(*CYAN,  255), width=lw)

    # ── Symbole central : éclair stylisé ─────────────────────
    # Éclair proportionnel à la taille
    bolt_w = size * 0.22
    bolt_h = size * 0.52
    bx, by = cx, cy - size * 0.04   # légèrement décalé vers le haut

    bolt = [
        (bx + bolt_w * 0.15,  by - bolt_h * 0.50),   # haut-gauche
        (bx + bolt_w * 0.65,  by - bolt_h * 0.50),   # haut-droit
        (bx + bolt_w * 0.02,  by + bolt_h * 0.08),   # milieu-gauche
        (bx + bolt_w * 0.45,  by + bolt_h * 0.08),   # milieu-droit
        (bx - bolt_w * 0.15,  by + bolt_h * 0.50),   # bas-gauche
        (bx + bolt_w * 0.35,  by - bolt_h * 0.06),   # milieu bas
        (bx - bolt_w * 0.02,  by - bolt_h * 0.06),   # milieu haut
    ]
    draw.polygon(bolt, fill=(*CYAN, 255))

    # Petit reflet blanc sur l'éclair
    if size >= 48:
        highlight = [
            (bx + bolt_w * 0.17,  by - bolt_h * 0.48),
            (bx + bolt_w * 0.52,  by - bolt_h * 0.48),
            (bx + bolt_w * 0.06,  by - bolt_h * 0.02),
            (bx + bolt_w * 0.22,  by - bolt_h * 0.02),
        ]
        draw.polygon(highlight, fill=(*WHITE, 80))

    return img


def main():
    imgs = [draw_icon(s) for s in SIZES]
    imgs[0].save(
        OUT, format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=imgs[1:],
    )
    print(f"Icone generee : {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
