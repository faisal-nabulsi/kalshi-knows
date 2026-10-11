"""Records 5 short product shots (real site, 1280x720 viewport so text is big, upscaled to 1080p) -> build/ad_shot{0..4}.mp4"""
import asyncio, json, os, time, glob, subprocess, shutil
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"
API = json.load(open(f"{H}/../docs/config.json"))["api"]; SITE = os.environ.get("SITE", "https://kalshi-knows.pages.dev")
BEAT = 60 / 126; DUR = [7 * BEAT] * 4 + [8 * BEAT]
TOP = "(sel)=>{const e=document.querySelector(sel);return e?e.getBoundingClientRect().top+scrollY-70:0}"
FIND = "(txt)=>{const e=[...document.querySelectorAll('h2,h3,p,div,span')].find(x=>x.children.length<3&&x.textContent.trim().toUpperCase().startsWith(txt));return e?e.getBoundingClientRect().top+scrollY-90:0}"
SLOW = "([dy,d])=>new Promise(r=>{const s=scrollY,t0=performance.now();const f=n=>{const p=Math.min(1,(n-t0)/(d*1000));scrollTo(0,s+dy*p);p<1?requestAnimationFrame(f):r()};requestAnimationFrame(f)})"
async def main():
    rd = f"{B}/ad_rec"; shutil.rmtree(rd, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=rd, record_video_size={"width": 1280, "height": 720})
        pg = await ctx.new_page(); t_open = time.time()
        await pg.goto(f"{SITE}/?present=1&quiet=1&api={API}#/live", wait_until="networkidle"); await pg.wait_for_timeout(4500)
        await pg.evaluate("(()=>{const d=document.createElement('div');d.style.cssText='position:fixed;inset:0;background:#fff;z-index:99999';document.body.appendChild(d);setTimeout(()=>d.remove(),400)})()")
        T = time.time(); wins = []
        async def at(s): await asyncio.sleep(max(0, T + s - time.time()))
        async def jump(y): await pg.evaluate("document.documentElement.style.scrollBehavior='auto'"); await pg.evaluate("y=>scrollTo(0,y)", y)
        # A receipts
        await jump(await pg.evaluate(TOP, "#receipts")); await at(1.2); wins.append(1.4); await pg.evaluate(SLOW, [60, DUR[0]])
        # B takeover
        await at(5.6); await pg.keyboard.press("t"); await at(6.4); wins.append(6.5); await at(6.5 + DUR[1] + .2)
        try: await pg.click("#to-close", timeout=1500)
        except Exception: pass
        # C shield
        await at(11.0); await pg.evaluate("location.hash='#/live'"); await jump(await pg.evaluate(TOP, "#live") + 330)
        await pg.evaluate("[...document.querySelectorAll('[data-shield]')].filter(e=>e.offsetParent).forEach(e=>e.click())")
        await at(12.4); wins.append(12.6); await pg.evaluate(SLOW, [40, DUR[2]])
        # D auto
        await at(17.0); await pg.evaluate("location.hash='#/auto'"); await jump(0); await at(18.2); wins.append(18.4); await pg.evaluate(SLOW, [50, DUR[3]])
        # E movers
        await at(22.6); await jump(await pg.evaluate(FIND, "MOVERS ACROSS")); await at(23.6); wins.append(23.8); await pg.evaluate(SLOW, [60, DUR[4]])
        await at(28.0)
        await ctx.close(); await b.close()
    webm = glob.glob(f"{rd}/*.webm")[0]
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", webm, "-t", "20", "-vf", "scale=64:36,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"], capture_output=True, text=True).stdout
    import re
    fr = re.findall(r"pts_time:([\d.]+)\s+lavfi.signalstats.YAVG=([\d.]+)", r.replace("\n", " "))
    dark = False; trim = None
    for t, y in fr:
        y = float(y)
        if y < 100: dark = True
        elif y > 200 and dark: trim = float(t); break
    print("sync at", trim)
    for i, (w, d) in enumerate(zip(wins, DUR)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{trim + w - 0.0:.2f}", "-i", webm, "-t", f"{d:.3f}", "-vf", "fps=30,scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{B}/ad_shot{i}.mp4"], check=True)
    print("shots done")
asyncio.run(main())
