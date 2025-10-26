#!/usr/bin/env python3
import cv2
import numpy as np
import os, sys, time, tty, termios, shutil

# ======================================
# ⚙️ CONFIGURATION DE BASE
# ======================================
VIDEO_PATH = input("Chemin de la vidéo : ")
CHAR_RATIO = 2  # Braille = 2 colonnes x 4 lignes
FPS_DEFAULT = 24
EXPORT_DIR = "ascii_export"
EXPORT_C_FILE = "main.c"

# ======================================
# 🧩 UTILITAIRES TERMINAL
# ======================================
def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch

def clear(): os.system("clear")

def get_terminal_size():
    cols, rows = shutil.get_terminal_size()
    return cols, rows - 3

# ======================================
# 🎨 CONVERSION BRAILLE
# ======================================
def frame_to_braille(frame, max_cols, max_rows, contrast=1.0, brightness=0.0, export=False):
    """Convertit une frame en ASCII Braille coloré."""
    # Ajustement contraste/luminosité
    frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness*255)
    h, w, _ = frame.shape

    # Calcul du scaling
    max_w = max_cols * CHAR_RATIO
    max_h = max_rows * 4
    scale = min(max_w / w, max_h / h)
    new_w = (int(w * scale) // 2) * 2
    new_h = (int(h * scale) // 4) * 4
    frame = cv2.resize(frame, (new_w, new_h))

    out = ""
    for y in range(0, new_h, 4):
        for x in range(0, new_w, 2):
            dots = 0
            color = frame[y:y+4, x:x+2].mean(axis=(0,1))
            for dy in range(4):
                for dx in range(2):
                    b, g, r = frame[y+dy, x+dx]
                    lum = 0.299*r + 0.587*g + 0.114*b
                    if lum > 128:
                        dots |= 1 << (dy + dx*4)
            char = chr(0x2800 + dots)
            r, g, b = int(color[2]), int(color[1]), int(color[0])
            if export:
                # échappement pour printf
                out += f"\\033[38;2;{r};{g};{b}m{char}\\033[0m"
            else:
                out += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        out += "\\n" if export else "\n"
    return out

# ======================================
# 🎞️ VIDÉO
# ======================================
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print("❌ Erreur : impossible d’ouvrir la vidéo.")
    sys.exit(1)

ret, frame = cap.read()
if not ret:
    print("❌ Erreur : impossible de lire la vidéo.")
    sys.exit(1)

# ======================================
# 🔧 PARAMÈTRES INTERACTIFS
# ======================================
contrast = 1.0
brightness = 0.0
fps = FPS_DEFAULT

HELP = """
COMMANDES :
e/d : contraste +/- 
r/f : luminosité +/- 
t/g : FPS +/- 
Enter : lancer la vidéo
s : lancer export ASCII
q ou Ctrl+C : quitter
"""

# ======================================
# 🔍 PRÉVISUALISATION INTERACTIVE
# ======================================
print(HELP)
while True:
    cols, rows = get_terminal_size()
    clear()
    print(frame_to_braille(frame, cols, rows, contrast, brightness, export=False))
    print(f"Contraste: {contrast:.1f} | Luminosité: {brightness:.2f} | FPS: {fps} | Terminal: {cols}x{rows}")
    print(HELP)

    k = getch()
    if k == "\r":
        mode = "play"
        break
    elif k == "s":
        mode = "export"
        break
    elif k in ("q", "\x03"):
        sys.exit(0)
    elif k == "e":
        contrast = min(3.0, contrast + 0.1)
    elif k == "d":
        contrast = max(0.1, contrast - 0.1)
    elif k == "r":
        brightness = min(1.0, brightness + 0.05)
    elif k == "f":
        brightness = max(-1.0, brightness - 0.05)
    elif k == "t":
        fps += 1
    elif k == "g":
        fps = max(1, fps - 1)

frame_time = 1.0 / fps
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

# ======================================
# ▶️ MODE LECTURE
# ======================================
if mode == "play":
    while True:
        ret, frame = cap.read()
        if not ret:  # fin de la vidéo
            break
        cols, rows = get_terminal_size()
        clear()
        print(frame_to_braille(frame, cols, rows, contrast, brightness, export=False))
        time.sleep(frame_time)
    print("▶️ Lecture terminée.")


# ======================================
# 💾 MODE EXPORT C
# ======================================
if mode == "export":
    os.makedirs(EXPORT_DIR, exist_ok=True)
    print(f"📦 Export des frames vers {EXPORT_DIR}/ ...")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    exported_frames = []

    for i in range(total):
        ret, frame = cap.read()
        if not ret: break
        cols, rows = get_terminal_size()
        ascii_frame = frame_to_braille(frame, cols, rows, contrast, brightness, export=True)
        exported_frames.append(ascii_frame)
        sys.stdout.write(f"\r🧩 {i+1}/{total} frames exportées")
        sys.stdout.flush()

    print("\n✅ Export terminé. Génération du fichier C ...")
    
    with open(EXPORT_C_FILE, "w") as f:
        f.write('#include <stdio.h>\n#include <unistd.h>\n\n')
        f.write('int main() {\n')
        f.write(f'    const int frame_time_us = {int(frame_time*1e6)};\n')
        f.write(f'    const char* frames[{len(exported_frames)}] = {{\n')
        for fr in exported_frames:
            f.write(f'        "{fr}",\n')
        f.write('    };\n')
        f.write('    int total = sizeof(frames)/sizeof(frames[0]);\n')
        f.write('    while(1) {\n')
        f.write('        for(int i=0;i<total;i++) {\n')
        f.write('            printf("\\033[H\\033[2J");\n')
        f.write('            printf("%s\\n", frames[i]);\n')
        f.write('            usleep(frame_time_us);\n')
        f.write('        }\n')
        f.write('    }\n    return 0;\n}\n')

    print(f"🧩 Fichier C généré : {EXPORT_C_FILE}")
    print("💡 Compile avec : gcc main.c -o anim && ./anim")

