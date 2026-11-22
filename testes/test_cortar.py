import re, sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import comum as c
import cortar as k


def test_titulo_curto_uma_linha():
    assert k.quebrar_titulo("ele caiu") == ["ELE CAIU"]


def test_titulo_longo_duas_linhas_equilibradas():
    l = k.quebrar_titulo("Bistecone não comprou o GTA 6 no lançamento kkkkk")
    assert len(l) == 2
    a, b = (k.largura(x, k.TAM_TITULO) for x in l)
    assert abs(a - b) < 250 and max(a, b) <= k.LARG_MAX


def test_agrupa_ate_3_palavras_e_quebra_na_pausa():
    p = [{"t": 0, "f": .2, "w": "um"}, {"t": .3, "f": .5, "w": "dois"}, {"t": .6, "f": .8, "w": "três"},
         {"t": .9, "f": 1.0, "w": "quatro"}, {"t": 3.0, "f": 3.2, "w": "cinco"}]
    g = k.agrupar_palavras(p)
    assert [len(x) for x in g] == [3, 1, 1]


def _posicoes(ass):
    return [(int(x), int(y)) for x, y in re.findall(r"\\pos\((\d+),(\d+)\)", ass)]


def test_ass_tudo_dentro_da_area_segura():
    pal = [{"t": 10 + i * .4, "f": 10 + i * .4 + .3, "w": f"palavra{i}"} for i in range(12)]
    ass = k.gerar_ass("Ele não acreditou no que viu no GTA 6 kkkk", pal, 10.0, 8.0)
    for x, y in _posicoes(ass):
        assert c.AREA_X0 <= x <= c.AREA_X1 and c.AREA_Y0 <= y <= c.AREA_Y1


def test_ass_tarja_sobre_a_divisao_e_destaque_amarelo():
    pal = [{"t": 1.0, "f": 1.3, "w": "não"}, {"t": 1.4, "f": 1.8, "w": "acredito"}]
    ass = k.gerar_ass("teste", pal, 0.0, 5.0)
    caixa = re.search(r"Caixa,,0,0,0,,\{\\an7\\pos\((\d+),(\d+)\)\\p1\}m 0 0 l (\d+) 0 l \d+ (\d+)", ass)
    x0, y0, bw, bh = map(int, caixa.groups())
    assert y0 < c.DIVISAO < y0 + bh
    assert abs((x0 + bw / 2) - 500) <= 1
    assert k.CORES["amarelo"] in ass and "ACREDITO" in ass


def test_ass_sem_legenda():
    ass = k.gerar_ass("teste", [{"t": 1, "f": 2, "w": "oi"}], 0.0, 5.0, legenda=False)
    assert "Legenda,," not in ass.split("[Events]")[1]


def test_recorte_proporcao_cabe_e_e_par():
    x, y, w, h = k.recorte_proporcao((100, 50, 640, 360), 1080 / 730)
    assert x >= 100 and y >= 50 and x + w <= 740 and y + h <= 410
    assert w % 2 == 0 and h % 2 == 0
    assert abs(w / h - 1080 / 730) < 0.02


def test_sem_rosto_nao_acha_camera():
    q = np.full((720, 1280, 3), 90, np.uint8)
    assert k.achar_camera([q] * 4) is None


def test_divide_cenas_na_troca_de_layout():
    a = np.full((36, 64), 30, np.uint8)
    b = np.full((36, 64), 200, np.uint8)
    assert k.dividir_cenas([a] * 6 + [b] * 6, passo=0.5) == [0, 6]


def test_troca_rapida_demais_nao_vira_cena():
    a = np.full((36, 64), 30, np.uint8)
    b = np.full((36, 64), 200, np.uint8)
    assert k.dividir_cenas([a] * 6 + [b] + [a] * 6, passo=0.5) == [0, 6]


