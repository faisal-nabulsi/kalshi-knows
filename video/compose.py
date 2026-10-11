"""Burned-in captions (transparent PNGs) + concat scenes + mux audio -> video/kalshi-knows-demo.mp4"""
import asyncio, json, os, subprocess, html
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; os.makedirs(f"{B}/caps", exist_ok=True)
T = json.load(open(f"{B}/timeline.json")); S = json.load(open(f"{B}/script.json"))
caps = T["caps"]
PAGE = """<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&display=swap"><style>
html,body{margin:0;background:transparent}#w{position:absolute;left:0;right:0;bottom:68px;display:flex;justify-content:center}
#c{max-width:1640px;padding:14px 30px 16px 26px;background:rgba(10,10,11,.86);border-left:8px solid #ff4d1a;color:#ede8df;font:600 38px/1.22 Archivo,Arial,sans-serif;text-align:left}</style></head><body><div id=w><div id=c></div></div></body></html>"""
async def caps_png():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.set_content(PAGE); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(1200)
        for i, c in enumerate(caps):
            await pg.evaluate("t=>document.getElementById('c').textContent=t", c["text"])
            await pg.screenshot(path=f"{B}/caps/{i:03d}.png", omit_background=True)
        await b.close()
asyncio.run(caps_png())
with open(f"{B}/concat.txt", "w") as f:
    for n, _ in S["scenes"]: f.write(f"file '{B}/{n}.mp4'\n")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{B}/concat.txt", "-c", "copy", f"{B}/scenes_all.mp4"], check=True)
cmd = ["ffmpeg", "-v", "error", "-y", "-i", f"{B}/scenes_all.mp4", "-i", f"{B}/audio.wav"]
for i in range(len(caps)): cmd += ["-i", f"{B}/caps/{i:03d}.png"]
fc = []; prev = "0:v"
for i, c in enumerate(caps):
    out = f"v{i}"; fc.append(f"[{prev}][{i+2}:v]overlay=0:0:enable='between(t,{c['start']},{c['end']})'[{out}]"); prev = out
cmd += ["-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-t", str(T["total"]), "-movflags", "+faststart", f"{H}/kalshi-knows-demo.mp4"]
subprocess.run(cmd, check=True)
print("wrote", f"{H}/kalshi-knows-demo.mp4")
