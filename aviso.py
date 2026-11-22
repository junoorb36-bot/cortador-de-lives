"""Toca um "plim" curto avisando que a tarefa de cortes terminou.

Uso: python aviso.py
Windows usa winsound; Mac usa afplay; Linux tenta paplay/aplay. Se não houver saída de som, não faz nada.
"""
import io
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

TAXA = 44100


def plim():
    """Duas notas subindo (Mi, depois Si), com ataque suave e cauda curta. Retorna bytes WAV."""
    partes = []
    for freq, dur in ((659.25, 0.16), (987.77, 0.42)):
        t = np.arange(int(TAXA * dur)) / TAXA
        env = np.minimum(1, t / 0.01) * np.exp(-t * 6)
        onda = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
        partes.append(onda * env)
    s = np.concatenate(partes)
    s = (s / np.abs(s).max() * 0.6 * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(s.tobytes())
    return buf.getvalue()


def tocar():
    dados = plim()
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(dados, winsound.SND_MEMORY)
            return
        arq = Path(tempfile.gettempdir()) / "cortador-plim.wav"
        arq.write_bytes(dados)
        for cmd in (["afplay"], ["paplay"], ["aplay", "-q"]):
            try:
                subprocess.run(cmd + [str(arq)], check=True, timeout=10, capture_output=True)
                return
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
    except Exception:
        pass  # sem som não é erro: o aviso é só conforto


if __name__ == "__main__":
    tocar()
