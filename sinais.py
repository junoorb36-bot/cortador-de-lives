"""Live já encerrada: baixa áudio e chat, acha os picos e transcreve em volta deles.

Uso: python sinais.py <link> <pasta-de-saida> [--n 30] [--modelo small]
Gera na pasta: sinais.json, candidatos.json e candidatos.txt (para o Claude ler).
"""
import argparse
import json
import math
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c

TAXA = 16000
ANTES, DEPOIS = 50, 25  # janela de transcrição em volta do pico (segundos)


# ---------- cálculo (testável) ----------

def volume_db(amostras, taxa=TAXA):
    """Volume (dBFS, RMS) de cada segundo inteiro."""
    n = len(amostras) // taxa
    if n == 0:
        return np.zeros(0)
    a = amostras[: n * taxa].astype(np.float32).reshape(n, taxa)
    if amostras.dtype == np.int16:
        a /= 32768.0
    rms = np.sqrt(np.mean(a * a, axis=1)) + 1e-9
    return 20 * np.log10(rms)


def volume_de_wav(caminho, bloco_seg=600):
    """Lê o wav aos poucos (live de horas não cabe inteira na memória)."""
    partes = []
    with wave.open(str(caminho), "rb") as w:
        assert w.getframerate() == TAXA and w.getnchannels() == 1
        while True:
            raw = w.readframes(TAXA * bloco_seg)
            if not raw:
                break
            partes.append(volume_db(np.frombuffer(raw, dtype=np.int16)))
    return np.concatenate(partes) if partes else np.zeros(0)


