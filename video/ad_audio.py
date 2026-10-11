"""Voice (Kokoro neural TTS, no filters) + synthesized beat -> build/ad_audio.wav, build/ad_timeline.json
VOICE=am_michael (am_adam, am_puck, ...) | SPEED=1.0
Human voice override: put video/voice_override/<line id, two digits>.wav (e.g. 03.wav). Line ids are printed by ad_data.py."""
import json, os, subprocess, hashlib, wave, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"; os.makedirs(f"{H}/voice_cache", exist_ok=True); os.makedirs(f"{H}/voice_override", exist_ok=True)
SR = 48000; D = json.load(open(f"{B}/ad.json")); BEAT = D["beat"]
VOICE = os.environ.get("VOICE", "am_michael"); SPEED = float(os.environ.get("SPEED", "1.0"))
starts = {}; t = 0.0
for n, b in D["scenes"]: starts[n] = t; t += b * BEAT
TOTAL = t; N = int((TOTAL + 1.5) * SR)
def dec(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()
_k = None
def tts(i, text):
    ov = f"{H}/voice_override/{i:02d}.wav"
    if os.path.exists(ov): return dec(ov)
    key = hashlib.md5(f"{VOICE}{SPEED}{text}".encode()).hexdigest()[:12]; w = f"{H}/voice_cache/{key}.wav"
    if not os.path.exists(w):
        global _k
        if _k is None:
            from kokoro_onnx import Kokoro; _k = Kokoro(f"{H}/models/kokoro-v1.0.onnx", f"{H}/models/voices-v1.0.bin")
        import soundfile as sf
        a, sr = _k.create(text, voice=VOICE, speed=SPEED, lang="en-us"); sf.write(w, a, sr)
    return dec(w)
voice = np.zeros(N, np.float32); timeline = []; cursor = 0.0
for ln in D["lines"]:
    a = tts(ln["id"], ln["text"])
    nz = np.where(np.abs(a) > 0.02)[0]; a = a[nz[0]:nz[-1] + 1] if len(nz) else a          # trim silence only
    a = a * (0.9 / max(1e-6, np.abs(a).max()))                                              # plain peak normalise
    st = max(starts[ln["scene"]] + ln["off"] * BEAT, cursor + 0.12); i = int(st * SR); voice[i:i + len(a)] += a[: N - i]
    cursor = st + len(a) / SR
    room = (starts[ln["scene"]] + dict(D["scenes"])[ln["scene"]] * BEAT) - cursor
    print(f"{ln['id']:2d} {ln['scene']:8} want {ln['off']*BEAT:5.2f}s got {st-starts[ln['scene']]:5.2f}s dur {len(a)/SR:4.2f}s room-left-in-scene {room:5.2f}s")
    timeline.append(dict(id=ln["id"], start=round(st, 2), end=round(cursor, 2)))
# ---------------- music: kick / snare / hats / bass / arp, 126 bpm
rng = np.random.RandomState(7); music = np.zeros(N, np.float32)
def add(arr, t0, g=1.0):
    i = int(t0 * SR)
    if i < N: arr = arr[: N - i]; music[i:i + len(arr)] += g * arr.astype(np.float32)
def tt(d): return np.arange(int(d * SR)) / SR
def kick():
    x = tt(0.28); f = 45 + 90 * np.exp(-x * 28); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 11) * 1.0
def snare():
    x = tt(0.22); n = rng.randn(len(x)); n = n - np.convolve(n, np.ones(6) / 6, 'same'); return (n * 0.6 + np.sin(2 * np.pi * 190 * x) * 0.5) * np.exp(-x * 20)
def hat(o=False):
    x = tt(0.25 if o else 0.05); n = rng.randn(len(x)); n = n - np.convolve(n, np.ones(4) / 4, 'same'); return n * np.exp(-x * (14 if o else 70)) * 0.35
def bass(f, d):
    x = tt(d); w = np.sin(2 * np.pi * f * x) + 0.35 * np.sin(4 * np.pi * f * x) + 0.15 * np.tanh(3 * np.sin(2 * np.pi * f * x)); return w * np.exp(-x * 5) * np.minimum(1, x * 200)
def pluck(f, d=0.3):
    x = tt(d); w = 2 * ((f * x) % 1) - 1; k = np.convolve(w, np.ones(24) / 24, 'same'); return k * np.exp(-x * 9)
