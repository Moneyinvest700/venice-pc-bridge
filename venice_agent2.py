# venice_agent2.py - token-protected PC control for Venice (text-only friendly).
# Every action returns plain text that includes what is on screen (OCR lines with click coordinates).
import http.server, socketserver, urllib.parse, threading, io, os, re, time, ctypes, subprocess, datetime, traceback
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "venice_agent.py"), encoding="utf-8").read()
TOKEN = re.search(r'TOKEN\s*=\s*"([^"]+)"', SRC).group(1)
PORT = 8798
LOCK = threading.Lock()
LOG = []
def log(m):
    LOG.append(datetime.datetime.now().strftime("%H:%M:%S ") + m); del LOG[:-40]

def active_title():
    try:
        u = ctypes.windll.user32
        h = u.GetForegroundWindow(); n = u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1); return b.value
    except Exception:
        return "?"

def shot_jpg():
    b = io.BytesIO(); pyautogui.screenshot().convert("RGB").save(b, "JPEG", quality=70); return b.getvalue()

def ocr_lines():
    p = os.path.join(os.environ.get("TEMP", HERE), "venice_look.png")
    pyautogui.screenshot().save(p)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "ocr.ps1"), p],
                           capture_output=True, text=True, timeout=40)
        out = r.stdout.strip()
        return out if out else ("(no text found) " + r.stderr.strip()[:300])
    except Exception as e:
        return "OCR failed: %s" % e

def look():
    w, h = pyautogui.size(); x, y = pyautogui.position()
    return "SCREEN %dx%d | mouse at %d,%d | active window: %s\nTEXT ON SCREEN, one per line as 'centerX,centerY | text' (use those numbers for click):\n%s\n" % (w, h, x, y, active_title(), ocr_lines())

def one(q, k):
    return q[k][0] if k in q and q[k] else None

def do(q):
    st = one(q, "steps")
    if st:
        res = []
        for part in st.split(";"):
            part = part.strip()
            if not part: continue
            k, _, v = part.partition("=")
            if k.strip() == "wait":
                time.sleep(min(float(v or 1), 10)); res.append("wait " + v); continue
            q2 = {k.strip(): [v], "wait": ["0.4"]}
            res.append(do(q2))
        time.sleep(float(one(q, "wait") or 1.5))
        return " | ".join(res)
    res = []
    if one(q, "click"):
        x, y = [int(v) for v in one(q, "click").split(",")]
        pyautogui.click(x, y, clicks=2 if one(q, "double") else 1, button=one(q, "button") or "left"); res.append("clicked %d,%d" % (x, y)); time.sleep(0.3)
    if one(q, "type") is not None:
        t = one(q, "type")[:500]; pyautogui.write(t, interval=0.03); res.append("typed %d chars" % len(t))
    if one(q, "key"):
        ks = [k.strip().lower().replace("win", "winleft") for k in one(q, "key").replace(" ", "+").split("+") if k.strip()]
        pyautogui.hotkey(*ks); res.append("key " + one(q, "key"))
    if one(q, "open"):
        u = one(q, "open")
        if not re.match(r"^https?://", u): raise ValueError("open only allows http(s) URLs")
        os.startfile(u); res.append("opened " + u)
    if one(q, "scroll"):
        pyautogui.scroll(int(one(q, "scroll"))); res.append("scrolled " + one(q, "scroll"))
    time.sleep(float(one(q, "wait") or 1.5))
    log(", ".join(res) or "look")
    return ", ".join(res)

HELP = """PC control for Venice. All answers are plain text. One fetch = do the action, then it reports what is on screen.
Base: {b}
Look only:  {b}/look
Act + look: {b}/do?click=683,384        (click at x,y; add &double=1 for double click)
            {b}/do?type=hello           (type text)
            {b}/do?key=enter            (enter, esc, tab, backspace, ctrl+l, ctrl+t, win ...)
            {b}/do?open=https://google.com   (open a website; http/https only)
            {b}/do?scroll=-5            (negative = down)
Many steps in ONE fetch (saves your daily scrape quota): {b}/do?steps=key=win%2Br;wait=1;type=notepad;key=enter&wait=2
  (steps are separated by ; and each is click=x,y or type=text or key=name or open=url or scroll=n; text must not contain ;)
You can combine: /do?click=640,60&type=youtube.com&key=enter&wait=2
Screen is 1366x768. Use the center coordinates from the TEXT ON SCREEN list. After every step read the new list and verify before the next step.
Recent actions:
{log}
"""

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ct="text/plain; charset=utf-8"):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        try:
            u = urllib.parse.urlparse(self.path); parts = [p for p in u.path.split("/") if p]
            if not parts or parts[0] != TOKEN:
                time.sleep(1); return self._send(404, "not found")
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True); act = parts[1] if len(parts) > 1 else ""
            base = "/" + TOKEN
            with LOCK:
                if act == "": return self._send(200, HELP.format(b=base, log="\n".join(LOG[-10:]) or "(none)"))
                if act == "shot.jpg": return self._send(200, shot_jpg(), "image/jpeg")
                if act == "look": return self._send(200, look())
                if act == "do":
                    r = do(q); return self._send(200, "DONE: %s\n%s" % (r, look()))
                if act in ("click", "type", "key", "open", "scroll"):
                    m = {"click": "click", "type": "type", "key": "key", "open": "open", "scroll": "scroll"}
                    q2 = dict(q)
                    if act == "click" and "x" in q: q2["click"] = ["%s,%s" % (q["x"][0], q["y"][0])]
                    elif act == "type": q2["type"] = q.get("text", [""])
                    elif act in ("key", "open", "scroll"): q2[act] = q.get({"key": "key", "open": "url", "scroll": "n"}[act], q.get(act, [""]))
                    r = do(q2); return self._send(200, "DONE: %s\n%s" % (r, look()))
            return self._send(404, "unknown")
        except Exception as e:
            log("ERROR %s" % e); traceback.print_exc(); self._send(500, "error: %s" % e)
    def log_message(self, *a): pass

class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True

if __name__ == "__main__":
    S(("127.0.0.1", PORT), H).serve_forever()