def test_filtro_janela_tem_linha_e_cheia_nao():
    janela = {"modo": "janela", "rect": (1500, 700, 400, 300), "ini": 0, "fim": 5}
    cheia = {"modo": "cheia", "rect": (900, 300, 200, 200), "ini": 0, "fim": 5}
    assert "drawbox" in k.filtro_cena(janela, 1920, 1080)
    f = k.filtro_cena(cheia, 1920, 1080)
    assert "drawbox" not in f and "scale=1080:1920" in f


def test_recorte_no_rosto_mantem_rosto_visivel():
    rect = (0, 0, 1920, 1080)
    rosto = (1700, 100, 100, 100)
    x, y, w, h = k.recorte_no_rosto(rect, rosto, 1080 / 730)
    assert x <= 1700 and x + w >= 1800 and y <= 100 and y + h >= 200


CAM = (800, 300, 125, 85)      # câmera do streamer no canto
JOGO = (240, 110, 300, 200)    # rosto de personagem do jogo, no meio


def _cena(ini, fim, modo, rect):
    return {"ini": ini, "fim": fim, "modo": modo, "rect": rect, "rosto": rect and (rect[0] + 10, rect[1] + 10, int(rect[2] * 0.4), int(rect[3] * 0.5)),
            "_q": []}


def test_camera_dominante_e_a_que_aparece_mais_tempo():
    cenas = [_cena(0, 4.5, "janela", JOGO), _cena(4.5, 43, "janela", CAM)]
    assert k.camera_dominante(cenas, 43)["rect"] == CAM


def test_sem_posicao_dominante_nao_mexe(monkeypatch):
    cenas = [_cena(0, 10, "jogo", None), _cena(10, 12, "janela", JOGO)]
    assert k.camera_dominante(cenas, 12) is None


def test_rosto_do_jogo_vira_camera_do_streamer(monkeypatch):
    # nos primeiros segundos o personagem do jogo foi confundido com a câmera,
    # mas a câmera do streamer continuava no canto
    monkeypatch.setattr(k, "rosto_dentro", lambda q, r: True)
    cenas = [_cena(0, 4.5, "janela", JOGO), _cena(4.5, 40, "janela", (790, 296, 130, 90)),
             _cena(40, 52, "janela", CAM)]
    k.fixar_camera(cenas, 52)
    assert all(cn["modo"] == "janela" and cn["rect"] == (790, 296, 130, 90) for cn in cenas)


def test_rosto_do_jogo_sem_camera_vira_so_jogo(monkeypatch):
    # streamer escondeu a câmera: nada no canto, então não usa o personagem como câmera
    monkeypatch.setattr(k, "rosto_dentro", lambda q, r: False)
    cenas = [_cena(0, 5, "janela", JOGO), _cena(5, 50, "janela", CAM), _cena(50, 52, "cheia", (100, 50, 300, 300))]
    k.fixar_camera(cenas, 52)
    assert cenas[0]["modo"] == "jogo" and cenas[1]["rect"] == CAM and cenas[2]["modo"] == "cheia"


def test_selfie_do_jogo_com_camera_no_canto_usa_a_camera(monkeypatch):
    monkeypatch.setattr(k, "rosto_dentro", lambda q, r: True)
    cenas = [_cena(0, 24, "janela", CAM), _cena(24, 34, "cheia", (410, 130, 360, 492))]
    k.fixar_camera(cenas, 34)
    assert cenas[1]["modo"] == "janela" and cenas[1]["rect"] == CAM


def test_camera_que_mudou_de_lugar_continua_sendo_camera(monkeypatch):
    # anúncio na tela empurrou a câmera para outro canto, com rosto do mesmo tamanho
    monkeypatch.setattr(k, "rosto_dentro", lambda q, r: False)
    outra = (600, 250, 120, 80)
    cenas = [_cena(0, 16, "janela", outra), _cena(16, 40, "janela", CAM)]
    k.fixar_camera(cenas, 40)
    assert cenas[0]["modo"] == "janela" and cenas[0]["rect"] == outra
