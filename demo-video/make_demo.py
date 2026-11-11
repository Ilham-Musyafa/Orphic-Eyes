#!/usr/bin/env python3
"""Build the Orphic Eyes hackathon demo video from two raw OBS recordings.

Put this file next to clip1.mp4 and clip2.mp4, then run:

    python make_demo.py --probe     # contact sheets in out/probe/ to check timestamps
    python make_demo.py             # builds out/orphic-eyes-demo.mp4 and verifies it

Needs ffmpeg/ffprobe on PATH (winget install Gyan.FFmpeg) and Pillow (pip install pillow).
Every edit decision lives in SHOTS below: tweak a start/end time or a zoom focus and re-run.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
WORK = OUT / "work"
W, H, FPS = 1920, 1080, 30

# Look
BG = (241, 242, 245)          # soft light gray
INK = (17, 17, 17)            # caption black
ORANGE = (249, 115, 22)       # #F97316
DARK_BG = (14, 15, 19)
SCALE = 0.84                  # recording size on the canvas
VW, VH = 1612, 906            # 1920*0.84, 1080*0.84 rounded to even
VX = (W - VW) // 2            # 154
VY = H - VH - 26              # 148: leaves a caption band above the window
RADIUS = 22
CAPTION_SIZE = 62
CAPTION_CY = VY // 2 + 2      # caption vertically centred in the band

# ---------------------------------------------------------------------------
# Captions. Wrap the key word in *asterisks* to make it orange.
CAPTIONS = {
    "c2": "Before vs After. Every change, *boxed.*",
    "c3": "*Flip* Before and After.",
    "c4": "Drag a box. It *snaps* to the element.",
    "c5": "Move it. Exact to *2 px.*",
    "c6": "One click. A *precise* prompt for any AI.",
}

# ---------------------------------------------------------------------------
# Shot list. Hard cuts between every entry.
#   clip/start/end: source range in seconds
#   speed: playback speed (1.5-2 for slow parts)
#   zoom: 1.0 = full window; 1.4-1.6 = punch-in.
#   fx/fy: point the zoom centres on (0..1 of the frame; 0.5/0.5 = middle).
#          --probe draws a crosshair there on the contact sheets. Unused when zoom is 1.0.
#   ramp: True = ease in from 1.0 over 0.7 s; False = start already zoomed
#   hold: seconds to freeze the last frame
# Times come from the brief; check them with --probe.
SHOTS = [
    # 1. Intro cards
    dict(card="intro1", dur=1.8),
    dict(card="intro2", dur=2.3),
    # 2. Try a sample -> side by side with change boxes
    dict(clip="clip1.mp4", start=12.4, end=15.4, speed=1.0, fx=0.5, fy=0.5, cap="c2"),  # "Try a sample" button
    dict(clip="clip1.mp4", start=15.4, end=21.4, speed=1.5, fx=0.5, fy=0.5, cap="c2"),  # full side-by-side view
    dict(clip="clip1.mp4", start=21.4, end=28.4, speed=1.75, zoom=1.4, fx=0.5, fy=0.45, cap="c2"),  # change boxes on the After side
    # 3. Overlay view, flipping Before/After
    dict(clip="clip1.mp4", start=34.0, end=41.0, speed=1.75, fx=0.5, fy=0.5, cap="c3"),  # full Overlay view
    dict(clip="clip1.mp4", start=41.0, end=49.0, speed=1.75, zoom=1.4, fx=0.5, fy=0.5, cap="c3"),  # Before/After toggle + changed area
    # 4. Drag + snap
    dict(clip="clip1.mp4", start=52.6, end=57.4, speed=1.0, zoom=1.4, fx=0.5, fy=0.5, cap="c4"),  # box being dragged + snap
    dict(clip="clip1.mp4", start=75.6, end=81.4, speed=1.25, zoom=1.5, fx=0.5, fy=0.5, cap="c4"),  # "Start free" button
    # 5. Move + Confirm
    dict(clip="clip2.mp4", start=15.6, end=23.4, speed=1.4, zoom=1.4, fx=0.5, fy=0.5, cap="c5"),  # dragged box snapping
    dict(clip="clip2.mp4", start=23.6, end=28.2, speed=1.0, fx=0.5, fy=0.5, cap="c5", hold=0.6),  # Confirm button / "Requests (1)"
    # 6. Verify - Round 2 modal + Copy prompt, zoomed and held so the prompt reads
    dict(clip="clip2.mp4", start=49.6, end=55.6, speed=1.5, fx=0.5, fy=0.5, cap="c6"),  # "Verify - Round 2" modal opening
    dict(clip="clip2.mp4", start=55.6, end=59.6, speed=1.0, zoom=1.6, fx=0.5, fy=0.5, ramp=True, cap="c6"),  # prompt text in modal
    dict(clip="clip2.mp4", start=59.6, end=62.0, speed=1.0, zoom=1.6, fx=0.5, fy=0.5, ramp=False, cap="c6", hold=1.0),  # prompt text + "Copy prompt to clipboard"
    # 7. Principle card
    dict(card="pixels", dur=3.6),
    # 8. Dark outro
    dict(card="outro", dur=4.5),
]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",      # Segoe UI Bold
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REG_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size, bold=True):
    for p in FONT_CANDIDATES if bold else FONT_REG_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        sys.stderr.write(" ".join(map(str, cmd)) + "\n" + r.stderr[-3000:])
        raise SystemExit(f"command failed: {cmd[0]}")
    return r.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out)["format"]["duration"])


# ---------------------------------------------------------------------------
# Graphics
def parse_rich(text):
    """'A *b* c' -> [('A ', INK), ('b', ORANGE), (' c', INK)]"""
    parts, on = [], False
    for i, chunk in enumerate(text.split("*")):
        if chunk:
            parts.append((chunk, ORANGE if on else INK))
        on = not on
    return parts


def draw_rich(img, text, size, cy, ink=INK, max_w=W - 160):
    d = ImageDraw.Draw(img)
    while True:
        f = font(size)
        parts = [(t, ink if c == INK else c) for t, c in parse_rich(text)]
        total = sum(f.getlength(t) for t, _ in parts)
        if total <= max_w or size < 30:
            break
        size -= 2
    x = (W - total) / 2
    for t, c in parts:
        d.text((x, cy), t, font=f, fill=c, anchor="lm")
        x += f.getlength(t)


def make_background():
    bg = Image.new("RGB", (W, H), BG)
    # soft shadow under the floating window
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((VX, VY + 14, VX + VW, VY + VH + 14), RADIUS, fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    bg.paste(Image.new("RGB", (W, H), (60, 66, 80)), (0, 0), sh)
    # hairline border so the light-theme app separates from the light background
    ImageDraw.Draw(bg).rounded_rectangle((VX - 1, VY - 1, VX + VW, VY + VH), RADIUS + 1, outline=(214, 217, 223), width=2)
    bg.save(WORK / "bg.png")

    mask = Image.new("L", (VW * 4, VH * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, VW * 4 - 1, VH * 4 - 1), RADIUS * 4, fill=255)
    mask.resize((VW, VH), Image.LANCZOS).save(WORK / "mask.png")


def make_caption(key):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_rich(img, CAPTIONS[key], CAPTION_SIZE, CAPTION_CY)
    img.save(WORK / f"cap_{key}.png")


def make_card(name):
    if name == "outro":
        img = Image.new("RGB", (W, H), DARK_BG)
        d = ImageDraw.Draw(img)
        d.text((W / 2, 452), "Orphic Eyes", font=font(132), fill=(255, 255, 255), anchor="mm")
        d.rounded_rectangle((W / 2 - 40, 548, W / 2 + 40, 556), 4, fill=ORANGE)
        d.text((W / 2, 620), "Visual review for AI-built UI", font=font(46, False), fill=(200, 204, 212), anchor="mm")
        d.text((W / 2, 700), "Built by Ilham Musyafa", font=font(36, False), fill=(140, 146, 158), anchor="mm")
    else:
        img = Image.new("RGB", (W, H), BG)
        if name == "intro1":
            draw_rich(img, "Your UI *changed.*", 110, H / 2)
        elif name == "intro2":
            draw_rich(img, "Orphic Eyes shows *exactly* what.", 104, H / 2)
        elif name == "pixels":
            for i, line in enumerate(["*Pixels* only.", "No page code.", "Runs locally."]):
                draw_rich(img, line, 104, H / 2 + (i - 1) * 132)
    img.save(WORK / f"card_{name}.png")


# ---------------------------------------------------------------------------
# Rendering
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
       "-r", str(FPS), "-video_track_timescale", "15360", "-an"]


def render_card(i, s):
    out = WORK / f"shot_{i:02d}.mp4"
    n = round(s["dur"] * FPS)
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / f"card_{s['card']}.png"),
         "-vf", "format=yuv420p", "-frames:v", str(n)] + ENC + [str(out)])
    return out, n / FPS


def render_clip(i, s, clip_len):
    out = WORK / f"shot_{i:02d}.mp4"
    start = min(s["start"], clip_len - 0.5)
    end = min(s["end"], clip_len - 0.05)          # never read past the end (no black tail)
    speed = s.get("speed", 1.0)
    hold = s.get("hold", 0.0) + max(0.0, (s["end"] - end) / speed)
    src_dur = end - start
    n = round((src_dur / speed + hold) * FPS)

    z = s.get("zoom", 1.0)
    chain = f"setpts=(PTS-STARTPTS)/{speed},fps={FPS}"
    if hold > 0:
        chain += f",tpad=stop_mode=clone:stop_duration={hold:.3f}"
    if z > 1.0:
        fx, fy = s.get("fx", 0.5), s.get("fy", 0.5)
        if s.get("ramp", True):
            p = "min(1,on/21)"                       # 0.7 s ease-in (smoothstep)
            zexpr = f"1+{z - 1}*({p})*({p})*(3-2*({p}))"
        else:
            zexpr = str(z)
        # 2x upscale first so zoompan's integer crop offsets don't cause visible jitter
        chain += (f",scale=3840:2160:flags=bicubic,zoompan=z='{zexpr}'"
                  f":x='max(0,min(iw-iw/zoom,iw*{fx}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,ih*{fy}-ih/zoom/2))':d=1:s={VW}x{VH}:fps={FPS}")
    else:
        chain += f",scale={VW}:{VH}:flags=lanczos"
    fg = (f"[1:v]{chain},format=rgba[v];[2:v]format=gray[m];[v][m]alphamerge[vm];"
          f"[0:v][vm]overlay={VX}:{VY}[b];[b][3:v]overlay=0:0,format=yuv420p[o]")
    run(["ffmpeg", "-y", "-v", "error",
         "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / "bg.png"),
         "-ss", f"{start:.3f}", "-t", f"{src_dur:.3f}", "-i", str(HERE / s["clip"]),
         "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / "mask.png"),
         "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / f"cap_{s['cap']}.png"),
         "-filter_complex", fg, "-map", "[o]", "-frames:v", str(n)] + ENC + [str(out)])
    return out, n / FPS


SCENE_OF = {"intro1": 1, "intro2": 1, "c2": 2, "c3": 3, "c4": 4, "c5": 5, "c6": 6, "pixels": 7, "outro": 8}
SCENE_NAME = {1: "Intro: Your UI changed. / Orphic Eyes shows exactly what.",
              2: "Try a sample: Before vs After. Every change, boxed.",
              3: "Overlay: Flip Before and After.",
              4: "Drag + snap: Drag a box. It snaps to the element.",
              5: "Move + Confirm: Move it. Exact to 2 px.",
              6: "Verify + Copy prompt: One click. A precise prompt for Hermes.",
              7: "Card: Pixels only. No page code. Runs locally.",
              8: "Dark outro: Orphic Eyes / Visual review plugin for Hermes Agent / Built by Ilham Musyafa"}


def build():
    for c in ("clip1.mp4", "clip2.mp4"):
        if not (HERE / c).exists():
            raise SystemExit(f"missing {c} next to make_demo.py")
    WORK.mkdir(parents=True, exist_ok=True)
    lens = {c: duration(HERE / c) for c in ("clip1.mp4", "clip2.mp4")}
    make_background()
    for k in CAPTIONS:
        make_caption(k)
    for name in ("intro1", "intro2", "pixels", "outro"):
        make_card(name)

    parts, t, scenes = [], 0.0, {}
    for i, s in enumerate(SHOTS):
        path, d = render_card(i, s) if "card" in s else render_clip(i, s, lens[s["clip"]])
        sc = SCENE_OF[s.get("card") or s["cap"]]
        scenes.setdefault(sc, [t, t])[1] = t + d
        parts.append(path)
        t += d
        print(f"  shot {i:2d}  {d:5.2f}s  -> {t:6.2f}s")

    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    joined = WORK / "joined.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    final = OUT / "orphic-eyes-demo.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-t", f"{t:.3f}", "-movflags", "+faststart", str(final)])

    lines = [f"{SCENE_NAME[k]}  {v[0]:5.1f}s - {v[1]:5.1f}s" for k, v in sorted(scenes.items())]
    (OUT / "scenes.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    verify(final)


def verify(final):
    info = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt",
                           "-of", "json", str(final)]))
    d = float(info["format"]["duration"])
    print(json.dumps(info, indent=1))
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    ok = (v["width"], v["height"]) == (W, H) and v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p" \
        and v["r_frame_rate"] == "30/1" and a and a[0]["codec_name"] == "aac" and d < 90
    # 6 frames across the video
    fdir = OUT / "check"
    fdir.mkdir(exist_ok=True)
    for k in range(6):
        ts = d * (k + 0.5) / 6
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(final), "-frames:v", "1", str(fdir / f"frame_{k}_{ts:05.1f}s.png")])
    # black-frame scan
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(final), "-vf", "blackdetect=d=0.03:pix_th=0.10", "-an", "-f", "null", "-"],
                       stderr=subprocess.PIPE, text=True)
    black = [l for l in r.stderr.splitlines() if "black_start" in l]
    size_mb = int(info["format"]["size"]) / 1e6
    print(f"\n{final}  {d:.2f}s  {size_mb:.1f} MB  spec_ok={bool(ok)}  black_segments={len(black)}")
    print(f"check frames: {fdir}")


def probe():
    """Contact sheets (1 frame per second, labelled) to confirm the timestamps."""
    pdir = OUT / "probe"
    pdir.mkdir(parents=True, exist_ok=True)
    for c in ("clip1.mp4", "clip2.mp4"):
        tmp = pdir / c.replace(".mp4", "")
        tmp.mkdir(exist_ok=True)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(HERE / c), "-vf", "fps=1,scale=384:-2", str(tmp / "%04d.jpg")])
        frames = sorted(tmp.glob("*.jpg"))
        cols, tw, th = 6, 384, 216 + 28
        for page in range(0, len(frames), 36):
            chunk = frames[page:page + 36]
            sheet = Image.new("RGB", (cols * tw, ((len(chunk) + cols - 1) // cols) * th), (255, 255, 255))
            d = ImageDraw.Draw(sheet)
            for j, fp in enumerate(chunk):
                x, y = (j % cols) * tw, (j // cols) * th
                sheet.paste(Image.open(fp), (x, y + 28))
                sec = page + j  # frame k is at ~k s
                d.text((x + 6, y + 4), f"{c} {sec // 60:02d}:{sec % 60:02d}", font=font(20), fill=(0, 0, 0))
                for si, s in enumerate(SHOTS):
                    if s.get("clip") != c or not (s["start"] - 0.5 <= sec <= s["end"]):
                        continue
                    cx, cy = x + s["fx"] * tw, y + 28 + s["fy"] * 216
                    z = s.get("zoom", 1.0)
                    if z > 1.0:  # area the zoom will show
                        zw, zh = tw / z, 216 / z
                        zx = x + max(0, min(tw - zw, s["fx"] * tw - zw / 2))
                        zy = y + 28 + max(0, min(216 - zh, s["fy"] * 216 - zh / 2))
                        d.rectangle((zx, zy, zx + zw, zy + zh), outline=ORANGE, width=2)
                    d.line((cx - 12, cy, cx + 12, cy), fill=(230, 30, 30), width=2)
                    d.line((cx, cy - 12, cx, cy + 12), fill=(230, 30, 30), width=2)
                    d.text((cx + 6, cy + 4), f"shot {si}" + (f" {z}x" if z > 1 else ""), font=font(14), fill=(230, 30, 30))
            sheet.save(pdir / f"{c[:-4]}_sheet_{page // 36}.jpg", quality=88)
        shutil.rmtree(tmp)
    print(f"contact sheets in {pdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="only make timestamp contact sheets")
    ap.add_argument("--verify", action="store_true", help="only verify out/orphic-eyes-demo.mp4")
    a = ap.parse_args()
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found: winget install Gyan.FFmpeg (then open a new terminal)")
    if a.probe:
        probe()
    elif a.verify:
        verify(OUT / "orphic-eyes-demo.mp4")
    else:
        build()
