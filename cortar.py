"""Monta os cortes verticais a partir das escolhas do Claude.

Uso: python cortar.py <pasta> [--so 2]       (--so: refaz só um corte)
Lê sinais.json, candidatos.json e escolhas.json. Grava cortes/corte-NN.mp4 e resultado.json.
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c

ALT_JOGO = c.H - c.DIVISAO          # 1190
TAM_TITULO, TAM_LEGENDA = 74, 86
LARG_MAX = c.AREA_X1 - c.AREA_X0    # 880
CORES = {  # ASS usa BGR
    "amarelo": "&H0000F0FF&", "verde": "&H0040FF40&", "vermelho": "&H003030FF&",
    "laranja": "&H00337FFF&", "azul": "&H00FFB040&", "rosa": "&H00B469FF&", "branco": "&H00FFFFFF&",
}
COR_TARJA = "&H001E1EE0&"   # vermelho #E01E1E em BGR


# ---------- texto ----------

def _fonte(tam):
    from PIL import ImageFont
    return ImageFont.truetype(str(c.FONTES / "Bangers-Regular.ttf"), tam)


def largura(texto, tam):
    return _fonte(tam).getlength(texto)


def quebrar_titulo(texto, tam=TAM_TITULO, larg=LARG_MAX - 60):
    """Caixa alta, no máximo 2 linhas, quebra que deixa as linhas mais parecidas."""
    t = " ".join(texto.upper().split())
    if largura(t, tam) <= larg:
        return [t]
    pal = t.split()
    melhor = None
    for i in range(1, len(pal)):
        a, b = " ".join(pal[:i]), " ".join(pal[i:])
        la, lb = largura(a, tam), largura(b, tam)
        nota = max(la, lb)
        if melhor is None or nota < melhor[0]:
            melhor = (nota, [a, b])
    return melhor[1]


def agrupar_palavras(palavras, max_pal=3, pausa=0.45):
    """Grupos de até 3 palavras; quebra em pausa ou pontuação."""
    grupos, atual = [], []
    for i, p in enumerate(palavras):
        if atual and (len(atual) >= max_pal or p["t"] - atual[-1]["f"] > pausa):
            grupos.append(atual)
            atual = []
        atual.append(p)
        if p["w"][-1:] in ".?!,":
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    return grupos


def _ts(s):
    s = max(0.0, s)
    h, r = divmod(s, 3600)
    m, r = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{r:05.2f}"


def _limpa(w):
    return w.replace("{", "").replace("}", "").replace("\\", "").upper()


def gerar_ass(titulo, palavras, inicio, duracao, legenda=True, cor="amarelo"):
    """Legenda .ass: tarja vermelha do título sobre a divisão + legenda palavra por palavra."""
    cx = c.centro_seguro()
    linhas = quebrar_titulo(titulo)
    alt_linha = int(TAM_TITULO * 1.02)
    larg_txt = max(largura(l, TAM_TITULO) for l in linhas)
    bw = int(min(LARG_MAX, larg_txt + 56))
    bh = alt_linha * len(linhas) + 26
    x0, y0, bw, bh = c.caixa_segura(cx - bw // 2, c.DIVISAO - bh // 2, bw, bh)
    fim = _ts(duracao + 1)
    ev = []
    caixa = f"m 0 0 l {bw} 0 l {bw} {bh} l 0 {bh}"
    ev.append(f"Dialogue: 0,0:00:00.00,{fim},Caixa,,0,0,0,,{{\\an7\\pos({x0},{y0})\\p1}}{caixa}{{\\p0}}")
    ty = y0 + bh // 2
    texto = "\\N".join(_limpa(l) for l in linhas)
    ev.append(f"Dialogue: 1,0:00:00.00,{fim},Titulo,,0,0,0,,{{\\an5\\pos({x0 + bw // 2},{ty})}}{texto}")

    if legenda and palavras:
        destaque = CORES.get(cor, cor if cor.startswith("&H") else CORES["amarelo"])
        ly = y0 + bh + 40 + TAM_LEGENDA // 2
        ly = min(ly, c.AREA_Y1 - TAM_LEGENDA)
        rel = [{**p, "t": p["t"] - inicio, "f": p["f"] - inicio} for p in palavras]
        rel = [p for p in rel if p["f"] > 0 and p["t"] < duracao]
        grupos = agrupar_palavras(rel)
        for gi, g in enumerate(grupos):
            fim_g = grupos[gi + 1][0]["t"] if gi + 1 < len(grupos) else g[-1]["f"] + 0.4
            fim_g = min(fim_g, g[-1]["f"] + 0.8, duracao)
            for wi, p in enumerate(g):
                t1 = p["t"] if wi else g[0]["t"]
                t2 = g[wi + 1]["t"] if wi + 1 < len(g) else fim_g
                if t2 <= t1:
                    continue
                partes = []
                for wj, q in enumerate(g):
                    w = _limpa(q["w"])
                    partes.append(f"{{\\c{destaque}}}{w}{{\\c&H00FFFFFF&}}" if wj == wi else w)
                pop = "\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)" if wi == 0 else ""
                ev.append(f"Dialogue: 2,{_ts(t1)},{_ts(t2)},Legenda,,0,0,0,,"
                          f"{{\\an5\\pos({cx},{ly}){pop}}}{' '.join(partes)}")

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {c.W}
PlayResY: {c.H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caixa,Arial,10,{COR_TARJA},&H000000FF&,&H00000000&,&H00000000&,0,0,0,0,100,100,0,0,1,3,0,7,0,0,0,1
Style: Titulo,{c.FONTE_NOME},{TAM_TITULO},&H00FFFFFF&,&H000000FF&,&H00000000&,&H00000000&,0,0,0,0,100,100,1,0,1,5,0,5,0,0,0,1
Style: Legenda,{c.FONTE_NOME},{TAM_LEGENDA},&H00FFFFFF&,&H000000FF&,&H00000000&,&H80000000&,0,0,0,0,100,100,1,0,1,7,2,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n"


# ---------- câmera ----------

def _maior_borda(perfil, lo, hi, prefer):
    """Índice de maior borda em perfil[lo:hi]."""
    lo, hi = max(0, lo), min(len(perfil), hi)
    if hi - lo < 3:
        return None, 0
    seg = perfil[lo:hi]
    i = int(np.argmax(seg))
    return lo + i, float(seg[i])


_DET = {}


def _detector(w, h):
    import cv2
    if (w, h) not in _DET:
        _DET[(w, h)] = cv2.FaceDetectorYN.create(str(c.PASTA_SKILL / "modelos" / "face_yunet.onnx"), "", (w, h), 0.75)
    return _DET[(w, h)]


def rosto_vivo(quadros, mov_min=1.5):
    """Rosto estável que SE MEXE (câmera de verdade). Rosto parado = arte do jogo, ignora."""
    import cv2
    hq, wq = quadros[0].shape[:2]
    det = _detector(wq, hq)
    rostos = []
    for q in quadros:
        _, fs = det.detect(q)
        if fs is not None and len(fs):
            fs = [f[:4] for f in fs if f[3] > hq / 30]
            if fs:
                rostos.append(max(fs, key=lambda r: r[2] * r[3]))
    if len(rostos) < max(1, len(quadros) // 3):
        return None
    fx, fy, fw, fh = np.median(np.array(rostos), axis=0).astype(int)
    fx, fy = max(0, fx), max(0, fy)
    if len(quadros) >= 2:
        gs = [cv2.cvtColor(q[fy:fy + fh, fx:fx + fw], cv2.COLOR_BGR2GRAY).astype(np.float32) for q in quadros]
        mov = np.median([np.abs(a - b).mean() for a, b in zip(gs, gs[1:])])
        if mov < mov_min:
            return None
    return int(fx), int(fy), int(fw), int(fh)


def achar_camera(quadros):
    """Como montar uma cena: None (só jogo), ("cheia", rosto) ou ("janela", retângulo da câmera)."""
    import cv2
    r = rosto_vivo(quadros)
    if r is None:
        return None
    fx, fy, fw, fh = r
    hq, wq = quadros[0].shape[:2]
    if fw > wq * 0.12:  # rosto grande: a cena é só câmera
        return ("cheia", r, r)

    # bordas retas da janela da câmera (mediana de vários quadros some com o que se mexe)
    g = np.median(np.stack([cv2.cvtColor(q, cv2.COLOR_BGR2GRAY) for q in quadros]), axis=0).astype(np.float32)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    ya, yb = max(0, fy - fh), min(hq, fy + 2 * fh)
    xa, xb = max(0, fx - fw), min(wq, fx + 2 * fw)
    col = gx[ya:yb].mean(axis=0)
    lin = gy[:, xa:xb].mean(axis=1)
    lim = max(np.percentile(col, 99), np.percentile(lin, 99)) * 0.6
    esq, se = _maior_borda(col, fx - 5 * fw, fx - fw // 3, 0)
    dir_, sd = _maior_borda(col, fx + fw + fw // 3, fx + 6 * fw, 0)
    cima, sc = _maior_borda(lin, fy - 4 * fh, fy - fh // 3, 0)
    baixo, sb = _maior_borda(lin, fy + fh + fh // 2, fy + 6 * fh, 0)
    bx0 = esq if esq is not None and se > lim else (0 if fx < 4 * fw else None)
    bx1 = dir_ if dir_ is not None and sd > lim else (wq if wq - (fx + fw) < 4 * fw else None)
    by0 = cima if cima is not None and sc > lim else (0 if fy < 3 * fh else None)
    by1 = baixo if baixo is not None and sb > lim else (hq if hq - (fy + fh) < 5 * fh else None)
    if None in (bx0, bx1, by0, by1) or (bx1 - bx0) < 2 * fw or (by1 - by0) < 2 * fh:
        w = int(fw * 4.2)
        h = int(w / (c.W / c.DIVISAO))
        x = int(fx + fw / 2 - w / 2)
        y = int(fy + fh / 2 - h * 0.45)
        x, y = max(0, min(x, wq - w)), max(0, min(y, hq - h))
        return ("janela", (x, y, min(w, wq), min(h, hq)), r)
    jan = (int(bx0) + 2, int(by0) + 2, int(bx1 - bx0) - 4, int(by1 - by0) - 4)
    prop = jan[2] / max(1, jan[3])
    if not (0.8 <= prop <= 2.6) or jan[2] * jan[3] > 0.4 * wq * hq or jan[2] > 7 * fw:
        w = int(fw * 4.2)
        h = int(w / (c.W / c.DIVISAO))
        x = max(0, min(int(fx + fw / 2 - w / 2), wq - w))
        y = max(0, min(int(fy + fh / 2 - h * 0.45), hq - h))
        jan = (x, y, min(w, wq), min(h, hq))
    return ("janela", jan, r)


def dividir_cenas(pequenos, passo, limiar=28.0, minimo=1.5):
    """Índices onde a imagem muda de cena (troca de layout), a partir de quadros pequenos em cinza."""
    cortes = [0]
    for i in range(1, len(pequenos)):
        d = np.abs(pequenos[i].astype(np.float32) - pequenos[i - 1].astype(np.float32)).mean()
        if d > limiar and (i - cortes[-1]) * passo >= minimo:
            cortes.append(i)
    return cortes


def recorte_proporcao(rect, proporcao, foco=(0.5, 0.45)):
    """Maior recorte com a proporção pedida dentro do retângulo, centrado no foco."""
    x, y, w, h = rect
    if w / h > proporcao:
        nw, nh = int(h * proporcao), h
    else:
        nw, nh = w, int(w / proporcao)
    nx = x + int((w - nw) * foco[0])
    ny = y + int((h - nh) * foco[1])
    return (nx // 2 * 2, ny // 2 * 2, nw // 2 * 2, nh // 2 * 2)


def recorte_no_rosto(rect, rosto, proporcao):
    """Maior recorte com a proporção dentro de rect, com o rosto no centro (um pouco acima do meio)."""
    x, y, w, h = recorte_proporcao(rect, proporcao, (0.5, 0.35))
    if not rosto:
        return x, y, w, h
    rx, ry, rw, rh = rosto
    X0, Y0, W0, H0 = rect
    nx = int(rx + rw / 2 - w / 2)
    ny = int(ry + rh / 2 - h * 0.42)
    nx = max(X0, min(nx, X0 + W0 - w))
    ny = max(Y0, min(ny, Y0 + H0 - h))
    return nx // 2 * 2, ny // 2 * 2, w, h


def recorte_jogo(wq, hq, foco="centro", cam=None):
    prop = c.W / ALT_JOGO
    fx = {"esquerda": 0.0, "centro": 0.5, "direita": 1.0}.get(foco, 0.5)
    return recorte_proporcao((0, 0, wq, hq), prop, (fx, 0.5))


# ---------- vídeo ----------

def baixar_trecho(url, ini, fim, destino):
    if destino.exists():
        return destino
    cmd = c.ytdlp() + ["-q", "--no-warnings", "--no-playlist",
                       "-f", "bv*[height<=1080][vcodec^=avc1]+ba/bv*[height<=1080]+ba/b",
                       "--download-sections", f"*{ini:.2f}-{fim:.2f}", "--force-keyframes-at-cuts",
                       "--merge-output-format", "mp4", "-o", str(destino), url]
    for tentativa in range(3):  # falha de rede passageira: tenta de novo
        try:
            c.rodar(cmd)
            return destino
        except RuntimeError:
            for resto in destino.parent.glob(destino.stem + "*"):
                resto.unlink(missing_ok=True)
            if tentativa == 2:
                raise
            time.sleep(5)
    return destino


def analisar_cenas(video, ss, dur, passo=0.5, larg=960):
    """Lista de cenas [{ini, fim, modo, rect}] com tempos relativos ao começo do corte."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    wq = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hq = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    esc = larg / wq
    quadros, peq = [], []
    t = 0.0
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, (ss + t) * 1000)
        ok, q = cap.read()
        if not ok:
            break
        q = cv2.resize(q, (larg, int(hq * esc)))
        quadros.append(q)
        peq.append(cv2.resize(cv2.cvtColor(q, cv2.COLOR_BGR2GRAY), (64, 36)))
        t += passo
    cap.release()
    if not quadros:
        raise RuntimeError("Não consegui ler o vídeo do trecho.")
    idx = dividir_cenas(peq, passo) + [len(quadros)]
    cenas = []
    for a, b in zip(idx, idx[1:]):
        sel = quadros[a:b]
        if len(sel) > 8:
            sel = [sel[int(i * len(sel) / 8)] for i in range(8)]
        cam = achar_camera(sel)
        modo, rect, rosto = ("jogo", None, None) if cam is None else cam
        cenas.append({"ini": a * passo, "fim": min(dur, b * passo), "modo": modo, "rect": rect, "rosto": rosto,
                      "_q": sel})
    fixar_camera(cenas, dur)
    for cn in cenas:
        cn.pop("_q", None)
        if cn["rect"] is not None:
            cn["rect"] = tuple(int(v / esc) for v in cn["rect"])
            cn["rosto"] = tuple(int(v / esc) for v in cn["rosto"])
    juntas = [cenas[0]]
    for cn in cenas[1:]:
        if cn["modo"] == juntas[-1]["modo"] and (cn["modo"] == "jogo" or _parecido(cn["rect"], juntas[-1]["rect"])):
            juntas[-1]["fim"] = cn["fim"]
        else:
            juntas.append(cn)
    juntas[-1]["fim"] = dur
    return juntas, wq, hq


