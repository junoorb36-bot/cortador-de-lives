"""Painel HTML com os cortes. Uso: python painel.py <pasta> [--abrir]"""
import argparse
import html
import json
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as c


def cartao(r):
    e = html.escape
    tags = " ".join(r.get("hashtags", []))
    post = r.get("post", "")
    nota = int(r.get("nota", 0))
    cls = "alta" if nota >= 75 else ("media" if nota >= 60 else "baixa")
    aviso = f'<p class="aviso">{e(r["aviso"])}</p>' if r.get("aviso") else ""
    return f"""
<article class="corte">
  <video src="{e(r['video'])}" poster="{e(r.get('capa', ''))}" controls preload="metadata" playsinline></video>
  <div class="info">
    <div class="topo"><span class="num">CORTE {r['n']:02d}</span>
      <span class="nota {cls}">{nota}<small>/100</small></span></div>
    <p class="motivo">{e(r.get('motivo', ''))}</p>
    <p class="meta">Na live: {c.hms(r['inicio'])} → {c.hms(r['fim'])} · {r['duracao']:.0f} s</p>
    {aviso}
    <div class="campo"><label>Título</label><div class="txt">{e(r['titulo'])}</div>
      <button data-copia="{e(r['titulo'])}">Copiar</button></div>
    <div class="campo"><label>Texto do post</label><div class="txt">{e(post)}<br><span class="tags">{e(tags)}</span></div>
      <button data-copia="{e(post + chr(10) + chr(10) + tags)}">Copiar</button></div>
    <a class="baixar" href="{e(r['video'])}" download>Baixar vídeo</a>
  </div>
</article>"""


def gerar(pasta):
    pasta = Path(pasta)
    s = c.ler_json(pasta / "sinais.json")
    res = c.ler_json(pasta / "resultado.json") if (pasta / "resultado.json").exists() else []
    ao_vivo = s.get("fonte") == "local"
    e = html.escape
    chat = "volume, fala e chat" if s.get("tem_chat") else "volume e fala (chat não disponível)"
    stats = [
        ("Live", c.hms(s.get("duracao", 0)) if s.get("duracao") else "ao vivo"),
        ("Momentos analisados", s.get("analisados", "–")),
        ("Viraram corte", len(res)),
        ("Tempo até os cortes", c.hms(s.get("tempo_sinais", 0) + s.get("tempo_cortes", 0)) if s.get("tempo_sinais") else "–"),
    ]
    st = "".join(f'<div class="stat"><b>{e(str(v))}</b><span>{e(k)}</span></div>' for k, v in stats)
    cards = "".join(cartao(r) for r in res) or '<p class="vazio">Nenhum corte ainda.</p>'
    refresh = '<meta http-equiv="refresh" content="20">' if ao_vivo and not s.get("encerrado") else ""
    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{refresh}
<title>Cortes · {e(s.get('canal') or s.get('titulo', ''))}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0c0d0f;--bg1:#15171a;--bg2:#1c1f23;--fg:#f5f7fa;--dim:#9aa3ad;--bd:#272a30;--or:#CD7F6A;--ok:#4caf50;--wa:#FFC107;--red:#E01E1E}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 Inter,system-ui,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 16px 80px}}
.tag{{font:700 12px 'JetBrains Mono',monospace;letter-spacing:.12em;color:var(--or);text-transform:uppercase}}
h1{{font-size:28px;margin:8px 0 4px;line-height:1.25}}.sub{{color:var(--dim);margin:0 0 24px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:16px}}
.stat{{background:var(--bg1);border:1px solid var(--bd);border-radius:10px;padding:14px}}
.stat b{{display:block;font:800 26px 'JetBrains Mono',monospace}}.stat span{{color:var(--dim);font-size:13px}}
.lembrete{{background:rgba(255,193,7,.08);border:1px solid rgba(255,193,7,.35);color:#f3dc98;border-radius:10px;padding:12px 14px;margin:0 0 28px;font-size:14px}}
.corte{{display:grid;grid-template-columns:270px 1fr;gap:22px;background:var(--bg1);border:1px solid var(--bd);border-radius:14px;padding:16px;margin-bottom:16px}}
video{{width:270px;aspect-ratio:9/16;border-radius:10px;background:#000}}
.topo{{display:flex;justify-content:space-between;align-items:center}}
.num{{font:700 13px 'JetBrains Mono',monospace;color:var(--dim);letter-spacing:.1em}}
.nota{{font:800 30px 'JetBrains Mono',monospace}}.nota small{{font-size:14px;color:var(--dim)}}
.nota.alta{{color:var(--ok)}}.nota.media{{color:var(--wa)}}.nota.baixa{{color:var(--dim)}}
.motivo{{font-size:16px;margin:6px 0}}.meta{{color:var(--dim);font:13px 'JetBrains Mono',monospace;margin:0 0 12px}}
.aviso{{color:var(--wa);font-size:14px}}
.campo{{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;margin:8px 0;position:relative}}
.campo label{{font:700 11px 'JetBrains Mono',monospace;color:var(--or);text-transform:uppercase;letter-spacing:.08em}}
.txt{{padding-right:80px;white-space:pre-wrap}}.tags{{color:#86b5f5}}
button{{position:absolute;top:10px;right:10px;background:var(--or);color:#111;border:0;border-radius:6px;padding:6px 12px;font:700 12px Inter;cursor:pointer}}
button.ok{{background:var(--ok)}}
.baixar{{display:inline-block;margin-top:8px;color:var(--or);font-weight:600}}
.vazio{{color:var(--dim)}}
footer{{margin-top:40px;color:#6b727b;font:12px 'JetBrains Mono',monospace}}footer a{{color:var(--or)}}
@media(max-width:700px){{.corte{{grid-template-columns:1fr}}video{{width:100%;max-width:320px;margin:0 auto;display:block}}}}
</style></head><body><div class="wrap">
<div class="tag">Cortador de Lives{' · AO VIVO' if ao_vivo and not s.get('encerrado') else ''}</div>
<h1>{e(s.get('titulo', ''))}</h1>
<p class="sub">{e(s.get('canal', ''))} · analisado por {chat}</p>
<div class="stats">{st}</div>
<div class="lembrete">Só poste cortes de streamers que permitem cortes. Para monetizar no YouTube, acrescente comentário ou narração sua: corte puro, sem nada seu, não entra na monetização.</div>
{cards}
<footer>Feito com o Cortador de Lives · skill grátis do <a href="https://naocodei.com">Não Codei</a></footer>
</div>
<script>
document.querySelectorAll('button[data-copia]').forEach(b=>b.onclick=()=>{{
  navigator.clipboard.writeText(b.dataset.copia).then(()=>{{b.textContent='Copiado';b.classList.add('ok');
  setTimeout(()=>{{b.textContent='Copiar';b.classList.remove('ok')}},1500)}})}});
</script></body></html>"""
    out = pasta / "painel.html"
    out.write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--abrir", action="store_true")
    a = ap.parse_args()
    p = gerar(a.pasta)
    print(p)
    if a.abrir:
        webbrowser.open(p.resolve().as_uri())
