"""TTS (macOS say, original character 'Big Spoiler Steve') + stingers -> build/audio.wav, build/timeline.json"""
import json, os, re, subprocess, numpy as np, hashlib
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; os.makedirs(f"{B}/tts", exist_ok=True)
SR = 48000
VOICE = os.environ.get("STEVE_VOICE", "Rocko (English (US))"); RATE = os.environ.get("STEVE_RATE", "228")
S = json.load(open(f"{B}/script.json"))
starts = {}; t = 0.0
for name, dur in S["scenes"]: starts[name] = t; t += dur
TOTAL = t
def dec(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()
FX = ("atempo=1.07,highpass=f=100,equalizer=f=180:t=q:w=1:g=3,equalizer=f=3200:t=q:w=1.2:g=4,"
      "acompressor=threshold=0.05:ratio=5:attack=4:release=80:makeup=4,alimiter=limit=0.9")
def tts(text):
    k = hashlib.md5(f"{VOICE}{RATE}{FX}{text}".encode()).hexdigest()[:12]; w = f"{B}/tts/{k}.wav"
    if not os.path.exists(w):
        a = f"{B}/tts/{k}.aiff"
        subprocess.run(["say", "-v", VOICE, "-r", RATE, "-o", a, text], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a, "-af", FX, "-ar", str(SR), "-ac", "1", w], check=True); os.remove(a)
    return dec(w)
N = int((TOTAL + 2) * SR); voice = np.zeros(N, np.float32); caps = []; cursor = 0.0
for ln in S["lines"]:
    start = max(starts[ln["scene"]] + ln["off"], cursor + 0.15)
    sents = [x for x in re.findall(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", ln["say"]) if x.strip()]
    csents = [x for x in re.findall(r"[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$", ln["text"]) if x.strip()]
    if len(csents) != len(sents): csents = [ln["text"]] * 1; sents = [ln["say"]]
    t0 = start
    for ss, cs in zip(sents, csents):
        a = tts(ss.strip()); i = int(t0 * SR); voice[i:i + len(a)] += a
        caps.append(dict(start=round(t0, 2), end=round(t0 + len(a) / SR + 0.15, 2), text=cs.strip(), scene=ln["scene"])); t0 += len(a) / SR + 0.12
    cursor = t0
    nominal = starts[ln["scene"]] + ln["off"]
    print(f"{ln['scene']:6} want {ln['off']:5.1f} got {start-starts[ln['scene']]:5.1f} end {t0-starts[ln['scene']]:5.1f} (scene {dict(S['scenes'])[ln['scene']]})")
# ---- stingers (pure synthesis, no samples)
def tt(d): return np.arange(int(d * SR)) / SR
def whoosh(d=0.7, f0=300, f1=3500, g=0.35):
    x = tt(d); ph = 2 * np.pi * (f0 * x + (f1 - f0) * x ** 2 / (2 * d)); env = np.sin(np.pi * x / d) ** 2
    n = np.random.RandomState(1).randn(len(x)) * 0.25
    return g * env * (np.sin(ph) * 0.6 + np.convolve(n, np.ones(12) / 12, 'same'))
def boom(d=1.1, g=0.7):
    x = tt(d); return g * np.exp(-x * 4.5) * (np.sin(2 * np.pi * (60 - 25 * x) * x) + 0.25 * np.random.RandomState(2).randn(len(x)) * np.exp(-x * 25))
def buzz(g=0.45):
    x = tt(1.0); gate = ((x % 0.25) < 0.13) & (x < 0.75); return g * gate * np.sign(np.sin(2 * np.pi * 160 * x)) * 0.5 + g * gate * np.sin(2 * np.pi * 320 * x) * 0.3
def ping(g=0.3, f=1760):
    x = tt(0.6); return g * np.exp(-x * 7) * np.sin(2 * np.pi * f * x)
def riser(d, g=0.18):
    x = tt(d); return g * (x / d) ** 2 * np.sin(2 * np.pi * (200 + 1400 * x / d) * x)
def tick(g=0.25):
    x = tt(0.05); return g * np.exp(-x * 90) * np.sin(2 * np.pi * 1000 * x)
fx = np.zeros(N, np.float32)
def put(sc, off, a):
    i = int((starts[sc] + off) * SR); a = a[: max(0, N - i)]; fx[i:i + len(a)] += a.astype(np.float32)
put("cold", 0.0, boom()); put("cold", 0.0, whoosh(0.5, 2500, 300)); put("cold", 3.2, riser(8.8))
for q in L if (L := [4.0, 5.0, 8.0, 10.0, 12.0]) else []: put("cold", q, tick())
put("money", 0.0, whoosh(0.6)); put("money", 8.96, buzz()); put("money", 8.96, boom(0.5, 0.35)); put("money", 28.3, boom(1.4, 0.9)); put("money", 28.3, ping(0.35)); put("money", 28.3, whoosh(0.4, 3000, 400, 0.4))
for q in np.arange(9.4, 28.2, 1.0): put("money", q, tick(0.08))
for q in (0, 9.3, 17.5, 27.6, 34.3): put("tour", q, whoosh(0.5, 500, 3000, 0.28))
for q in (0, 6.0, 11.8, 17.8): put("how", q, whoosh(0.45, 400, 2800, 0.25)); put("how", q + 0.35, ping(0.15, 880))
put("close", 0.0, boom(1.0, 0.6)); put("close", 0.0, whoosh(0.5)); put("close", 16.0, ping(0.25, 1320)); put("close", 16.0, whoosh(0.5, 300, 2500, 0.2))
# duck stingers under voice a little
env = np.convolve(np.abs(voice), np.ones(SR // 10) / (SR // 10), 'same'); duck = 1 - 0.45 * np.clip(env * 8, 0, 1)
mix = voice * 1.0 + fx * duck
np.save(f"{B}/mix.npy", mix)
raw = f"{B}/mix_raw.wav"
import wave
with wave.open(raw, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", "loudnorm=I=-15:TP=-1.5:LRA=9", f"{B}/audio.wav"], check=True)
json.dump(dict(starts=starts, total=TOTAL, caps=caps), open(f"{B}/timeline.json", "w"), indent=1)
print("total", TOTAL)
