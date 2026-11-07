#!/usr/bin/env python3
"""
Tes kelayakan Orphic Eyes (tanpa Hermes).

Yang diuji:
  Tes 1 (kembar)      : halaman SAMA dipotret 2x -> selisih harus PERSIS 0 piksel.
  Tes 2 (sensitivitas): satu tombol digeser 8 piksel -> selisih harus ada dan
                        kotaknya harus berada di sekitar tombol saja.
  Tes 3 (tepi halus)  : halaman penuh teks, gradasi, dan sudut membulat dipotret
                        2x -> selisih harus 0 (menguji kebisingan anti-alias).

Cara pakai (PowerShell / terminal):
  pip install pillow
  python reference_capture_test.py
  python reference_capture_test.py --browser "C:\\Path\\ke\\msedge.exe"   (jika tidak terdeteksi)

Skrip ini hanya membuat berkas di folder 'orphic_out' di samping skrip,
membuka peramban lokal tanpa jendela (headless), dan tidak memakai internet.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError:
    print("Pillow belum terpasang. Jalankan:  pip install pillow")
    sys.exit(2)

HERE = Path(__file__).resolve().parent
OUT = HERE / "orphic_out"

W, H = 1280, 800
SHIFT = 8  # piksel

PAGE_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"><title>uji</title>
<style>
  html,body{{margin:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1d2433}}
  nav{{height:64px;background:#1d2433;color:#fff;display:flex;align-items:center;padding:0 24px;font-size:20px}}
  main{{padding:48px}}
  h1{{margin:0 0 12px;font-size:36px}}
  p{{margin:0 0 24px;font-size:18px;max-width:640px}}
  .btn{{position:relative;left:{shift}px;display:inline-block;padding:14px 28px;
        background:#2f6fed;color:#fff;border-radius:10px;font-size:18px}}
</style></head><body>
<nav>Halaman Uji Orphic Eyes</nav>
<main>
  <h1>Selamat datang</h1>
  <p>Ini halaman contoh untuk menguji apakah dua potret layar yang identik
     menghasilkan selisih nol, dan apakah pergeseran kecil terdeteksi.</p>
  <span class="btn">Mulai sekarang</span>
</main></body></html>
"""

REALISTIC = """<!doctype html>
<html><head><meta charset="utf-8"><title>realistis</title>
<style>
  html,body{margin:0;font-family:Georgia,'Times New Roman',serif;color:#222;
            background:linear-gradient(135deg,#eef2ff,#fdf2f8)}
  header{padding:28px 48px;font-size:30px;font-weight:bold}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;padding:0 48px}
  .card{background:#fff;border-radius:18px;padding:22px;box-shadow:0 6px 20px rgba(0,0,0,.12)}
  .card h3{margin:0 0 8px;font-size:22px}
  .card p{margin:0;font-size:15px;line-height:1.5}
  .pill{display:inline-block;margin-top:14px;padding:6px 16px;border-radius:999px;
        background:#10b981;color:#fff;font-size:14px;font-family:Arial,sans-serif}
</style></head><body>
<header>Dasbor contoh dengan teks, gradasi, dan sudut membulat</header>
<div class="grid">
  <div class="card"><h3>Pendapatan</h3><p>Lorem ipsum dolor sit amet, consectetur
    adipiscing elit, sed do eiusmod tempor incididunt ut labore.</p><span class="pill">+12,4%</span></div>
  <div class="card"><h3>Pengguna</h3><p>Ut enim ad minim veniam, quis nostrud exercitation
    ullamco laboris nisi ut aliquip ex ea commodo consequat.</p><span class="pill">+3,1%</span></div>
  <div class="card"><h3>Tiket</h3><p>Duis aute irure dolor in reprehenderit in voluptate
    velit esse cillum dolore eu fugiat nulla pariatur.</p><span class="pill">-0,8%</span></div>
</div></body></html>
"""


def find_browser(cli_value):
    if cli_value:
        return cli_value if os.path.exists(cli_value) else None
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        p = shutil.which(name)
        if p:
            return p
    return None


def capture(browser, html_path, png_path, extra_flags):
    """Potret satu halaman lokal dengan peramban headless."""
    profile = tempfile.mkdtemp(prefix="orphic_profile_")
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--force-prefers-reduced-motion",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=2000",
        f"--window-size={W},{H}",
        f"--user-data-dir={profile}",   # profil terpisah agar tidak bentrok dengan Edge/Chrome yang sedang terbuka
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ] + extra_flags
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            # Peramban macet: hentikan paksa, lalu lihat apakah potret sempat jadi.
            proc.kill()
            proc.wait()
    except OSError as exc:
        print(f"   Tidak bisa menjalankan peramban: {exc}")
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return png_path.exists() and png_path.stat().st_size > 0