def camera_dominante(cenas, dur, minimo=0.4):
    """Janela da câmera que mais tempo aparece no corte. A câmera do streamer fica parada no mesmo
    canto; rosto em outro lugar é personagem do jogo. None se nenhuma posição domina o corte."""
    grupos = []
    for cn in cenas:
        if cn["modo"] != "janela":
            continue
        d = cn["fim"] - cn["ini"]
        for g in grupos:
            if _parecido(g["rect"], cn["rect"]):
                g["dur"] += d
                if d > g["maior"]:
                    g.update(rect=cn["rect"], rosto=cn["rosto"], maior=d)
                break
        else:
            grupos.append({"rect": cn["rect"], "rosto": cn["rosto"], "dur": d, "maior": d})
    if not grupos:
        return None
    g = max(grupos, key=lambda g: g["dur"])
    return g if g["dur"] >= minimo * dur else None


def rosto_dentro(quadros, rect, fracao=0.25):
    """Há um rosto (qualquer um, não só o maior) dentro de rect em parte dos quadros?"""
    hq, wq = quadros[0].shape[:2]
    det = _detector(wq, hq)
    x, y, w, h = rect
    achou = 0
    for q in quadros:
        _, fs = det.detect(q)
        if fs is None:
            continue
        if any(x <= f[0] + f[2] / 2 <= x + w and y <= f[1] + f[3] / 2 <= y + h for f in fs):
            achou += 1
    return achou >= max(1, int(len(quadros) * fracao))


