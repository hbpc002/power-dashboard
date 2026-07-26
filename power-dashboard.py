#!/usr/bin/env python3
import http.server, json, os, urllib.parse, time, mimetypes, shutil
from collections import deque

HP = os.path.expanduser("~/power-dashboard.html")
PORT = 8899

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".bmp": "image/bmp", ".ico": "image/x-icon",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".aac": "audio/aac",
    ".mp4": "video/mp4", ".webm": "video/webm", ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska", ".mov": "video/quicktime",
    ".txt": "text/plain", ".log": "text/plain", ".json": "application/json",
    ".html": "text/html", ".css": "text/css", ".js": "application/javascript",
    ".py": "text/x-python", ".sh": "text/x-shell", ".conf": "text/plain",
    ".yaml": "text/yaml", ".yml": "text/yaml", ".xml": "application/xml",
    ".csv": "text/csv", ".md": "text/markdown",
}

def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None

def read_int(path):
    v = read_file(path)
    return int(v) if v else None

def get_mime(path):
    _, ext = os.path.splitext(path)
    return MIME_MAP.get(ext.lower(), mimetypes.guess_type(path)[0] or "application/octet-stream")

def is_text_mime(m):
    return m.startswith("text/") or m in ("application/json", "application/xml", "application/javascript")

def safe_path(user_path):
    try:
        t = os.path.realpath(user_path)
        if os.path.exists(t):
            return t
    except: pass
    return None

def list_dir(path):
    sp = safe_path(path)
    if not sp or not os.path.isdir(sp): return None
    entries = []
    try:
        for name in sorted(os.listdir(sp)):
            full = os.path.join(sp, name)
            is_dir = os.path.isdir(full)
            sz = os.path.getsize(full) if not is_dir else 0
            mt = os.path.getmtime(full)
            mime = get_mime(name) if not is_dir else None
            entries.append({"name": name, "is_dir": is_dir, "size": sz, "mtime": mt, "mime": mime})
    except PermissionError: pass
    return {"path": path, "entries": entries}

def read_file_content(path, max_lines=200):
    sp = safe_path(path)
    if not sp or not os.path.isfile(sp): return None
    mime = get_mime(sp)
    txt = is_text_mime(mime)
    try:
        if txt:
            with open(sp, "r", errors="replace") as f:
                lines = f.readlines()[:max_lines]
            return {"path": path, "content": "".join(lines), "total_lines": len(lines), "truncated": len(lines)>=max_lines, "mime": mime, "is_text": True}
        else:
            with open(sp, "rb") as f:
                data = f.read()
            return {"path": path, "size": len(data), "mime": mime, "is_text": False, "can_preview": mime.startswith("image/")}
    except: return None

def delete_path(user_path):
    sp = safe_path(user_path)
    if not sp or not os.path.exists(sp): return {"error": "not found"}
    try:
        if os.path.isdir(sp):
            shutil.rmtree(sp)
            return {"ok": True}
        elif os.path.isfile(sp):
            os.remove(sp)
            return {"ok": True}
        else:
            return {"error": "not a file or dir"}
    except PermissionError: return {"error": "permission denied"}
    except Exception as e: return {"error": str(e)}

def write_file(path, content):
    sp = safe_path(path)
    if not sp or not os.path.isfile(sp): return {"error": "not found"}
    try:
        with open(sp, "w") as f:
            f.write(content)
        return {"ok": True}
    except PermissionError: return {"error": "permission denied"}
    except Exception as e: return {"error": str(e)}

def get_battery():
    bats, acs, usbs = [], [], []
    sp = "/sys/class/power_supply"
    for name in os.listdir(sp):
        up = os.path.join(sp, name, "uevent")
        if not os.path.exists(up): continue
        data = {}
        with open(up) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    data[k] = v
        t = data.get("POWER_SUPPLY_TYPE")
        if t == "Battery": bats.append(data)
        elif t == "Mains": acs.append(data)
        elif t == "USB": usbs.append(data)
    return {"batteries": bats, "ac": acs, "usb": usbs}

