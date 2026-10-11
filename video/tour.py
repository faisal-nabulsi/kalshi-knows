"""Records the real site (1920x1080) following a timed choreography -> build/tour.mp4 (40 s, 30 fps)"""
import asyncio, json, os, time, glob, subprocess, shutil
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"
API = json.load(open(f"{H}/../docs/config.json"))["api"]
SITE = os.environ.get("SITE", "https://kalshi-knows.pages.dev")
DUR = dict(json.load(open(f"{B}/script.json"))["scenes"])["tour"]
SCROLL = """([y,d])=>new Promise(r=>{const s=scrollY,t0=performance.now();document.documentElement.style.scrollBehavior='auto';
 const f=n=>{let p=Math.min(1,(n-t0)/(d*1000));p=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;scrollTo(0,s+(y-s)*p);p<1?requestAnimationFrame(f):r()};requestAnimationFrame(f)})"""
TOP = """(sel)=>{const e=document.querySelector(sel);return e?e.getBoundingClientRect().top+scrollY-80:0}"""
FIND = """(txt)=>{const e=[...document.querySelectorAll('h2,h3,p,div,span')].find(x=>x.children.length<3&&x.textContent.trim().toUpperCase().startsWith(txt));return e?e.getBoundingClientRect().top+scrollY-100:0}"""


async def main():
    rd = f"{B}/rec"; shutil.rmtree(rd, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=rd, record_video_size={"width": 1920, "height": 1080})
        pg = await ctx.new_page(); t_open = time.time()
        await pg.goto(f"{SITE}/?present=1&quiet=1&api={API}#/live", wait_until="networkidle"); await pg.wait_for_timeout(5000)
        T = time.time(); trim = T - t_open

        async def at(s): await asyncio.sleep(max(0, T + s - time.time()))

        async def go(h):
            await pg.evaluate(f"location.hash='#/{h}'"); await pg.evaluate("scrollTo(0,0)")

        async def scroll_to_text(txt, d):
            y = await pg.evaluate(FIND, txt); await pg.evaluate(SCROLL, [y, d])
        await at(0.8); await pg.evaluate("document.documentElement.style.scrollBehavior='auto'"); await pg.evaluate("y=>scrollTo(0,y)", await pg.evaluate(TOP, "#live")); await pg.wait_for_timeout(1200)
        await at(4.6); await pg.evaluate(SCROLL, [await pg.evaluate(TOP, "#receipts"), 1.8])
        await at(9.3); await pg.keyboard.press("t")
        await at(14.2)
        try: await pg.click("#to-reveal", timeout=1500)
        except Exception: pass
        await at(17.0)
        try: await pg.click("#to-close", timeout=1500)
        except Exception: pass
        await at(17.4); await go("proof")
        await at(19.0); await scroll_to_text("HEAD-TO-HEAD", 1.6)
        await at(24.0); await scroll_to_text("MODEL LEADERBOARD", 1.6)
        await at(27.4); await go("auto")
        await at(30.0); await scroll_to_text("MOVERS ACROSS", 2.0)
        await at(34.2); await go("dutch")
        await at(36.6); await pg.evaluate(SCROLL, [300, 2.0])
        await at(DUR + 0.5)
        await ctx.close(); await b.close()
    webm = glob.glob(f"{rd}/*.webm")[0]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{trim:.2f}", "-i", webm, "-t", str(DUR), "-vf", "fps=30,scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{B}/tour.mp4"], check=True)
    print("tour done, trim", round(trim, 2))

asyncio.run(main())
