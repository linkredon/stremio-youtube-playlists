#!/usr/bin/env python3
"""Stremio YouTube Playlist addon. Python 3.10+ / yt-dlp."""
import json, os, re, subprocess, sys, time
from urllib.parse import urlparse, unquote, parse_qs, quote
from flask import Flask, jsonify, request, Response
from threading import Lock

HOST = os.environ.get("HOST","127.0.0.1")
PORT = int(os.environ.get("PORT", "7777"))
LIMIT = int(os.environ.get("MAX_VIDEOS","250"))
TTL = 1800
_cache = {}
_lock = Lock()
PID = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
VID = re.compile(r"^[A-Za-z0-9_-]{11}$")
PREFIX = "ypl:"
MANIFEST = {"id":"com.local.yt","version":"1.4.0","name":"YT Playlists",
 "resources":["catalog","meta","stream"],"types":["series"],
 "catalogs":[{"type":"series","id":"yt","name":"YT",
              "extra":[{"name":"search","isRequired":True}]}]}


def playlist_id(value):
    value = (value or "").strip()
    if PID.fullmatch(value):
        return value
    # Accept youtube.com/playlist?list=..., youtube.com/watch?v=...&list=...
    try:
        u = urlparse(value)
        h = (u.hostname or "").lower()
        if h not in ("youtube.com","www.youtube.com","m.youtube.com","music.youtube.com","youtu.be"):
            return None
        v = parse_qs(u.query).get("list",[""])[0]
        return v if PID.fullmatch(v) else None
    except Exception:
        return None

def media_id(pid):
    return PREFIX + pid

def playlist(pid):
    now=time.time()
    with _lock:
        found=_cache.get(pid)
        if found and now-found[0]<TTL:
            return found[1]
    # Do not download videos. Retrieves only metadata from public YouTube playlist.
    cmd=[sys.executable,"-m","yt_dlp","--flat-playlist","--dump-single-json",
         "--skip-download","--no-warnings","--playlist-end",str(LIMIT),
         "https://www.youtube.com/playlist?list="+pid]
    try:
        result=subprocess.run(cmd, capture_output=True, text=True, timeout=100)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tempo limite ao consultar o YouTube (100 s).") from exc
    if result.returncode:
        raise RuntimeError((result.stderr or "yt-dlp não conseguiu abrir a playlist.")[-600:])
    try:
        data=json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError("YouTube retornou metadados inválidos.") from exc
    items=[]
    for raw in data.get("entries",[]):
        if not isinstance(raw,dict):
            continue
        v=raw.get("id") or ""
        if not VID.fullmatch(str(v)):
            continue
        items.append({
            "id":str(v),
            "title":raw.get("title") or ("Vídeo "+str(len(items)+1)),
            "thumbnail":f"https://i.ytimg.com/vi/{v}/hqdefault.jpg",
            "duration":raw.get("duration"),
        })
    if not items:
        raise RuntimeError("Playlist vazia, privada ou indisponível. Mixes automáticos RD podem não funcionar.")
    result={
       "title":data.get("title") or f"Playlist {pid}",
       "description":data.get("description") or "Vídeos do YouTube organizados como episódios.",
       "items":items,
       "thumbnail":items[0]["thumbnail"]
    }
    with _lock:
        _cache[pid]=(time.time(),result)
    return result


# Extract an expiring playable URL on demand. YouTube may reject datacenter traffic.
def playable_url(video_id):
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings",
           "--no-check-certificates", "-f",
           "best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none][vcodec!=none]",
           "--get-url", "https://www.youtube.com/watch?v=" + video_id]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    except subprocess.TimeoutExpired:
        print("yt-dlp: timed out resolving video", video_id, flush=True)
        return None
    if result.returncode != 0:
        print("yt-dlp: video extraction failed", video_id,
              (result.stderr or "")[-400:], flush=True)
        return None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("https://"):
            return line
    return None

def meta_preview(pid, info):
    return {"id":media_id(pid),"type":"series","name":info["title"],
            "poster":info["thumbnail"],"posterShape":"landscape",
            "description":f'{len(info["items"])} vídeos, na ordem da playlist.'}

def metadata(pid, info):
    obj=meta_preview(pid,info)
    obj["description"]=info["description"][:1200]
    obj["videos"]=[
      {"id":f'{PREFIX}{pid}:{i}:{v["id"]}',"title":v["title"],
       "season":1,"episode":i,"released":"2020-01-01T00:00:00.000Z",
       "thumbnail":v["thumbnail"],
       **({"overview": f'Duração aproximada: {int(v["duration"])} segundos'} if isinstance(v.get("duration"),(float,int)) else {})
      }
      for i,v in enumerate(info["items"],start=1)
    ]
    return obj

def response(resource,typ,ident,extra):
    if typ!="series":
        return {"metas":[] } if resource=="catalog" else {"streams":[]}
    if resource=="catalog":
        if ident not in ("yt", "youtube-playlist-search"):
            return {"metas":[]}
        pid=playlist_id(extra.get("search",[""])[0])
        if not pid: return {"metas":[]}
        return {"metas":[meta_preview(pid,playlist(pid))]}
    if resource=="meta":
        if not ident.startswith(PREFIX): return {"meta":None}
        pid=ident[len(PREFIX):]
        if not PID.fullmatch(pid): return {"meta":None}
        return {"meta":metadata(pid,playlist(pid))}
    if resource=="stream":
        # e.g. ypl:PLAYLIST_ID:1:VIDEO_ID
        m=re.fullmatch(r"ypl:([A-Za-z0-9_-]{10,80}):(\d+):([A-Za-z0-9_-]{11})",ident)
        if not m: return {"streams":[]}
        pid, num, vid=m.groups()
        info=playlist(pid)
        index=int(num)-1
        if index<0 or index>=len(info["items"]) or info["items"][index]["id"]!=vid:
            return {"streams":[]}
        streams=[]
        streams.extend([
          {"name":"YouTube (player integrado)","ytId":vid,
           "behaviorHints":{"bingeGroup":"youtube-playlists-youtube"}},
          {"name":"Abrir no YouTube (navegador)",
           "externalUrl":"https://www.youtube.com/watch?v="+vid}
        ])
        return {"streams":streams}
    return {}


app = Flask(__name__)

@app.after_request
def headers(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Cache-Control"] = "no-store"
    return r

@app.route("/manifest.json", methods=["GET", "HEAD"])
def manifest():
    # Keep the exact 219-byte JSON of the accepted Discord Test A.
    body = json.dumps(MANIFEST, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return Response(body, content_type="application/json; charset=utf-8")

@app.get("/")
@app.get("/health")
def health():
    return jsonify(status="ok", addon=MANIFEST["name"])

@app.get("/<resource>/<typ>/<path:rest>.json")
def stremio_route(resource, typ, rest):
    if resource not in ("catalog", "meta", "stream"):
        return jsonify(error="Rota desconhecida"), 404
    ident, slash, raw_extra = rest.partition("/")
    extras = {}
    if slash:
        for part in raw_extra.split("&"):
            k, eq, val = part.partition("=")
            if eq:
                extras.setdefault(unquote(k), []).append(unquote(val))
    try:
        return jsonify(response(resource, typ, unquote(ident), extras))
    except RuntimeError as e:
        print("Erro:", e, flush=True)
        return jsonify(error=str(e)), 502
    except Exception as e:
        print("Erro inesperado:", repr(e), flush=True)
        return jsonify(error="Erro interno"), 500

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)