ROOT = [55.0, 43.65, 65.41, 49.0]; CH = [[220, 261.6, 329.6], [174.6, 220, 261.6], [261.6, 329.6, 392], [196, 246.9, 293.7]]
nb = int(TOTAL / BEAT) + 1
for b in range(nb):
    t0 = b * BEAT; sc = next(n for n in reversed(D["scenes"]) if starts[n[0]] <= t0 + 1e-6)[0]; lb = (t0 - starts[sc]) / BEAT
    full = sc != "hook" or lb >= 8; bar = (b // 4) % 4
    if sc == "money" and 6 <= lb < 8: continue                       # drop-out before the counter
    fade = 1.0 if sc != "close" else max(0.0, min(1.0, (starts["close"] + dict(D["scenes"])["close"] * BEAT - t0) / (5 * BEAT)))
    if fade <= 0: continue
    add(kick(), t0, 0.9 * fade)
    if b % 2 == 1 and full: add(snare(), t0, 0.5 * fade)
    if full:
        for h8 in (0, 0.5): add(hat(h8 > 0), t0 + h8 * BEAT, 0.5 * fade)
        add(bass(ROOT[bar], BEAT * 0.48), t0, 0.55 * fade); add(bass(ROOT[bar] * (2 if b % 2 else 1), BEAT * 0.48), t0 + BEAT / 2, 0.45 * fade)
        for k, h8 in enumerate((0, 0.25, 0.5, 0.75)): add(pluck(CH[bar][(b * 4 + k) % 3] * 2), t0 + h8 * BEAT, 0.10 * fade)
    elif lb >= 4: add(hat(), t0 + BEAT / 2, 0.4)
    if lb == 0 and b > 0: add(np.convolve(rng.randn(int(0.9 * SR)), np.ones(3) / 3, 'same') * np.exp(-tt(0.9) * 5), t0, 0.22 * fade)   # crash at each scene start
# stingers
def whoosh(d, f0, f1, g):
    x = tt(d); ph = 2 * np.pi * (f0 * x + (f1 - f0) * x ** 2 / (2 * d)); return g * np.sin(np.pi * x / d) ** 2 * (np.sin(ph) * 0.5 + rng.randn(len(x)) * 0.12)
fx = np.zeros(N, np.float32)
def put(sc, beat, a):
    i = int((starts[sc] + beat * BEAT) * SR); a = a[: max(0, N - i)]; fx[i:i + len(a)] += a.astype(np.float32)
buz = lambda: (lambda x: 0.5 * (((x % 0.22) < 0.12) & (x < 0.7)) * np.sign(np.sin(2 * np.pi * 170 * x)))(tt(0.9))
put("money", 1.0, buz()); put("money", 5.5, whoosh(0.6, 3000, 300, 0.3)); put("money", 8.0, whoosh(4.7, 200, 2400, 0.12)); put("money", 18.0, whoosh(0.4, 200, 3000, 0.4))
put("money", 18.0, kick() * 1.0); put("money", 18.0, np.sin(2 * np.pi * 1760 * tt(0.5)) * np.exp(-tt(0.5) * 8) * 0.3)
for sc in ("hook", "montage", "proof"): put(sc, 0, whoosh(0.35, 400, 2500, 0.2))
for b in (0, 8, 16, 24, 32): put("proof", b, kick() * 0.5)
put("close", 8.0, kick() * 1.0); put("close", 8.0, whoosh(0.4, 300, 2800, 0.3))
# duck music under voice
env = np.abs(voice); k = int(0.05 * SR); env = np.convolve(env, np.ones(k) / k, 'same')
rel = np.zeros_like(env); a = 0.0
for i in range(0, N, 480):                               # 10 ms steps, fast attack / slow release
    v = env[i:i + 480].max(); a = v if v > a else a * 0.965; rel[i:i + 480] = a
duck = 1 - 0.62 * np.clip(rel * 6, 0, 1)
music_g = 0.30 / max(1e-6, np.percentile(np.abs(music), 99.5))
mix = voice * 0.95 + (music * music_g + fx * 0.8) * duck
mix *= 0.89 / max(0.89, np.abs(mix).max())
with wave.open(f"{B}/ad_mix.wav", "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{B}/ad_mix.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", "-ac", "2", f"{B}/ad_audio.wav"], check=True)
json.dump(dict(starts=starts, total=TOTAL, lines=timeline), open(f"{B}/ad_timeline.json", "w"), indent=1); print("total", round(TOTAL, 2))
