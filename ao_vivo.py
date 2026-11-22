"""Live no ar: grava em pedaços, lê o chat, detecta picos e coloca os momentos numa fila.

Comandos:
  python ao_vivo.py gravar  <link> <pasta>      roda até existir <pasta>/PARAR (deixe em segundo plano)
  python ao_vivo.py esperar <pasta>             bloqueia até chegar um momento novo na fila e imprime o caminho
  python ao_vivo.py janela  <pasta> <momento>   junta os pedaços em volta do momento, transcreve e imprime o candidato
  python ao_vivo.py parar   <pasta>
"""
import json
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c
import sinais as s

TAXA = 16000
SEG = 60            # duração de cada pedaço gravado
GUARDA = 15 * 60    # quanto tempo de pedaços manter
INTERVALO = 120     # mínimo entre dois momentos
ESPERA_DESFECHO = 30
LIMITE = 6.0


# ---------- cálculo (testável) ----------

class Detector:
    """Recebe volume (1 por segundo) e contagem de chat; decide quando há um momento."""

    def __init__(self, limite=LIMITE, intervalo=INTERVALO, aquecimento=60):
        self.vol = deque(maxlen=300)
        self.chat = deque(maxlen=300)
        self.limite, self.intervalo, self.aquec = limite, intervalo, aquecimento
        self.ultimo = -1e9
        self.t = 0

    def adicionar(self, db, msgs=0):
        self.vol.append(db)
        self.chat.append(msgs)
        self.t += 1

    def avaliar(self):
        """Chame a cada 10 s. Devolve (segundo_do_pico, volume_db, chat_x) ou None."""
        if self.t < self.aquec or self.t - self.ultimo < self.intervalo:
            return None
        v = np.array(self.vol)
        base = np.median(v)
        ult = v[-10:]
        i = int(np.argmax(ult))
        exc = float(ult[i] - base)
        ch = np.array(self.chat)
        chat_x = None
        if ch.sum() > 0:
            taxa = np.convolve(ch, np.ones(10), mode="valid")
            med = max(np.median(taxa), 1.0)
            chat_x = float(ch[-10:].sum() / med)
        forca = exc + (4 * np.log2(max(chat_x, 1.0)) if chat_x else 0)
        if forca < self.limite:
            return None
        pico = self.t - 10 + i
        self.ultimo = pico
        return pico, exc, chat_x


def pedacos_para_apagar(pedacos, agora, guarda=GUARDA):
    """Pedaços (nome, ini, fim) que terminaram há mais de `guarda` segundos."""
    return [p for p in pedacos if agora - p[2] > guarda]


def pedacos_da_janela(pedacos, ini, fim):
    return [p for p in pedacos if p[2] > ini and p[1] < fim]


# ---------- chat ----------

class ChatTwitch(threading.Thread):
    daemon = True

    def __init__(self, canal):
        super().__init__()
        self.canal, self.cont, self.ok = canal.lower(), 0, False

    def run(self):
        while True:
            try:
                sk = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=30)
                sk.sendall(f"NICK justinfan{int(time.time()) % 99999}\r\nJOIN #{self.canal}\r\n".encode())
                buf = b""
                while True:
                    d = sk.recv(4096)
                    if not d:
                        break
                    buf += d
                    *linhas, buf = buf.split(b"\r\n")
                    for l in linhas:
                        if l.startswith(b"PING"):
                            sk.sendall(b"PONG :tmi.twitch.tv\r\n")
                        elif b" PRIVMSG " in l:
                            self.cont += 1
                            self.ok = True
            except OSError:
                time.sleep(5)

    def pegar(self):
        n, self.cont = self.cont, 0
        return n


