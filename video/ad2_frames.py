"""Deterministic frames for hook/story/proof/close, timed from build/ad2_cues.json"""
import asyncio, json, os, sys, subprocess
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; FPS = 30; WORKERS = 5
DATA = open(f"{B}/ad2.json").read(); CUES = open(f"{B}/ad2_cues.json").read(); BD = json.loads(CUES)["bounds"]
async def worker(p, scene, idxs, outdir, t0):
    b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1920, "height": 1080})
    await pg.add_init_script(f"window.DATA={DATA};window.CUES={CUES}")
    await pg.goto(f"file://{H}/ad2.html"); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(1500)
    for i in idxs:
        await pg.evaluate(f"render('{scene}',{t0 + i / FPS})"); await pg.screenshot(path=f"{outdir}/{i:05d}.jpg", type="jpeg", quality=93)
    await b.close()
async def main():
    async with async_playwright() as p:
        for n in sys.argv[1:] or ["hook", "what", "story", "proof", "close"]:
            s, e = BD[n]; nf = int(round((e - s) * FPS)); out = f"{B}/a2fr_{n}"; os.makedirs(out, exist_ok=True)
            await asyncio.gather(*[worker(p, n, list(range(w, nf, WORKERS)), out, s) for w in range(WORKERS)])
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{out}/%05d.jpg", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", f"{B}/a2_{n}.mp4"], check=True)
            subprocess.run(["rm", "-rf", out]); print("done", n, nf)
asyncio.run(main())