def get_cpu_temp():
    v = read_int("/sys/class/hwmon/hwmon4/temp1_input")
    if v is not None: return v / 1000.0
    v = read_int("/sys/class/thermal/thermal_zone0/temp")
    if v is not None: return v / 1000.0
    return None


_prev_cpu = None
_prev_cpus = {}

def get_cpu_usage():
    global _prev_cpu, _prev_cpus
    try:
        with open("/proc/stat") as f:
            lines = f.readlines()
        # Overall
        line = lines[0]
        parts = [int(x) for x in line.strip().split()[1:]]
        total = sum(parts)
        idle = parts[3] + parts[4]
        pct = 0
        if _prev_cpu:
            dtotal = total - _prev_cpu["total"]
            didle = idle - _prev_cpu["idle"]
            pct = (1 - didle / dtotal) * 100 if dtotal > 0 else 0
        _prev_cpu = {"total": total, "idle": idle}
        # Per-core
        per = {}
        for ln in lines[1:]:
            if not ln.startswith("cpu"): break
            cols = ln.strip().split()
            core = cols[0]
            vals = [int(x) for x in cols[1:]]
            t = sum(vals)
            i = vals[3] + vals[4]
            if core in _prev_cpus:
                dt = t - _prev_cpus[core]["total"]
                di = i - _prev_cpus[core]["idle"]
                per[core] = round((1 - di / dt) * 100, 1) if dt > 0 else 0
            else:
                per[core] = 0
            _prev_cpus[core] = {"total": t, "idle": i}
        return {"overall": round(pct, 1), "per_core": per}
    except Exception:
        return None

def get_cpu_freq():
    v = read_int("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    if v is not None: return v / 1000.0
    v = read_int("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq")
    if v is not None: return v / 1000.0
    return None

def get_cpu_cores(): return os.cpu_count() or 0

def get_mem():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k] = int(v.strip().split()[0])
        t = info.get("MemTotal", 0)*1024
        a = info.get("MemAvailable", 0)*1024
        return {"total": t, "available": a, "cached": info.get("Cached", 0)*1024, "buffers": info.get("Buffers", 0)*1024}
    except: return None

def get_load():
    try:
        with open("/proc/loadavg") as f:
            p = f.read().strip().split()
            return p[0], p[1], p[2]
    except: return None, None, None

def get_disk_io():
    try:
        r = w = 0
        with open("/proc/diskstats") as f:
            for line in f:
                p = line.split()
                if len(p) >= 14:
                    r += int(p[5])*512
                    w += int(p[9])*512
        return {"read": r, "write": w}
    except: return None

def get_disk_usage():
    try:
        mounts = []
        with open("/proc/mounts") as f:
            for line in f:
                p = line.split()
                if len(p) >= 2 and p[0].startswith("/dev/") and p[1].startswith("/"):
                    mounts.append(p[1])
        seen, res = set(), []
        for m in mounts:
            if m in seen or "/snap/" in m: continue
            seen.add(m)
            try:
                s = os.statvfs(m)
                total = s.f_frsize * s.f_blocks
                free = s.f_frsize * s.f_bfree
                avail = s.f_frsize * s.f_bavail
                used = total - free
                res.append({"mount": m, "total": total, "used": used, "free": free, "avail": avail, "pct": round(used / total * 100, 1) if total else 0})
            except: pass
        return res
    except: return None

def get_network():
    try:
        res = []
        nd = "/sys/class/net"
        if os.path.isdir(nd):
            for iface in os.listdir(nd):
                sd = os.path.join(nd, iface, "statistics")
                if not os.path.isdir(sd): continue
                def rs(n):
                    v = read_file(os.path.join(sd, n))
                    return int(v) if v else 0
                st = read_file(os.path.join(nd, iface, "operstate")) or "unknown"
                res.append({"ifname": iface, "operstate": st, "rx_bytes": rs("rx_bytes"), "tx_bytes": rs("tx_bytes")})
        return res
    except: return None

