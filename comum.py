"""Constantes e utilidades compartilhadas do cortador de lives."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PASTA_SKILL = Path(__file__).resolve().parent
FONTES = PASTA_SKILL / "fontes"
FONTE_NOME = "Bangers"

# Vertical 9:16
W, H = 1080, 1920
FPS = 30
DIVISAO = 730  # altura da faixa da câmera (38%)

# Margens cobertas pela interface (soma de TikTok, Reels e Shorts)
MARGEM_TOPO, MARGEM_BASE, MARGEM_DIR, MARGEM_ESQ = 260, 480, 140, 60
AREA_X0, AREA_X1 = MARGEM_ESQ, W - MARGEM_DIR          # 60 .. 940
AREA_Y0, AREA_Y1 = MARGEM_TOPO, H - MARGEM_BASE        # 260 .. 1440


def centro_seguro():
    """Centro horizontal da área segura (não o centro da tela)."""
    return (AREA_X0 + AREA_X1) // 2


def caixa_segura(x, y, w, h):
    """Empurra a caixa para dentro da área segura. Encolhe se não couber."""
    w = min(w, AREA_X1 - AREA_X0)
    h = min(h, AREA_Y1 - AREA_Y0)
    x = max(AREA_X0, min(x, AREA_X1 - w))
    y = max(AREA_Y0, min(y, AREA_Y1 - h))
    return x, y, w, h


def ytdlp():
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def rodar(cmd, **kw):
    """Roda um comando e devolve stdout; levanta erro com a mensagem do programa."""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise RuntimeError(f"Falhou: {' '.join(map(str, cmd[:3]))}...\n{r.stderr[-1500:]}")
    return r.stdout


def plataforma(url):
    u = url.lower()
    if "twitch.tv" in u:
        return "twitch"
    if "kick.com" in u:
        return "kick"
    if "youtu" in u:
        return "youtube"
    return "outra"


def info_link(url):
    """Título, duração e se está ao vivo, usando yt-dlp."""
    out = rodar(ytdlp() + ["-J", "--no-warnings", "--no-playlist", url])
    d = json.loads(out)
    ao_vivo = bool(d.get("is_live")) or d.get("live_status") == "is_live"
    return {
        "url": url,
        "id": d.get("id"),
        "titulo": d.get("title") or d.get("id"),
        "canal": d.get("uploader") or d.get("channel") or "",
        "duracao": d.get("duration") or 0,
        "ao_vivo": ao_vivo,
        "plataforma": plataforma(url),
        "tem_chat": "live_chat" in (d.get("subtitles") or {}),
    }


def nome_pasta(titulo):
    s = re.sub(r"[^\w\s-]", "", titulo, flags=re.UNICODE).strip()
    s = re.sub(r"\s+", "-", s)[:60].strip("-")
    return s or "live"


def hms(seg):
    seg = int(seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def salvar_json(caminho, dados):
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def carregar_whisper(modelo="small"):
    from faster_whisper import WhisperModel
    n = max(1, (os.cpu_count() or 4) - 2)
    return WhisperModel(modelo, device="auto", compute_type="int8", cpu_threads=n)


def transcrever(model, wav, offset=0.0, clip=None):
    """Lista de palavras [{t, f, w}] com tempos absolutos (somando offset)."""
    kw = dict(language="pt", word_timestamps=True, vad_filter=True, beam_size=1)
    if clip:
        kw["clip_timestamps"] = clip
    segs, _ = model.transcribe(str(wav) if isinstance(wav, (str, Path)) else wav, **kw)
    pal = []
    for s in segs:
        for w in s.words or []:
            pal.append({"t": round(w.start + offset, 2), "f": round(w.end + offset, 2), "w": w.word.strip()})
    return pal
