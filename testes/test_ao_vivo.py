import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ao_vivo as av


def _alimentar(det, segundos, db=-35.0, picos=(), chat=0):
    achados = []
    for i in range(segundos):
        det.adicionar(db + (15 if det.t in picos else 0), chat)
        if det.t % 10 == 0:
            r = det.avaliar()
            if r:
                achados.append(r[0])
    return achados


def test_dispara_no_pico():
    det = av.Detector()
    achados = _alimentar(det, 400, picos={200})
    assert len(achados) == 1 and abs(achados[0] - 200) <= 1


def test_silencio_nao_dispara():
    assert _alimentar(av.Detector(), 600) == []


def test_intervalo_minimo_entre_momentos():
    det = av.Detector(intervalo=120)
    achados = _alimentar(det, 700, picos={200, 250, 300, 500})
    assert all(b - a >= 120 for a, b in zip(achados, achados[1:]))
    assert achados == [200, 500]  # 250 e 300 caem dentro do intervalo e são descartados


def test_nao_dispara_no_aquecimento():
    assert _alimentar(av.Detector(aquecimento=60), 100, picos={20}) == []


def test_chat_acelerado_dispara():
    det = av.Detector()
    for i in range(300):
        det.adicionar(-35.0, 1.0)
    for i in range(10):
        det.adicionar(-35.0, 20.0)
    assert det.avaliar() is not None


def test_limpeza_dos_pedacos():
    ped = [("a", 0, 60), ("b", 60, 120), ("c", 900, 960)]
    assert av.pedacos_para_apagar(ped, agora=1000, guarda=900) == [("a", 0, 60)]


def test_pedacos_da_janela():
    ped = [("a", 0, 60), ("b", 60, 120), ("c", 120, 180)]
    assert [p[0] for p in av.pedacos_da_janela(ped, 50, 130)] == ["a", "b", "c"]
    assert [p[0] for p in av.pedacos_da_janela(ped, 61, 119)] == ["b"]
