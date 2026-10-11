"""Voice with word timestamps + quiet beat -> build/ad2_audio.wav, build/ad2_cues.json
ENGINE=auto|elevenlabs|edge   (auto: ElevenLabs if ~/.config/elevenlabs/key exists, else edge-tts)
ELEVEN_VOICE=Brian (premade voice name)  EDGE_VOICE=en-US-AndrewMultilingualNeural
Human voice override: video/voice_override/<scene>.wav (hook, story, proof, more, close) -> timing then falls back to even word spacing."""
import asyncio, base64, hashlib, json, os, re, subprocess, wave, time, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; os.makedirs(f"{H}/voice_cache", exist_ok=True)
SR = 48000; D = json.load(open(f"{B}/ad2.json")); BEAT = 60 / 126
KEYF = os.path.expanduser("~/.config/elevenlabs/key"); ENGINE = os.environ.get("ENGINE", "auto")
if ENGINE == "auto": ENGINE = "elevenlabs" if os.path.exists(KEYF) else "edge"
EDGE_VOICE = os.environ.get("EDGE_VOICE", "en-US-AndrewMultilingualNeural"); ELEVEN_VOICE = os.environ.get("ELEVEN_VOICE", "Liam")
norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())
def dec(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()
def split_markers(text):
    """-> clean text, [(cue, [anchor words])]"""
    cues = []; clean = ""; 
    parts = re.split(r"(\[[a-z]+\])", text)
    pending = []
    for p in parts:
        m = re.fullmatch(r"\[([a-z]+)\]", p)
        if m: pending.append(m.group(1)); continue
        if pending and p.strip():
            toks = p.split()[:2]
            for c in pending: cues.append((c, [norm(t) for t in toks]))
            pending = []
        clean += p
    return clean, cues
async def edge(text, path):
    import edge_tts
    for attempt in range(8):
        try:
            c = edge_tts.Communicate(text, EDGE_VOICE, boundary="WordBoundary"); ws = []; audio = b""
            async for ch in c.stream():
                if ch["type"] == "audio": audio += ch["data"]
                elif ch["type"] == "WordBoundary": ws.append((ch["offset"] / 1e7, ch["text"]))
            if audio and ws: open(path, "wb").write(audio); return ws
        except Exception as e: print("edge retry", attempt, type(e).__name__)
        await asyncio.sleep(1.5)
    raise RuntimeError("edge-tts failed")
def eleven(text, path):
    import requests; key = open(KEYF).read().strip(); hd = {"xi-api-key": key}
    vs = requests.get("https://api.elevenlabs.io/v1/voices", headers=hd, timeout=30).json()["voices"]
    pick = next((v for v in vs if v["name"].split(" - ")[0].strip().lower() == ELEVEN_VOICE.lower() and v.get("category") == "premade"), None) or next(v for v in vs if v.get("category") == "premade")
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{pick['voice_id']}/with-timestamps?output_format=mp3_44100_128", headers=hd, timeout=120,
        json={"text": text, "model_id": os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2"), "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.35, "use_speaker_boost": True}})
    r.raise_for_status(); j = r.json(); open(path, "wb").write(base64.b64decode(j["audio_base64"]))
    al = j["alignment"]; ch, st = al["characters"], al["character_start_times_seconds"]; ws = []; cur = ""; t0 = 0
    for c, s in zip(ch, st):
        if c.isspace():
            if cur: ws.append((t0, cur)); cur = ""
        else:
            if not cur: t0 = s
            cur += c
    if cur: ws.append((t0, cur))
    return ws
def synth(scene, text):
    ov = f"{H}/voice_override/{scene}.wav"
    if os.path.exists(ov):
        a = dec(ov); toks = text.split(); d = len(a) / SR; return a, [(i * d / len(toks), w) for i, w in enumerate(toks)]
    key = hashlib.md5(f"{ENGINE}{EDGE_VOICE}{ELEVEN_VOICE}{text}".encode()).hexdigest()[:12]; mp3 = f"{H}/voice_cache/{key}.mp3"; js = f"{H}/voice_cache/{key}.json"
    if not (os.path.exists(mp3) and os.path.exists(js)):
        ws = asyncio.run(edge(text, mp3)) if ENGINE == "edge" else eleven(text, mp3); json.dump(ws, open(js, "w"))
    return dec(mp3), json.load(open(js))
def match(ws, anchors, start):
    for i in range(start, len(ws)):
        if norm(ws[i][1]) == anchors[0] and (len(anchors) < 2 or i + 1 >= len(ws) or norm(ws[i + 1][1]) == anchors[1]): return i
    for i in range(start, len(ws)):
        if norm(ws[i][1]) == anchors[0]: return i
    return None