_history = deque(maxlen=2400)

def push_history(stats):
    net = stats.get("network")
    net_rx = net_tx = None
    if net:
        net_rx = sum(int(i.get("rx_bytes", 0)) for i in net if i.get("operstate") == "up")
        net_tx = sum(int(i.get("tx_bytes", 0)) for i in net if i.get("operstate") == "up")
    mem = stats.get("memory")
    mem_used = 1 - mem["available"] / mem["total"] if mem and mem.get("total") else None
    load = stats.get("load")
    load1 = float(load[0]) if load and load[0] else None
    _history.append({
        "ts": time.time(), "cpu_temp": stats.get("cpu_temp"),
        "cpu_usage": stats.get("cpu_usage") and stats["cpu_usage"].get("overall"),
        "mem_used": mem_used, "load1": load1,
        "net_rx_raw": net_rx, "net_tx_raw": net_tx,
    })

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        q = urllib.parse.urlparse(self.path).query
        ps = urllib.parse.parse_qs(q)
        if p == "/api/stats":
            s = get_battery()
            d = {
                "batteries": s["batteries"], "ac": s["ac"],"usb": s["usb"],
                "cpu_temp": get_cpu_temp(), "cpu_freq": get_cpu_freq(), "cpu_usage": get_cpu_usage(),
                "cpu_cores": get_cpu_cores(),
                "memory": get_mem(), "load": get_load(),
                "disk_io": get_disk_io(), "disk_usage": get_disk_usage(), "network": get_network(),
            }
            push_history(d)
            self.send_json(d)
        elif p == "/api/history":
            self.send_json(list(_history))
        elif p == "/api/files":
            fp = ps.get("path", ["/home/hbpc"])[0]
            act = ps.get("action", ["list"])[0]
            if act == "read" and "file" in ps:
                self.send_json(read_file_content(ps["file"][0]))
            elif act == "serve" and "file" in ps:
                self.serve_file(ps["file"][0])
            else:
                self.send_json(list_dir(fp))
        else:
            h = read_file(HP) or "<h1>Not found</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(h.encode())
    def do_DELETE(self):
        q = urllib.parse.urlparse(self.path).query
        ps = urllib.parse.parse_qs(q)
        if "file" in ps:
            self.send_json(delete_path(ps["file"][0]))
        else:
            self.send_error(400, "Missing file parameter")
    def do_PUT(self):
        self._handle_upload()
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        q = urllib.parse.urlparse(self.path).query
        ps = urllib.parse.parse_qs(q)
        if p == "/api/files" and ps.get("action", [""])[0] == "save" and "file" in ps:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            self.send_json(write_file(ps["file"][0], body))
        elif p == "/api/files" and ps.get("action", [""])[0] == "upload" and "file" in ps:
            self._handle_upload()
        else:
            self.send_error(400, "Invalid request")
    def _handle_upload(self):
        q = urllib.parse.urlparse(self.path).query
        ps = urllib.parse.parse_qs(q)
        fp = ps.get("file", [None])[0]
        sp = safe_path(fp)
        if not sp:
            self.send_json({"error": "invalid path"})
            return
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        try:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with open(sp, "wb") as f:
                f.write(data)
            self.send_json({"ok": True, "size": len(data)})
        except Exception as e:
            self.send_json({"error": str(e)})
    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def serve_file(self, filepath):
        sp = safe_path(filepath)
        if not sp or not os.path.isfile(sp):
            self.send_error(404, "File not found")
            return
        try:
            with open(sp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", get_mime(sp))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except:
            self.send_error(500)
    def log_message(self, fmt, *args): pass

if __name__ == "__main__":
    print(f"Dashboard: http://localhost:{PORT}")
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