def fixar_camera(cenas, dur):
    """Usa sempre a mesma janela de câmera do streamer: troca rostos do jogo confundidos com a câmera
    e acaba com pequenos pulos de enquadramento entre cenas. Muda `cenas` no lugar."""
    dom = camera_dominante(cenas, dur)
    if dom is None:
        return
    for cn in cenas:
        # "cheia" pode ser o streamer em tela cheia (fica) ou um close de personagem/selfie do jogo
        # com a câmera ainda no canto (vira a câmera de sempre)
        if cn["modo"] == "janela" and _parecido(cn["rect"], dom["rect"]) or rosto_dentro(cn["_q"], dom["rect"]):
            cn.update(modo="janela", rect=dom["rect"], rosto=dom["rosto"])
        elif cn["modo"] == "janela" and cn["rosto"][2] > 2 * dom["rosto"][2]:
            # rosto bem maior que o do streamer, fora do canto de sempre: close de personagem do jogo
            cn.update(modo="jogo", rect=None, rosto=None)
        # rosto de tamanho parecido em outro lugar: a câmera mudou de posição (ex.: anúncio na tela); mantém


def _parecido(r1, r2, tol=0.25):
    if not r1 or not r2:
        return False
    return all(abs(a - b) <= tol * max(r1[2], r1[3]) for a, b in zip(r1, r2))