class ChatYouTube:
    """yt-dlp grava o chat ao vivo num arquivo; contamos as linhas novas."""

    def __init__(self, url, pasta):
        self.arq = pasta / "chat.live_chat.json"
        self.proc = subprocess.Popen(c.ytdlp() + ["-q", "--no-warnings", "--skip-download", "--write-subs",
                                                  "--sub-langs", "live_chat", "-o", str(pasta / "chat"), url],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pos = 0
        self.ok = False

    def pegar(self):
        arqs = list(self.arq.parent.glob("chat*.live_chat.json*"))
        if not arqs:
            return 0
        a = max(arqs, key=lambda p: p.stat().st_size)
        with open(a, "rb") as f:
            f.seek(self.pos)
            d = f.read()
            self.pos += len(d)
        n = d.count(b"addChatItemAction")
        if n:
            self.ok = True
        return n


class SemChat:
    ok = False

    def pegar(self):
        return 0


# ---------- gravador ----------

def url_stream(url):
    """Endereços do vídeo e do áudio (o YouTube manda separados; a Twitch, junto)."""
    out = c.rodar(c.ytdlp() + ["-g", "--no-warnings", "-f",
                               "bv*[height<=1080]+ba/b[height<=1080]/b", url])
    return out.strip().splitlines()[:2]


def gravar(url, pasta):
    pasta = Path(pasta)
    (pasta / "pedacos").mkdir(parents=True, exist_ok=True)
    (pasta / "fila").mkdir(exist_ok=True)
    parar = pasta / "PARAR"
    parar.unlink(missing_ok=True)
    info = c.info_link(url)
    if not info["ao_vivo"]:
        print("Essa live não está no ar. Use o modo de live encerrada (sinais.py).")
        sys.exit(2)
    plat = info["plataforma"]
    chat = (ChatTwitch(url.rstrip("/").split("/")[-1]) if plat == "twitch"
            else ChatYouTube(url, pasta) if plat == "youtube" else SemChat())
    if isinstance(chat, ChatTwitch):
        chat.start()
    sin = {"url": url, "titulo": info["titulo"], "canal": info["canal"], "plataforma": plat,
           "fonte": "local", "tem_chat": False, "analisados": 0, "inicio_gravacao": time.time()}
    c.salvar_json(pasta / "sinais.json", sin)
    det = Detector()
    pedacos = []          # (arquivo, ini, fim) em segundos de gravação
    relogio = 0.0         # segundos de gravação acumulados
    sessao, n_seg = 0, 0
    pendentes = []        # (pico, exc, chat_x, quando_liberar)
    print(f"Gravando \"{info['titulo']}\". Para encerrar: python ao_vivo.py parar \"{pasta}\"", flush=True)

    while not parar.exists():
        try:
            src = url_stream(url)
        except Exception:
            if not _esperar_volta(url, parar):
                break
            continue
        sessao += 1
        lista = pasta / "pedacos" / f"lista-{sessao}.csv"
        entradas = sum((["-i", u] for u in src), [])
        aud = "1:a:0" if len(src) > 1 else "0:a:0"
        proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-y", *entradas,
             "-map", "0:v:0", "-map", aud, "-c", "copy", "-f", "segment", "-segment_time", str(SEG),
             "-reset_timestamps", "1", "-segment_list", str(lista), "-segment_list_type", "csv",
             str(pasta / "pedacos" / f"s{sessao}_%05d.ts"),
             "-map", aud, "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        base_sessao = relogio
        lidos_lista = 0
        seg_atual = 0
        while not parar.exists():
            raw = proc.stdout.read(TAXA * 2)
            if not raw or len(raw) < TAXA * 2:
                break
            db = float(s.volume_db(np.frombuffer(raw, dtype=np.int16))[0])
            seg_atual += 1
            relogio = base_sessao + seg_atual
            det.adicionar(db, 0)
            if seg_atual % 10 == 0:
                msgs = chat.pegar()
                for k in range(1, min(10, len(det.chat)) + 1):
                    det.chat[-k] = msgs / 10
                r = det.avaliar()
                if r:
                    pico = relogio - (det.t - r[0])
                    pendentes.append((pico, r[1], r[2], relogio + ESPERA_DESFECHO))
                # pedaços prontos
                if lista.exists():
                    linhas = lista.read_text().strip().splitlines()
                    for l in linhas[lidos_lista:]:
                        nome, ini, fim = l.split(",")
                        pedacos.append((str(pasta / "pedacos" / nome), base_sessao + float(ini), base_sessao + float(fim)))
                    lidos_lista = len(linhas)
                for p in pedacos_para_apagar(pedacos, relogio):
                    Path(p[0]).unlink(missing_ok=True)
                    pedacos.remove(p)
                c.salvar_json(pasta / "pedacos.json", pedacos)
                for item in list(pendentes):
                    if relogio >= item[3]:
                        pendentes.remove(item)
                        m = {"pico": item[0], "volume_db": item[1], "chat_x": item[2], "criado": time.time()}
                        c.salvar_json(pasta / "fila" / f"momento-{int(item[0]):06d}.json", m)
                        print(f"Momento em {c.hms(item[0])} (+{item[1]:.1f} dB)", flush=True)
                if chat.ok and not sin["tem_chat"]:
                    sin["tem_chat"] = True
                    c.salvar_json(pasta / "sinais.json", sin)
        proc.kill()
        if parar.exists() or not _esperar_volta(url, parar):
            break
    if isinstance(chat, ChatYouTube):
        chat.proc.kill()
    sin["encerrado"] = True
    c.salvar_json(pasta / "sinais.json", sin)
    print("Gravação encerrada.", flush=True)


def _esperar_volta(url, parar, limite=120):
    print("A live caiu. Tentando reconectar por 2 minutos...", flush=True)
    t0 = time.time()
    while time.time() - t0 < limite and not parar.exists():
        try:
            if c.info_link(url)["ao_vivo"]:
                return True
        except Exception:
            pass
        time.sleep(15)
    return False


# ---------- comandos para o Claude ----------

def esperar(pasta):
    pasta = Path(pasta)
    feitos = pasta / "fila" / "feitos.txt"
    vistos = set(feitos.read_text().split()) if feitos.exists() else set()
    for _ in range(60):
        if (pasta / "sinais.json").exists():
            break
        time.sleep(2)
    (pasta / "fila").mkdir(parents=True, exist_ok=True)
    while True:
        for m in sorted((pasta / "fila").glob("momento-*.json")):
            if m.name not in vistos:
                with open(feitos, "a") as f:
                    f.write(m.name + "\n")
                print(m)
                return
        sin = c.ler_json(pasta / "sinais.json")
        if (pasta / "PARAR").exists() or sin.get("encerrado"):
            print("ENCERRADO")
            return
        time.sleep(5)


def janela(pasta, momento):
    pasta = Path(pasta)
    m = c.ler_json(momento)
    ini, fim = max(0.0, m["pico"] - s.ANTES), m["pico"] + s.DEPOIS
    for _ in range(60):  # espera os pedaços do fim da janela ficarem prontos
        pedacos = c.ler_json(pasta / "pedacos.json")
        if pedacos and pedacos[-1][2] >= fim:
            break
        time.sleep(5)
    sel = pedacos_da_janela(pedacos, ini, fim)
    if not sel:
        print("Os pedaços desse momento já foram apagados ou ainda não existem.")
        sys.exit(1)
    (pasta / "janelas").mkdir(exist_ok=True)
    arq = pasta / "janelas" / f"janela-{int(m['pico']):06d}.ts"
    lista = arq.with_suffix(".txt")
    lista.write_text("".join(f"file '{Path(p[0]).as_posix()}'\n" for p in sel))
    c.rodar(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(arq)])
    arq_ini = sel[0][1]
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(arq), "-ac", "1", "-ar", str(TAXA),
                          "-f", "s16le", "pipe:1"], capture_output=True).stdout
    amos = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    model = c.carregar_whisper()
    pal = c.transcrever(model, amos, offset=arq_ini)
    pal = [p for p in pal if ini - 5 <= p["t"] <= fim + 5]
    cands_arq = pasta / "candidatos.json"
    cands = c.ler_json(cands_arq) if cands_arq.exists() else []
    cand = {"id": len(cands) + 1, "pico": m["pico"], "janela": [ini, fim], "volume_db": m["volume_db"],
            "chat_x": m["chat_x"], "palavras": pal, "arquivo": str(arq), "arquivo_ini": arq_ini}
    cands.append(cand)
    c.salvar_json(cands_arq, cands)
    sin = c.ler_json(pasta / "sinais.json")
    sin["analisados"] = len(cands)
    c.salvar_json(pasta / "sinais.json", sin)
    print(s.texto_candidato(cand))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "gravar":
        gravar(sys.argv[2], sys.argv[3])
    elif cmd == "esperar":
        esperar(sys.argv[2])
    elif cmd == "janela":
        janela(sys.argv[2], sys.argv[3])
    elif cmd == "parar":
        Path(sys.argv[2], "PARAR").touch()
        print("Pedido de parada enviado.")


if __name__ == "__main__":
    main()