def compare(path_a, path_b):
    a = Image.open(path_a).convert("RGB")
    b = Image.open(path_b).convert("RGB")
    if a.size != b.size:
        return {"same_size": False, "size_a": a.size, "size_b": b.size}
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    mask = diff.convert("L").point(lambda v: 255 if v > 0 else 0)
    changed = mask.histogram()[255]
    total = a.size[0] * a.size[1]
    max_delta = max(max(ch.getextrema()) for ch in diff.split())
    return {
        "same_size": True,
        "size": a.size,
        "changed_px": changed,
        "percent": 100.0 * changed / total,
        "bbox": bbox,
        "max_delta": max_delta,
    }


def verdict(ok):
    return "LULUS" if ok else "GAGAL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", help="Jalur ke msedge.exe / chrome.exe jika tidak terdeteksi otomatis")
    ap.add_argument("--no-sandbox", action="store_true", help="Hanya untuk container Linux/root")
    args = ap.parse_args()

    browser = find_browser(args.browser)
    if not browser:
        print("Peramban Edge/Chrome tidak ditemukan. Jalankan ulang dengan:")
        print('  python reference_capture_test.py --browser "C:\\Path\\ke\\msedge.exe"')
        sys.exit(2)
    extra = ["--no-sandbox"] if args.no_sandbox else []

    OUT.mkdir(exist_ok=True)
    pages = {
        "a": OUT / "page_a.html",
        "b": OUT / "page_b.html",
        "real": OUT / "page_real.html",
    }
    pages["a"].write_text(PAGE_TMPL.format(shift=0), encoding="utf-8")
    pages["b"].write_text(PAGE_TMPL.format(shift=SHIFT), encoding="utf-8")
    pages["real"].write_text(REALISTIC, encoding="utf-8")

    print(f"Peramban : {browser}")
    print(f"Ukuran   : {W}x{H}, skala layar 1")
    print("-" * 60)

    shots = {}
    plan = [("a1", "a"), ("a2", "a"), ("b1", "b"), ("r1", "real"), ("r2", "real")]
    for name, page in plan:
        png = OUT / f"{name}.png"
        if png.exists():
            png.unlink()
        ok = capture(browser, pages[page], png, extra)
        shots[name] = png if ok else None
        if not ok:
            print(f"Potret '{name}' GAGAL dibuat. Peramban mungkin menolak opsi headless.")
    if any(v is None for v in shots.values()):
        print("\nHasil: GAGAL di tahap potret. Kirim pesan ini ke Claude apa adanya.")
        sys.exit(1)

    results = []

    # Tes 1: kembar
    r1 = compare(shots["a1"], shots["a2"])
    ok1 = r1.get("same_size") and r1["changed_px"] == 0
    results.append(ok1)
    print("Tes 1  Halaman sama dipotret 2x (harus selisih PERSIS 0)")
    if r1.get("same_size"):
        print(f"       ukuran {r1['size']}, piksel beda = {r1['changed_px']}, selisih warna maks = {r1['max_delta']}")
    else:
        print(f"       ukuran potret berbeda: {r1['size_a']} vs {r1['size_b']}")
    print(f"       -> {verdict(ok1)}")

    # Tes 2: sensitivitas
    r2 = compare(shots["a1"], shots["b1"])
    ok2 = False
    if r2.get("same_size") and r2["bbox"]:
        x0, y0, x1, y1 = r2["bbox"]
        # Tombol ada di kiri-atas halaman (sekitar x 48..240, y 230..285). Beri ruang longgar,
        # tapi kotak selisih harus kecil dan tidak menyentuh menu atas (y < 64) atau tepi kanan.
        inside = (x0 >= 30 and x1 <= 360 and y0 >= 150 and y1 <= 340)
        small = (x1 - x0) <= 300 and (y1 - y0) <= 120
        ok2 = inside and small and r2["changed_px"] > 0
    results.append(ok2)
    print("\nTes 2  Tombol digeser 8 piksel (harus terdeteksi, hanya di area tombol)")
    if r2.get("same_size"):
        print(f"       piksel beda = {r2['changed_px']} ({r2['percent']:.3f}% halaman), kotak = {r2['bbox']}")
    print(f"       -> {verdict(ok2)}")

    # Tes 3: tepi halus
    r3 = compare(shots["r1"], shots["r2"])
    ok3 = r3.get("same_size") and r3["changed_px"] == 0
    results.append(ok3)
    print("\nTes 3  Halaman teks+gradasi+sudut bulat dipotret 2x (harus selisih 0)")
    if r3.get("same_size"):
        print(f"       piksel beda = {r3['changed_px']}, selisih warna maks = {r3['max_delta']}")
    print(f"       -> {verdict(ok3)}")

    print("-" * 60)
    if all(results):
        print("HASIL AKHIR: LULUS. Pendekatan 'peramban headless + Pillow' stabil di PC ini.")
    else:
        print("HASIL AKHIR: ADA YANG GAGAL. Salin seluruh keluaran ini dan kirim ke Claude.")
    print(f"Berkas hasil ada di: {OUT}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
