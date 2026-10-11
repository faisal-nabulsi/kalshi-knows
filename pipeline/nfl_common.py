import time, random, httpx, json, threading
KB="https://api.elections.kalshi.com/trade-api/v2"
_lock=threading.Lock(); _last=[0.0]
cl=httpx.Client(timeout=30)
def get(url, params=None, rate=0.34):
    for i in range(7):
        with _lock:
            w=_last[0]+rate-time.time()
            if w>0: time.sleep(w)
            _last[0]=time.time()
        try:
            r=cl.get(url,params=params)
        except Exception:
            time.sleep(2**i*0.5); continue
        if r.status_code==200: return r.json()
        if r.status_code in (429,500,502,503,504): time.sleep(2**i*0.7+random.random()); continue
        return None
    return None
