---
name: cortador-de-lives
description: Corta lives (YouTube, Twitch, Kick) e podcasts em clipes verticais prontos para TikTok, Reels e Shorts, com a câmera do streamer em cima, o jogo embaixo, tarja de título e legenda animada. Funciona com a live acontecendo (modo ao vivo) ou já encerrada. Use quando o usuário disser "corta essa live", "corta esta live", "clipa essa live", "faz cortes dessa live", "acompanha essa live", "prepara o cortador de lives", ou mandar um link de live pedindo cortes/clipes.
---

# Cortador de Lives

Você (Claude) assiste a live pela pessoa: o computador faz o trabalho braçal (baixar, medir volume e chat, transcrever, montar o vídeo) e **você decide** quais momentos viram corte, onde começa e termina cada um, e escreve título e post. Tudo local, sem API paga.

Os scripts ficam na pasta desta skill. Abaixo, `SK` = caminho desta pasta (a mesma do SKILL.md). Rode sempre com `python "SK/arquivo.py"`.

Fale com a pessoa em português simples. Ela provavelmente não programa: não mostre comandos nem erros crus, explique o que está acontecendo.

## 0. Preparar (primeira vez, ou se algo faltar)
Frase: "prepara o cortador de lives". Rode `python "SK/instalar.py"`. Se ele pedir para fechar e abrir o Claude Code (ffmpeg recém-instalado), avise a pessoa.

## 1. Descobrir o modo
Pasta de saída: `Cortes/<nome-curto-da-live>` dentro da pasta onde o Claude foi aberto (crie se não existir).
Descubra se a live está no ar:
```
python -c "import sys; sys.path.insert(0, r'SK'); import comum, json; print(json.dumps(comum.info_link('<link>'), ensure_ascii=False))"
```
`ao_vivo: true` → **modo ao vivo** (seção 3). Senão → **live encerrada** (seção 2).

## 2. Live encerrada
1. `python "SK/sinais.py" "<link>" "<pasta>"` (rode em segundo plano; ~4 min para 4 h de live). Ele baixa só o áudio, mede volume e chat, e transcreve em volta dos ~30 momentos mais fortes.
2. Leia `<pasta>/candidatos.txt` **inteiro**. Cada momento tem o minuto, o volume acima do normal, a velocidade do chat (quando existe) e a fala com o tempo em segundos entre colchetes.
3. Dê nota de 0 a 100 a cada momento (critérios na seção 4) e escreva `<pasta>/escolhas.json` com os melhores (padrão: 3 cortes com nota ≥ 60; a pessoa pode pedir "quero 5 cortes" ou "só nota acima de 70"). Para acertar início e fim exatos, consulte os tempos de cada palavra em `candidatos.json` (campo `palavras`: `t` início, `f` fim).
4. `python "SK/cortar.py" "<pasta>"` (~30 s por corte).
5. `python "SK/painel.py" "<pasta>" --abrir`.
6. Confira 1 quadro de cada corte antes de entregar (`ffmpeg -ss 3 -i corte-01.mp4 -frames:v 1 x.jpg` e leia a imagem): câmera no lugar, nada estranho. Se a câmera saiu errada, refaça só aquele com `--so N` depois de ajustar.
7. Entregue: quantos cortes, a nota e o motivo de cada um, onde estão os arquivos, e o tempo total.
8. **Aviso sonoro:** logo antes de escrever a entrega, rode `python "SK/aviso.py"` (toca um "plim" para a pessoa saber que terminou).

## 3. Modo ao vivo
1. Inicie o gravador **em segundo plano** (fica rodando até parar):
   `python "SK/ao_vivo.py" gravar "<link>" "<pasta>"`
2. Em seguida, também em segundo plano: `python "SK/ao_vivo.py" esperar "<pasta>"`. Ele termina quando chega um momento novo e imprime o caminho do arquivo do momento (ou `ENCERRADO`).
3. Quando o `esperar` terminar com um momento:
   - `python "SK/ao_vivo.py" janela "<pasta>" "<arquivo-do-momento>"` → imprime a fala em volta do pico, no mesmo formato da seção 2.
   - Dê a nota. Se ≥ 60 (ou o limite pedido), **acrescente** o corte em `escolhas.json` (crie com `{"estilo": {}, "cortes": []}` se não existir) e rode `python "SK/cortar.py" "<pasta>" --so <número do corte na lista>` e depois `python "SK/painel.py" "<pasta>"` (o painel se atualiza sozinho a cada 20 s; abra com `--abrir` só no primeiro corte).
   - Rode `python "SK/aviso.py"` e avise a pessoa numa linha: "Corte novo: <título> (nota X)". Se a nota for baixa, só registre e siga.
   - Rode o `esperar` de novo. Repita.
