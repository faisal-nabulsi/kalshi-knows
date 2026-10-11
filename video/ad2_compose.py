"""Chips on product shots + concat hook/story/proof/more/close + audio -> video/kalshi-knows-ad.mp4"""
import asyncio, json, os, subprocess
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; CU = json.load(open(f"{B}/ad2_cues.json")); C = CU["cues"]; BD = CU["bounds"]
CHIPS = ["HIDE SPOILERS", "SYNC TO YOUR STREAM", "AUTO: DEMO ORDERS"]
PAGE = """<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@900&display=swap"><style>html,body{margin:0;background:transparent}
#c{position:absolute;left:60px;bottom:60px;padding:6px 40px 14px 32px;background:rgba(10,10,11,.92);border-left:14px solid #ff4d1a;color:#ede8df;font:900 120px/1 'Big Shoulders Display',Impact,sans-serif;text-transform:uppercase;white-space:nowrap}</style></head><body><div id=c></div></body></html>"""
async def chips():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1920, "height": 1080}); await pg.set_content(PAGE); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(1500)
        for i, t in enumerate(CHIPS):
            await pg.evaluate("t=>document.getElementById('c').textContent=t", t); await pg.screenshot(path=f"{B}/a2_chip{i}.png", omit_background=True)
        await b.close()
asyncio.run(chips())
ms = BD["more"][0]; segs = [(0.0, C["sync"] - ms), (C["sync"] - ms, C["agent"] - ms), (C["agent"] - ms, BD["more"][1] - ms)]
cmd = ["ffmpeg", "-v", "error", "-y"]
for i in range(3): cmd += ["-i", f"{B}/a2_shot{i}.mp4"]
for i in range(3): cmd += ["-i", f"{B}/a2_chip{i}.png"]
tr = [f"[{i}:v]trim=0:{e-s:.3f},setpts=PTS-STARTPTS,scale=1920:1080,setsar=1,fps=30,format=yuv420p[t{i}]" for i, (s, e) in enumerate(segs)]
fc = tr + ["[t0][t1][t2]concat=n=3:v=1:a=0[m]"]; prev = "m"
pre = C["hide"] - ms                                  # lead-in before the first cue shows shot 0 too
for i, (s, e) in enumerate(segs):
    z = f"v{i}"; fc.append(f"[{prev}][{3+i}:v]overlay=x='-w+min(w+60,(t-{s+0.05:.3f})*w*9)':y=0:enable='between(t,{s+0.05:.3f},{e:.3f})':eval=frame[{z}]"); prev = z
cmd += ["-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-r", "30", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{B}/a2_more.mp4"]
subprocess.run(cmd, check=True)
with open(f"{B}/a2_concat.txt", "w") as f:
    for n in ("hook", "what", "story", "proof", "more", "close"): f.write(f"file '{B}/a2_{n}.mp4'\n")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{B}/a2_concat.txt", "-i", f"{B}/ad2_audio.wav", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{CU['total']:.3f}", "-movflags", "+faststart", f"{H}/kalshi-knows-ad.mp4"], check=True)
print("wrote", f"{H}/kalshi-knows-ad.mp4")
