"""Deterministic frame renderer for the synthetic scenes. usage: frames.py [scene...]"""
import asyncio, json, os, sys, subprocess
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"
FPS = 30; WORKERS = int(os.environ.get("WORKERS", 5))
S = json.load(open(f"{B}/ad.json")); DATA = open(f"{B}/ad.json").read()
async def worker(p, scene, idxs, outdir):
    b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1920, "height": 1080})
    await pg.add_init_script(f"window.DATA={DATA}")
    await pg.goto(f"file://{H}/ad.html"); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(1500)
    for i in idxs:
        await pg.evaluate(f"render('{scene}',{i/FPS})")
        await pg.screenshot(path=f"{outdir}/{i:05d}.jpg", type="jpeg", quality=93)
    await b.close()
async def main():
    names = sys.argv[1:] or [n for n, _ in S["scenes"] if n != "montage"]
    async with async_playwright() as p:
        for n in names:
            dur = dict(S["scenes"])[n] * S["beat"]; nf = int(round(dur * FPS)); out = f"{B}/afr_{n}"; os.makedirs(out, exist_ok=True)
            await asyncio.gather(*[worker(p, n, list(range(w, nf, WORKERS)), out) for w in range(WORKERS)])
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{out}/%05d.jpg", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", f"{B}/ad_{n}.mp4"], check=True)
            subprocess.run(["rm", "-rf", out]); print("done", n, nf)
asyncio.run(main())