def filtro_cena(cena, wq, hq, foco_jogo="centro", cor_linha="E01E1E", i=0):
    """Filtro ffmpeg que transforma a cena no vertical 1080x1920."""
    fx = {"esquerda": 0.0, "centro": 0.5, "direita": 1.0}.get(foco_jogo, 0.5)
    if cena["modo"] == "janela":
        cx, cy, cw, ch = recorte_no_rosto(cena["rect"], cena.get("rosto"), c.W / c.DIVISAO)
        jx, jy, jw, jh = recorte_jogo(wq, hq, foco_jogo)
        return (f"split[a{i}][b{i}];"
                f"[a{i}]crop={cw}:{ch}:{cx}:{cy},scale={c.W}:{c.DIVISAO}:flags=lanczos,setsar=1[x{i}];"
                f"[b{i}]crop={jw}:{jh}:{jx}:{jy},scale={c.W}:{ALT_JOGO}:flags=lanczos,setsar=1[y{i}];"
                f"[x{i}][y{i}]vstack,drawbox=x=0:y={c.DIVISAO - 3}:w={c.W}:h=6:color=0x{cor_linha}:t=fill")
    if cena["modo"] == "cheia":
        rx, ry, rw, rh = cena["rect"]
        nw = int(hq * c.W / c.H) // 2 * 2
        fx = min(1.0, max(0.0, (rx + rw / 2 - nw / 2) / max(1, wq - nw)))
    x, y, w, h = recorte_proporcao((0, 0, wq, hq), c.W / c.H, (fx, 0.5))
    return f"crop={w}:{h}:{x}:{y},scale={c.W}:{c.H}:flags=lanczos,setsar=1"