4. "para de acompanhar" → `python "SK/ao_vivo.py" parar "<pasta>"`. Mostre o resumo.
O gravador guarda só os últimos 15 minutos de vídeo; um momento precisa ser cortado antes disso.

## 4. Como dar a nota (seja duro)
- **Funciona para quem nunca viu a live?** Se precisa de contexto para entender, nota baixa.
- **Começa no início da ideia?** Nunca comece no meio de uma frase ou de uma piada. Comece na pergunta, no anúncio, na leitura da mensagem do chat que provocou a reação.
- **Tem desfecho?** Grito, risada, susto, resposta engraçada, revelação. Sem desfecho, nota baixa.
- **Barulho não é momento:** volume alto de alerta, música ou efeito sonoro sem reação do streamer não conta.
- **Fala de personagem do jogo não é o streamer.** Cutscenes e diálogos do jogo (geralmente em inglês) aparecem na transcrição como um português estranho, formal ou sem sentido ("Yo! Então, o que agora? Vamos fazer o que você tem que fazer"). Ignore esses trechos; o que vale é a reação do streamer, que fala gíria brasileira ("mano", "velho", "caralho").
- Leitura de doação/agradecimento, "deixa o like", recado de bastidor = fora, a não ser que a mensagem em si seja a piada.
- Duração de **20 a 60 s**. Comece ~0,3 s antes da primeira palavra e termine ~0,5 s depois da última.
- 90+: viraliza fácil. 75–89: muito bom. 60–74: bom. Abaixo de 60: não corta.

## 5. escolhas.json
```json
{"estilo": {"legenda": true, "cor": "amarelo", "foco_jogo": "centro", "trocas": {"GT6": "GTA 6"}},
 "cortes": [{"id": 19, "inicio": 8686.4, "fim": 8719.4, "nota": 86,
   "motivo": "Uma frase dizendo por que esse momento é bom.",
   "titulo": "A HORA QUE O GTA 6 LIBEROU NA LIVE",
   "post": "Texto curto do post, com 1 ou 2 emojis e uma pergunta para comentar.",
   "hashtags": ["#gta6", "#cortes"]}]}
```
- `id` = número do momento em `candidatos.txt`. `inicio`/`fim` em segundos da live.
- **Título da tarja**: caixa alta, até ~45 caracteres, tom de canal de corte brasileiro (fofoca, surpresa, "KKKK" permitido), sem clickbait mentiroso. Cite o streamer quando ajudar.
- `trocas`: corrige erros da transcrição na legenda (nomes de jogos, gírias, nome do streamer).

## 6. Ajustes por frase (refaça com `cortar.py`, não precisa baixar de novo)
Ao terminar qualquer ajuste, rode `python "SK/aviso.py"` antes de responder.
- "deixa a legenda verde/amarela/…" → `estilo.cor` (amarelo, verde, vermelho, laranja, azul, rosa, branco).
- "sem legenda" → `estilo.legenda: false`.
- "foca no lado esquerdo/direito do jogo" → `estilo.foco_jogo`.
- "muda o título do corte 2" → edite e rode `--so 2`.
- "começa 2 segundos antes" → ajuste `inicio` e rode `--so N`.
Título e legenda ficam sempre dentro da área segura do vertical (margens de TikTok, Reels e Shorts); o código já garante isso.

## 7. Quando algo dá errado
- Live privada, só para membros, com login ou bloqueio de idade: explique que a ferramenta não consegue acessar e pare.
- Sem chat (Kick, live antiga da Twitch): segue só com volume e fala; avise no resumo.
- Nenhum momento com nota ≥ 60: mostre os 3 melhores como "fracos" e pergunte se quer cortar mesmo assim.
- A câmera não foi encontrada: o corte sai com o jogo em tela cheia e o painel avisa.

## 8. Lembrete que sempre vai na entrega
Só poste cortes de streamers que permitem. Para monetizar no YouTube, acrescente comentário ou narração sua: corte puro, sem nada seu, não entra na monetização.
