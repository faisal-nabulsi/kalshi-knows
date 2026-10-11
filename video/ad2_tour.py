"""3 product shots for the 'everything else' line, durations driven by the spoken cues -> build/a2_shot{0,1,2}.mp4"""
import asyncio, json, os, time, glob, subprocess, shutil, re
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"
API = json.load(open(f"{H}/../docs/config.json"))["api"]; SITE = os.environ.get("SITE", "https://kalshi-knows.pages.dev")
CU = json.load(open(f"{B}/ad2_cues.json")); C = CU["cues"]; end = CU["bounds"]["more"][1]
DUR = [C["sync"] - CU["bounds"]["more"][0], C["agent"] - C["sync"], end - C["agent"]]
TOP = "(sel)=>{const e=document.querySelector(sel);return e?e.getBoundingClientRect().top+scrollY-70:0}"
SLOW = "([dy,d])=>new Promise(r=>{const s=scrollY,t0=performance.now();const f=n=>{const p=Math.min(1,(n-t0)/(d*1000));scrollTo(0,s+dy*p);p<1?requestAnimationFrame(f):r()};requestAnimationFrame(f)})"
async def record():
    rd = f"{B}/a2_rec"; shutil.rmtree(rd, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=rd, record_video_size={"width": 1280, "height": 720})
        pg = await ctx.new_page()
        await pg.goto(f"{SITE}/?present=1&quiet=1&api={API}#/live", wait_until="domcontentloaded", timeout=60000)
        try: await pg.wait_for_function("document.querySelector('#live-meta')?.textContent.includes('GAMES TRACKED')", timeout=25000)
        except Exception: print("live-meta wait timed out; continuing")
        await pg.wait_for_timeout(3000)
        MARK = "(()=>{const d=document.createElement('div');d.style.cssText='position:fixed;left:0;top:0;width:60px;height:60px;background:#f0f;z-index:99999';document.body.appendChild(d);setTimeout(()=>d.remove(),450)})()"
        async def jump(y): await pg.evaluate("document.documentElement.style.scrollBehavior='auto'"); await pg.evaluate("y=>scrollTo(0,y)", y)
        async def settle(y):                      # re-assert scroll position (the site resets scroll after data loads)
            for _ in range(6):
                await jump(y); await pg.wait_for_timeout(350)
                if abs(await pg.evaluate("scrollY") - y) < 6: break
        async def shot(d, dy):
            await pg.evaluate(MARK); await pg.wait_for_timeout(700); await pg.evaluate(SLOW, [dy, d + .3]); await pg.wait_for_timeout(300)
        click_shield = "[...document.querySelectorAll('[data-shield]')].filter(e=>e.offsetParent).forEach(e=>e.click())"
        live_y = await pg.evaluate(TOP, "#live") + 330
        await settle(live_y); await pg.evaluate(click_shield); await pg.wait_for_timeout(500); await shot(DUR[0], 30)
        await pg.evaluate(click_shield); await pg.evaluate("[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&/YouTube TV/.test(e.textContent)).forEach(e=>e.click())"); await settle(live_y); await shot(DUR[1], 30)
        await pg.evaluate("location.hash='#/auto'"); await pg.wait_for_timeout(1200); await settle(0); await shot(DUR[2], 50)
        await ctx.close(); await b.close()
    webm = glob.glob(f"{rd}/*.webm")[0]
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", webm, "-vf", "crop=40:40:0:0,signalstats,metadata=print:key=lavfi.signalstats.UAVG:file=-", "-f", "null", "-"], capture_output=True, text=True).stdout
    fr = re.findall(r"pts_time:([\d.]+)\s+lavfi.signalstats.UAVG=([\d.]+)", r.replace("\n", " ")); marks = []
    for t, u in fr:
        if float(u) > 175 and (not marks or float(t) - marks[-1] > 1.5): marks.append(float(t))
    print("markers", marks)
    if len(marks) < 3: return False
    for i, (w, d) in enumerate(zip(marks[:3], DUR)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{w + 0.6:.2f}", "-i", webm, "-t", f"{d + 0.1:.3f}", "-vf", "fps=30,scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{B}/a2_shot{i}.mp4"], check=True)
    return True
for attempt in range(3):
    if asyncio.run(record()): print("shots done"); break
    print("sync flash not found, retrying")
else: raise SystemExit("tour recording failed")
