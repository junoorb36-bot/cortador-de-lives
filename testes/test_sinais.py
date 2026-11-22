import json, sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import sinais as s


def test_volume_por_segundo_e_alto_maior_que_baixo():
    taxa = 16000
    baixo = (np.random.default_rng(0).standard_normal(taxa) * 300).astype(np.int16)
    alto = (np.random.default_rng(1).standard_normal(taxa) * 8000).astype(np.int16)
    v = s.volume_db(np.concatenate([baixo, alto, baixo]), taxa)
    assert len(v) == 3 and v[1] > v[0] + 20


def _live_sintetica(picos, dur=3600):
    rng = np.random.default_rng(2)
    v = -35 + rng.standard_normal(dur) * 1.0
    for p in picos:
        v[p] += 15
    return v


def test_acha_os_picos_certos():
    v = _live_sintetica([500, 1500, 3000])
    picos = s.achar_picos(s.pontuar(v), n=3)
    assert picos == [500, 1500, 3000]


def test_picos_respeitam_distancia():
    v = _live_sintetica([1000, 1030, 1060, 2000])
    picos = s.achar_picos(s.pontuar(v), n=10, distancia=90)
    assert all(b - a >= 90 for a, b in zip(picos, picos[1:]))
    assert 2000 in picos


def test_sem_pico_nao_inventa():
    v = _live_sintetica([])
    assert s.achar_picos(s.pontuar(v), n=5, minimo=6.0) == []


def test_chat_acelerado_vira_bonus():
    v = _live_sintetica([])
    cont = np.ones(3600)
    cont[2000:2010] = 30
    forca = s.pontuar(v, s.velocidade_chat(cont))
    assert int(np.argmax(forca)) in range(1995, 2015)


def test_ler_chat_youtube(tmp_path):
    linhas = [
        {"replayChatItemAction": {"videoOffsetTimeMsec": "12500", "actions": [{"addChatItemAction": {}}]}},
        {"replayChatItemAction": {"videoOffsetTimeMsec": "12900", "actions": [{"addChatItemAction": {}}, {"addChatItemAction": {}}]}},
        {"replayChatItemAction": {"videoOffsetTimeMsec": "30000", "actions": [{"addLiveChatTickerItemAction": {}}]}},
    ]
    arq = tmp_path / "chat.live_chat.json"
    arq.write_text("\n".join(json.dumps(l) for l in linhas), encoding="utf-8")
    cont = s.ler_chat_youtube(arq, 60)
    assert cont[12] == 3 and cont[30] == 0


def test_texto_candidato():
    cand = {"id": 2, "pico": 125.0, "volume_db": 9.5, "chat_x": None,
            "palavras": [{"t": 100.0, "f": 100.3, "w": "não"}, {"t": 100.4, "f": 100.8, "w": "acredito"},
                         {"t": 103.0, "f": 103.4, "w": "olha"}]}
    txt = s.texto_candidato(cand)
    assert "#2" in txt and "2:05" in txt
    assert "[    100.0] não acredito" in txt and "[    103.0] olha" in txt


def test_silencio_mutado_nao_vira_pico_gigante():
    v = _live_sintetica([2500])
    v[1000:1300] = -180.0  # trecho mutado
    forca = s.pontuar(v)
    assert forca.max() < 30
    assert 2500 in s.achar_picos(forca, n=1)
