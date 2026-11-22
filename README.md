# Cortador de Lives

Skill do Claude Code que corta lives (YouTube, Twitch e Kick) em clipes verticais prontos para TikTok, Reels e Shorts. O clipe sai com a câmera do streamer em cima, o jogo embaixo, uma tarja com o título e legenda animada.

Você não precisa programar. Basta mandar o link para o Claude Code e pedir: **"corta essa live"**.

Feito pelo canal [Não Codei](https://naocodei.com), que ensina Claude Code para quem não é programador.

## O que ela faz

- **Live encerrada:** baixa só o áudio, acha os momentos mais fortes, monta os cortes e abre um painel com vídeo, nota, título e texto do post de cada um.
- **Live acontecendo (modo ao vivo):** acompanha a transmissão e entrega um corte novo sempre que acontece um momento bom.
- **Ajustes por conversa:** "deixa a legenda verde", "muda o título do corte 2", "começa 2 segundos antes".
- Toca um aviso sonoro quando termina.

Tudo roda no seu computador. **Não usa API paga:** quem decide os cortes é o próprio Claude, dentro da sua assinatura do Claude Code.

## Como ela escolhe os cortes

1. **O computador ouve a live inteira.** Ele mede o volume em comparação com o normal do próprio streamer e a velocidade do chat em comparação com o normal da live. Grito somado a chat acelerado gera um pico.
2. **O computador filtra.** Ficam os 30 picos mais fortes, com pelo menos 90 segundos de distância entre eles. Ele transcreve a fala de 50 segundos antes até 25 segundos depois de cada pico.
3. **O Claude lê e dá nota de 0 a 100.** O momento funciona para quem nunca viu a live? Começa no início da ideia? Tem desfecho? Barulho sem reação, cena do jogo e leitura de doação ficam de fora.
4. **Nota 60 ou mais vira corte** de 20 a 60 segundos. Por padrão saem os 3 melhores, mas você pode pedir outra quantidade.

## Instalação

Você precisa do [Claude Code](https://claude.com/claude-code) e do Python 3.10 ou mais novo.

O jeito mais fácil é pedir ao próprio Claude Code:

> instala a skill https://github.com/junoorb36-bot/cortador-de-lives

Se preferir fazer à mão, clone o repositório na pasta de skills:

- **Windows:** `git clone https://github.com/junoorb36-bot/cortador-de-lives "%USERPROFILE%\.claude\skills\cortador-de-lives"`
- **Mac/Linux:** `git clone https://github.com/junoorb36-bot/cortador-de-lives ~/.claude/skills/cortador-de-lives`

Depois, no Claude Code, diga **"prepara o cortador de lives"**. A skill instala o que falta: ffmpeg, yt-dlp, faster-whisper, OpenCV, a fonte da tarja e o detector de rostos.

## Como usar

- "corta essa live: <link>"
- "faz 10 cortes dessa live: <link>"
- "acompanha essa live: <link>" (modo ao vivo) e depois "para de acompanhar"

Os cortes ficam na pasta `Cortes/` de onde você abriu o Claude Code.

## Limites

- Lives privadas, só para membros ou com restrição de idade não funcionam.
- Sem chat (Kick ou lives antigas da Twitch), ela usa só volume e fala.
- Se a câmera do streamer não aparece na transmissão, o corte sai com o jogo em tela cheia.
- Feita e testada no Windows.

## Antes de postar

Só poste cortes de streamers que permitem. Para monetizar no YouTube, acrescente comentário ou narração sua: corte puro, sem nada seu, não entra na monetização.

## Créditos

- Transcrição: [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Download: [yt-dlp](https://github.com/yt-dlp/yt-dlp) e [ffmpeg](https://ffmpeg.org)
- Detector de rostos: [YuNet, do OpenCV Zoo](https://github.com/opencv/opencv_zoo) (baixado na instalação)
- Fonte da tarja: [Bangers](https://fonts.google.com/specimen/Bangers), licença OFL (baixada na instalação)

Licença MIT.
