"""Confere e instala o que o cortador de lives precisa. Uso: python instalar.py"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import importlib.util
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
FONTE = PASTA / "fontes" / "Bangers-Regular.ttf"
FONTE_URL = "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf"
ROSTO = PASTA / "modelos" / "face_yunet.onnx"
ROSTO_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

PACOTES = {"faster_whisper": "faster-whisper", "cv2": "opencv-python-headless", "PIL": "pillow",
           "numpy": "numpy", "yt_dlp": "yt-dlp"}


def ok(msg):
    print(f"  [ok] {msg}")


def main():
    faltou = []
    print("Conferindo o cortador de lives...")
    falta_pip = [pip for mod, pip in PACOTES.items() if importlib.util.find_spec(mod) is None]
    if falta_pip:
        print(f"  instalando: {', '.join(falta_pip)} (pode levar alguns minutos)")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", *falta_pip])
        if r.returncode != 0:
            faltou.append("pacotes Python: " + ", ".join(falta_pip))
    else:
        ok("pacotes Python")

    if shutil.which("ffmpeg"):
        ok("ffmpeg")
    else:
        if sys.platform == "win32" and shutil.which("winget"):
            print("  instalando ffmpeg pelo winget...")
            subprocess.run(["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                            "--accept-source-agreements", "--accept-package-agreements"])
            faltou.append("ffmpeg instalado: FECHE e ABRA o Claude Code de novo para ele aparecer")
        elif sys.platform == "darwin" and shutil.which("brew"):
            subprocess.run(["brew", "install", "ffmpeg"])
        else:
            faltou.append("ffmpeg (instale em https://ffmpeg.org/download.html)")

    if not FONTE.exists():
        FONTE.parent.mkdir(exist_ok=True)
        try:
            urllib.request.urlretrieve(FONTE_URL, FONTE)
            ok("fonte Bangers baixada")
        except Exception as e:
            faltou.append(f"fonte Bangers ({e})")
    else:
        ok("fonte Bangers")

    if not ROSTO.exists():
        ROSTO.parent.mkdir(exist_ok=True)
        try:
            urllib.request.urlretrieve(ROSTO_URL, ROSTO)
            ok("detector de rosto baixado")
        except Exception as e:
            faltou.append(f"detector de rosto ({e})")
    else:
        ok("detector de rosto")

    if faltou:
        print("\nPENDENTE:")
        for f in faltou:
            print("  -", f)
        sys.exit(1)
    print("\nTudo pronto. Na primeira transcrição o modelo de fala (~500 MB) é baixado uma vez.")


if __name__ == "__main__":
    main()
