# Edição — o que aprendemos com o vídeo de referência

Referência: vídeo de uma criadora sobre retenção ("você tem 3 segundos para prender a atenção").
Os pontos dela, e como cada um virou edição no Ecos da História:

| Dica dela | O que ela quer dizer | Como aplicamos |
|---|---|---|
| **3 segundos, tudo começa com um gancho** | Quem não for fisgado logo de cara arrasta para o lado. | O vídeo não abre mais com fade lento do preto. Já no 1º segundo entra a **frase da thumbnail, grande, no centro** (ex.: "1.000 ANOS / CAÍRAM EM 1 DIA"), junto com o impacto sonoro. Quem clicou pela thumbnail vê a promessa confirmada. |
| **Ganchos visuais** (texto colorido, elementos, efeito sonoro) | O olho precisa de algo para ler e ouvir além da fala. | Gancho em branco + faixa vermelha, impacto grave na abertura, **datas e anos "saltando" em dourado** no momento em que são narrados (ex.: "29 DE MAIO DE 1453"). |
| **Movimento logo na cena** | O olhar segue o que se mexe; imagem parada perde a pessoa. | Já tínhamos partículas, chama tremendo e câmera na mão. Agora cada corte também entra com um **"soco" de zoom** curto. |
| **Cada frase, um ângulo diferente** (dinamismo) | Trocar o enquadramento a cada frase gera novidade constante e segura até o fim. | Esta é a maior mudança. Antes, cada imagem ficava ~14 s numa panorâmica lenta. Agora **cada imagem vira 3 ou 4 "tomadas"**: plano geral, depois closes nos rostos e na ação, e de novo um plano médio. Os **cortes são secos e caem nas pausas da narração**, a cada ~4 s, como numa edição com várias câmeras. Os closes são escolhidos automaticamente (`tools/angulos.py`), que procura rostos iluminados e regiões de detalhe. |
| **Títulos: mostre do que se trata antes de falar** | O espectador decide em 1 s se o vídeo é para ele. | É o mesmo gancho de abertura: o título aparece antes da primeira palavra do narrador. Nos Shorts, o título fixo no topo já fazia isso. |
| **Headlines chamativas / agressivas** | A frase de abertura precisa ser forte o bastante para a pessoa ficar. | Os roteiros já abrem com número chocante ou cena forte. A frase da thumbnail (curta e agressiva) agora também abre o vídeo. |
| **Não é só o gancho, é como você termina** (pedir comentário) | O final deve gerar uma ação: comentar. | A pergunta final da narração agora aparece **na tela**, com a faixa vermelha **"COMENTE AQUI EMBAIXO"**. Comentários puxam o algoritmo. |

## O que não aplicamos (de propósito)

- **Legenda palavra por palavra no vídeo longo:** combina com vídeos verticais de fala rápida, mas num documentário 16:9 polui a imagem. Ela continua nos Shorts, onde já está.
- **Colagens de prints e "eu gravando":** é o estilo pessoal dela e não combina com um canal dark de história.

## Como usar

- `python3 tools/render.py 11-constantinopla` renderiza no modo novo (dinâmico), que agora é o padrão.
- `python3 tools/render.py 11-constantinopla --estatico` volta ao estilo antigo, uma panorâmica por imagem.
- O render também grava `videos/.<slug>-limpo.mp4`, o primeiro minuto sem textos. O `tools/short.py` usa esse arquivo, porque o Short tem título e legendas próprios.
