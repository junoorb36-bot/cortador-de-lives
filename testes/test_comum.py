import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import comum as c


def test_centro_seguro_nao_e_centro_da_tela():
    assert c.centro_seguro() == 500


def test_caixa_dentro_fica_igual():
    assert c.caixa_segura(100, 300, 200, 100) == (100, 300, 200, 100)


def test_caixa_empurrada_para_dentro():
    x, y, w, h = c.caixa_segura(950, 1800, 200, 100)
    assert x + w <= 940 and y + h <= 1440 and x >= 60 and y >= 260


def test_caixa_grande_demais_encolhe():
    x, y, w, h = c.caixa_segura(0, 0, 2000, 3000)
    assert (x, y, w, h) == (60, 260, 880, 1180)


def test_plataforma():
    assert c.plataforma("https://www.twitch.tv/videos/1") == "twitch"
    assert c.plataforma("https://youtu.be/x") == "youtube"
    assert c.plataforma("https://kick.com/x") == "kick"


def test_hms():
    assert c.hms(3725) == "1:02:05"
    assert c.hms(65) == "1:05"