def linha_de_base(v, janela=300):
    """Mediana móvel aproximada (blocos de 30 s), mesmo tamanho de v."""
    if len(v) == 0:
        return v
    b = 30
    nb = math.ceil(len(v) / b)
    meds = np.array([np.median(v[i * b:(i + 1) * b]) for i in range(nb)])
    k = max(1, janela // b // 2)
    suave = np.array([np.median(meds[max(0, i - k): i + k + 1]) for i in range(nb)])
    return np.repeat(suave, b)[: len(v)]


def ler_chat_youtube(caminho, duracao):
    """Mensagens por segundo a partir do .live_chat.json do yt-dlp (uma ação por linha)."""
    cont = np.zeros(int(duracao) + 1)
    for linha in Path(caminho).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        r = d.get("replayChatItemAction", {})
        ms = r.get("videoOffsetTimeMsec")
        if ms is None:
            continue
        for a in r.get("actions", []):
            if "addChatItemAction" in a:
                s = int(int(ms) / 1000)
                if 0 <= s < len(cont):
                    cont[s] += 1
    return cont


def velocidade_chat(cont, janela=10):
    """Velocidade do chat em cada segundo, relativa à mediana da live (1.0 = normal)."""
    if cont is None or cont.sum() == 0:
        return None
    k = np.ones(janela)
    taxa = np.convolve(cont, k, mode="same")
    base = np.median(taxa[taxa > 0]) if (taxa > 0).any() else 1.0
    return taxa / max(base, 1.0)


PISO_DB = -50.0  # abaixo disso é silêncio (áudio mutado da Twitch, intervalo)


def pontuar(vol, chat_x=None):
    """Força de cada segundo: dB acima da linha de base + bônus de chat acelerado.

    Silêncio absoluto não entra na linha de base (senão a volta do som parece um grito de +140 dB).
    """
    v = np.maximum(vol, PISO_DB)
    som = v > PISO_DB + 1
    ref = np.where(som, v, np.median(v[som]) if som.any() else PISO_DB)
    exc = np.where(som, v - linha_de_base(ref), 0.0)
    # pico de 3 s: um grito curto conta
    viz = np.maximum.reduce([exc, np.roll(exc, 1), np.roll(exc, -1)])
    forca = (exc + viz) / 2  # o segundo do pico vence os vizinhos
    if chat_x is not None:
        n = min(len(forca), len(chat_x))
        forca = forca[:n] + 4 * np.log2(np.maximum(chat_x[:n], 1.0))
    return forca


def achar_picos(forca, n=30, distancia=90, minimo=4.0, margem=ANTES):
    """Os n segundos mais fortes, a pelo menos `distancia` s um do outro."""
    ordem = np.argsort(forca)[::-1]
    escolhidos = []
    for s in ordem:
        if forca[s] < minimo or len(escolhidos) >= n:
            break
        if s < 10:
            continue
        if all(abs(s - e) >= distancia for e in escolhidos):
            escolhidos.append(int(s))
    return sorted(escolhidos)


def texto_candidato(cand):
    """Bloco legível: palavras agrupadas em frases com o tempo de início."""
    linhas, atual, ini, ult = [], [], None, None
    for p in cand["palavras"]:
        if atual and (p["t"] - ult > 0.7 or len(atual) >= 14):
            linhas.append(f"  [{ini:9.1f}] {' '.join(atual)}")
            atual = []
        if not atual:
            ini = p["t"]
        atual.append(p["w"])
        ult = p["f"]
    if atual:
        linhas.append(f"  [{ini:9.1f}] {' '.join(atual)}")
    chat = f" · chat {cand['chat_x']:.1f}x" if cand.get("chat_x") is not None else ""
    cab = (f"### #{cand['id']} · pico em {c.hms(cand['pico'])} ({cand['pico']:.0f} s) · "
           f"volume +{cand['volume_db']:.1f} dB{chat}")
    return cab + "\n" + ("\n".join(linhas) if linhas else "  (sem fala)")


# ---------- etapas com rede/disco ----------

def baixar_audio(url, pasta):
    wav = pasta / "audio.wav"
    if wav.exists():
        return wav
    c.rodar(c.ytdlp() + ["-q", "--no-warnings", "-f", "ba/b", "-N", "8", "--no-playlist",
                         "-o", str(pasta / "audio_orig.%(ext)s"), url])
    orig = next(pasta.glob("audio_orig.*"))
    c.rodar(["ffmpeg", "-loglevel", "error", "-y", "-i", str(orig), "-ac", "1", "-ar", str(TAXA),
             "-c:a", "pcm_s16le", str(wav)])
    orig.unlink()
    return wav


def baixar_chat(url, pasta, info):
    if info["plataforma"] != "youtube":
        return None
    try:
        c.rodar(c.ytdlp() + ["-q", "--no-warnings", "--skip-download", "--write-subs",
                             "--sub-langs", "live_chat", "-o", str(pasta / "chat"), url], timeout=900)
    except Exception:
        return None
    arq = next(pasta.glob("chat*.live_chat.json"), None)
    return arq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("pasta")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--modelo", default="small")
    a = ap.parse_args()

    t0 = time.time()
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    print("1/4 Lendo o link...", flush=True)
    info = c.info_link(a.url)
    if info["ao_vivo"]:
        print("ESSA LIVE ESTÁ NO AR. Use o modo ao vivo (ao_vivo.py).")
        sys.exit(2)

    print(f"2/4 Baixando só o áudio de \"{info['titulo']}\" ({c.hms(info['duracao'])})...", flush=True)
    wav = baixar_audio(a.url, pasta)
    chat_arq = baixar_chat(a.url, pasta, info)
    t_down = time.time() - t0

    print("3/4 Medindo volume e chat...", flush=True)
    vol = volume_de_wav(wav)
    chat_x = None
    if chat_arq:
        chat_x = velocidade_chat(ler_chat_youtube(chat_arq, len(vol)))
    forca = pontuar(vol, chat_x)
    picos = achar_picos(forca, n=a.n)
    vv = np.maximum(vol, PISO_DB)
    base = linha_de_base(np.where(vv > PISO_DB + 1, vv, np.median(vv[vv > PISO_DB + 1]) if (vv > PISO_DB + 1).any() else PISO_DB))
    n_altos = int((forca >= 4.0).sum())

    print(f"4/4 Ouvindo em volta de {len(picos)} momentos...", flush=True)
    model = c.carregar_whisper(a.modelo)
    cands = []
    with wave.open(str(wav), "rb") as w:
        total = w.getnframes()
        for i, p in enumerate(picos, 1):
            ini = max(0, p - ANTES)
            fim = min(total / TAXA, p + DEPOIS)
            w.setpos(int(ini * TAXA))
            amos = np.frombuffer(w.readframes(int((fim - ini) * TAXA)), dtype=np.int16).astype(np.float32) / 32768
            pal = c.transcrever(model, amos, offset=ini)
            cands.append({
                "id": i, "pico": float(p), "janela": [float(ini), float(fim)],
                "volume_db": float(max(vol[p], PISO_DB) - base[p]),
                "chat_x": float(chat_x[p]) if chat_x is not None and p < len(chat_x) else None,
                "palavras": pal,
            })
            print(f"   {i}/{len(picos)}", end="\r", flush=True)

    c.salvar_json(pasta / "candidatos.json", cands)
    resumo = {
        "url": a.url, "titulo": info["titulo"], "canal": info["canal"], "duracao": info["duracao"],
        "plataforma": info["plataforma"], "fonte": "url", "tem_chat": chat_x is not None,
        "momentos_altos": n_altos, "analisados": len(cands),
        "tempo_download": round(t_down), "tempo_sinais": round(time.time() - t0),
    }
    c.salvar_json(pasta / "sinais.json", resumo)
    cab = (f"LIVE: {info['titulo']} · {info['canal']} · {c.hms(info['duracao'])}\n"
           f"Chat: {'sim' if chat_x is not None else 'não disponível (só volume e fala)'}\n"
           f"Tempos entre colchetes são segundos desde o início da live.\n\n")
    (pasta / "candidatos.txt").write_text(cab + "\n\n".join(texto_candidato(x) for x in cands), encoding="utf-8")
    print(f"\nPronto em {c.hms(time.time() - t0)}. {n_altos} segundos de volume alto, "
          f"{len(cands)} momentos para avaliar. Leia {pasta / 'candidatos.txt'}")


if __name__ == "__main__":
    main()