def montar(trecho, ass, saida, cenas, wq, hq, cwd, ss=0.0, dur=None, foco_jogo="centro"):
    n = len(cenas)
    partes = [f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)) if n > 1 else "[0:v]null[s0]"]
    for i, cn in enumerate(cenas):
        partes.append(f"[s{i}]trim=start={cn['ini']:.3f}:end={cn['fim']:.3f},setpts=PTS-STARTPTS,"
                      f"{filtro_cena(cn, wq, hq, foco_jogo, i=i)}[c{i}]")
    partes.append("".join(f"[c{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps={c.FPS},"
                  f"ass={ass}:fontsdir=.fontes[v]")
    filtro = ";".join(partes)
    cmd = ["ffmpeg", "-loglevel", "error", "-y"]
    if ss:
        cmd += ["-ss", f"{ss:.2f}"]
    cmd += ["-i", str(trecho)]
    if dur:
        cmd += ["-t", f"{dur:.2f}"]
    cmd += ["-filter_complex", filtro, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])


def capa(video, jpg, t):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=360:-1", str(jpg)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--so", type=int)
    a = ap.parse_args()
    t0 = time.time()
    pasta = Path(a.pasta)
    sinais = c.ler_json(pasta / "sinais.json")
    cands = {x["id"]: x for x in c.ler_json(pasta / "candidatos.json")}
    esc = c.ler_json(pasta / "escolhas.json")
    estilo = esc.get("estilo", {})
    (pasta / "cortes").mkdir(exist_ok=True)
    (pasta / "trechos").mkdir(exist_ok=True)
    fontes = pasta / ".fontes"
    fontes.mkdir(exist_ok=True)
    shutil.copy(c.FONTES / "Bangers-Regular.ttf", fontes / "Bangers-Regular.ttf")

    res_arq = pasta / "resultado.json"
    resultado = {r["n"]: r for r in (c.ler_json(res_arq) if res_arq.exists() else [])}
    for n, corte in enumerate(esc["cortes"], 1):
        if a.so and n != a.so:
            continue
        cand = cands[corte["id"]]
        ini, fim = float(corte["inicio"]), float(corte["fim"])
        dur = fim - ini
        print(f"Corte {n}: {corte['titulo']} ({dur:.0f} s)", flush=True)
        if sinais.get("fonte") == "local":
            trecho, ss = Path(cand["arquivo"]), ini - cand["arquivo_ini"]
        else:
            trecho = baixar_trecho(sinais["url"], ini, fim, pasta / "trechos" / f"trecho-{corte['id']:02d}-{int(ini)}-{int(fim)}.mp4")
            ss = 0.0
        cenas, wq, hq = analisar_cenas(trecho, ss, dur)
        modos = {cn["modo"] for cn in cenas}
        aviso = None if modos & {"janela", "cheia"} else "Não achei a câmera do streamer: usei o jogo em tela cheia."
        trocas = estilo.get("trocas", {})
        palavras = [{**p, "w": trocas.get(p["w"], p["w"])} for p in cand["palavras"] if p["f"] > ini and p["t"] < fim]
        ass_txt = gerar_ass(corte["titulo"], palavras, ini, dur, estilo.get("legenda", True), estilo.get("cor", "amarelo"))
        ass_rel = f"cortes/corte-{n:02d}.ass"
        (pasta / ass_rel).write_text(ass_txt, encoding="utf-8")
        saida = pasta / "cortes" / f"corte-{n:02d}.mp4"
        montar(trecho, ass_rel, saida, cenas, wq, hq, cwd=pasta, ss=ss, dur=dur,
               foco_jogo=estilo.get("foco_jogo", "centro"))
        capa(saida, pasta / "cortes" / f"corte-{n:02d}.jpg", min(dur / 3, 4))
        resultado[n] = {"n": n, **corte, "duracao": round(dur, 1), "video": f"cortes/corte-{n:02d}.mp4",
                        "capa": f"cortes/corte-{n:02d}.jpg", "cenas": cenas, "aviso": aviso}
        # salva a cada corte: se um corte posterior falhar, os anteriores continuam no painel
        c.salvar_json(res_arq, [resultado[k] for k in sorted(resultado)])
    c.salvar_json(res_arq, [resultado[k] for k in sorted(resultado)])
    sinais = c.ler_json(pasta / "sinais.json")
    sinais["tempo_cortes"] = round(time.time() - t0)
    c.salvar_json(pasta / "sinais.json", sinais)
    print(f"Pronto: {len(esc['cortes'])} cortes em {pasta / 'cortes'}")


if __name__ == "__main__":
    main()