paras = []; t = 0.35; cues = {}; bounds = {}
voice_parts = []
for scene, text in D["paras"]:
    clean, cl = split_markers(text); a, ws = synth(scene, clean)
    a = a * (0.9 / max(1e-6, np.abs(a).max()))
    nz = np.where(np.abs(a) > 0.01)[0]; lead = nz[0] / SR if len(nz) else 0
    pstart = t - lead + 0.0                       # shift so first sound happens at t
    start_sound = t; end_sound = pstart + (nz[-1] / SR if len(nz) else len(a) / SR)
    last = 0
    for cue, anc in cl:
        i = match(ws, anc, last); 
        if i is None: i = min(len(ws) - 1, int(len(ws) * 0.5)); print("cue fallback", cue)
        last = i; cues[cue] = round(pstart + ws[i][0] - 0.05, 3)
    voice_parts.append((pstart, a)); bounds[scene] = [start_sound - 0.2, end_sound + 0.45]
    t = end_sound + 0.9
names = [s for s, _ in D["paras"]]
bounds[names[0]][0] = 0.0
for i in range(len(names) - 1): m = (bounds[names[i]][1] + bounds[names[i + 1]][0]) / 2; bounds[names[i]][1] = m; bounds[names[i + 1]][0] = m
bounds[names[-1]][1] = bounds[names[-1]][1] + 2.2
TOTAL = bounds[names[-1]][1]; N = int((TOTAL + 1) * SR)
voice = np.zeros(N, np.float32)
for ps, a in voice_parts:
    i = max(0, int(ps * SR)); voice[i:i + len(a)] += a[: N - i]
# ---- quiet, simple beat
rng = np.random.RandomState(3); music = np.zeros(N, np.float32)
tt = lambda d: np.arange(int(d * SR)) / SR
def add(arr, t0, g):
    i = int(t0 * SR)
    if 0 <= i < N: arr = arr[: N - i]; music[i:i + len(arr)] += g * arr.astype(np.float32)
x = tt(0.25); kick = np.sin(2 * np.pi * np.cumsum(45 + 80 * np.exp(-x * 30)) / SR) * np.exp(-x * 12)
x = tt(0.05); n = rng.randn(len(x)); hat = (n - np.convolve(n, np.ones(4) / 4, 'same')) * np.exp(-x * 70)
def bass(f, d=0.22): x = tt(d); return (np.sin(2 * np.pi * f * x) + .3 * np.sin(4 * np.pi * f * x)) * np.exp(-x * 6) * np.minimum(1, x * 200)
ROOT = [55.0, 43.65, 65.41, 49.0]
for b in range(int(TOTAL / BEAT) + 1):
    t0 = b * BEAT; fade = min(1, max(0, (TOTAL - t0) / 3.0)) * min(1, t0 / 1.0 + .2)
    add(kick, t0, .8 * fade); add(hat, t0 + BEAT / 2, .35 * fade); add(bass(ROOT[(b // 4) % 4]), t0, .45 * fade)
    if b % 2: add(bass(ROOT[(b // 4) % 4] * 2, .15), t0 + BEAT / 2, .25 * fade)
fx = np.zeros(N, np.float32)
def put(t0, a, g=1.0):
    i = int(t0 * SR); a = a[: max(0, N - i)]; fx[i:i + len(a)] += g * a.astype(np.float32)
def whoosh(d, f0, f1): x = tt(d); return np.sin(np.pi * x / d) ** 2 * (np.sin(2 * np.pi * (f0 * x + (f1 - f0) * x ** 2 / (2 * d))) * .5 + rng.randn(len(x)) * .1)
xb = tt(1.0); boom = np.sin(2 * np.pi * (60 - 25 * xb) * xb) * np.exp(-xb * 5)
buz = ((tt(0.8) % 0.22) < 0.12) * np.sign(np.sin(2 * np.pi * 170 * tt(0.8))) * 0.5
for s in names[1:]: put(bounds[s][0] - 0.08, whoosh(0.3, 500, 2600), .22)
put(cues["mk"], boom, .35); put(cues["alert"], buz, .5); put(cues["tv"], boom, .5); put(cues["logo"], boom, .5)
env = np.convolve(np.abs(voice), np.ones(2400) / 2400, 'same'); rel = np.zeros_like(env); a_ = 0.0
for i in range(0, N, 480): v = env[i:i + 480].max(); a_ = v if v > a_ else a_ * .97; rel[i:i + 480] = a_
duck = 1 - 0.65 * np.clip(rel * 6, 0, 1)
mix = voice * 0.95 + (music * (0.20 / max(1e-6, np.percentile(np.abs(music), 99.5))) + fx * .7) * duck
mix *= 0.89 / max(0.89, np.abs(mix).max())
with wave.open(f"{B}/ad2_mix.wav", "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{B}/ad2_mix.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", "-ac", "2", f"{B}/ad2_audio.wav"], check=True)
json.dump(dict(cues=cues, bounds=bounds, total=TOTAL, engine=ENGINE, voice=EDGE_VOICE if ENGINE == "edge" else ELEVEN_VOICE), open(f"{B}/ad2_cues.json", "w"), indent=1)
print("engine", ENGINE, "total", round(TOTAL, 2)); print(json.dumps(cues)); print(json.dumps(bounds))
