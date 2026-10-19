# Sombras da História — Guia do Canal

**Slogan:** *A história que os livros esquecem.*

Um canal dark (sem rosto) de história mundial: Roma, Grécia, Egito, Idade Média, impérios, mistérios e tragédias. O tom é de documentário. É sério e imersivo, sempre com uma virada ("o que você sabe está errado") e com fatos verificáveis.

Outros nomes que considerei, caso o principal já esteja em uso no YouTube: **Relíquias do Tempo**, **Arquivo Antigo**, **Crônicas Sombrias**, **O Cronista**.

---

## Identidade visual

| Item | Definição |
|---|---|
| Estilo das imagens | Pintura a óleo cinematográfica, claro-escuro (Rembrandt), sombras profundas, granulação de filme |
| Paleta | Preto, ocre, dourado `#E9C46A` e vermelho-sangue `#C81616` |
| Fonte da thumbnail | **Anton** (títulos grandes, em caixa alta) |
| Fonte da marca | **Cinzel** (nome do canal, estilo inscrição romana) |
| Thumbnail | Personagem ou cena à direita, lado esquerdo escuro com 2 linhas de texto: a 1ª em branco, a 2ª em uma faixa vermelha |
| Avatar e banner | `canal/avatar.jpg` (800×800) e `canal/banner.jpg` (2560×1440, o texto já está na área segura) |

## Voz

- **ElevenLabs:** *Nassif – Documentary, History & Thriller* (`acdKA5HckGxoxxvy40dA`), PT-BR, modelo `eleven_multilingual_v2`.
- Grave, cadenciada e com pausas, no estilo History Channel.
- Custo: ~1 crédito por caractere. Cada vídeo de ~4–5 min gasta ~3.500–4.600 créditos.

## Fórmula do roteiro (10 cenas, ~4–5 min)

1. **Gancho (cena 1):** um número chocante ou uma cena forte, terminando com "mas o que você sabe... está errado".
2. **Contexto (cenas 2–3):** como tudo começou.
3. **Desenvolvimento (cenas 4–7):** curiosidades e quebra de mitos. Um "detalhe que quase ninguém conhece" por cena.
4. **Clímax (cenas 8–9):** o momento mais sombrio ou a grande revelação.
5. **Fechamento (cena 10):** a reflexão, uma pergunta para os comentários e o CTA "se inscreva".

Cada cena tem uma linha `IMG:` com o prompt da imagem, em inglês.

## Pipeline de produção

```
roteiros/NN-tema.md        → roteiro + metadados (TITULO, THUMB, DESCRICAO, TAGS)
audio/NN-tema.mp3          → narração ElevenLabs (texto: python3 tools/narracao.py roteiros/NN-tema.md)
imagens/NN/cenaXX.jpg      → 10 imagens 16:9 + thumb_base.jpg
python3 tools/render.py NN-tema   → videos/NN-tema.mp4 (Ken Burns, crossfade, trilha ambiente)
python3 tools/thumb.py NN-tema    → thumbnails/NN-tema.jpg (1280×720)
```

Os prompts de imagem de todos os roteiros estão em `prompts-imagens.md`.

---

## Os 10 primeiros vídeos (pacote de upload)

Ordem sugerida de publicação (comece pelos temas mais buscados):

| # | Arquivo | Título | Duração |
|---|---|---|---|
| 1 | 01-coliseu | O Lado Sombrio do Coliseu que Ninguém Te Contou | 5:41 |
| 2 | 08-piramides | Quem Realmente Construiu as Pirâmides do Egito? | 4:40 |
| 3 | 03-termopilas | 300 Contra 1 Milhão? A Verdade Sobre as Termópilas | 4:56 |
| 4 | 06-cleopatra | Cleópatra: A Última Rainha do Egito Não Era Quem Você Pensa | 4:34 |
| 5 | 02-pompeia | As Últimas 24 Horas de Pompeia | 4:54 |
| 6 | 09-templarios | Sexta-Feira 13: O Dia em que os Templários Caíram | 4:54 |
| 7 | 07-vikings | O Dia em que os Vikings Chegaram: Lindisfarne, 793 | 4:29 |
| 8 | 05-peste-negra | Peste Negra: Quando Um Terço da Europa Morreu | 4:31 |
| 9 | 04-alexandria | Quem Realmente Destruiu a Biblioteca de Alexandria? | 5:22 |
| 10 | 10-fogo-grego | Fogo Grego: A Arma Secreta que Ninguém Consegue Recriar | 4:22 |

A descrição e as tags de cada vídeo estão no topo do roteiro (`roteiros/NN-tema.md`). Na descrição, acrescente:

```
📜 Sombras da História — a história que os livros esquecem.
🔔 Inscreva-se e ative o sininho para novos episódios.
Narração: voz gerada por IA (ElevenLabs). Imagens: ilustrações geradas por IA.
```

**Ritmo sugerido:** 3 vídeos por semana (seg/qua/sex, ~18h). Isso cobre ~3 semanas com esse lote.

## Avisos importantes ao postar

- **YouTube Studio → Detalhes → "Conteúdo alterado ou sintético":** marque **Sim**, já que as imagens são geradas por IA e retratam cenas realistas. É obrigatório e não prejudica o alcance.
- **Monetização:** o YouTube desmonetiza canais com conteúdo "repetitivo/produzido em massa". Para se proteger, mantenha roteiros originais (como estes) e varie os ganchos e as estruturas. Se possível, acrescente edição própria (zoom, legendas, efeitos sonoros).
- Revise os fatos de cada roteiro antes de postar. Os fatos foram escritos com cuidado, mas os comentários de canais de história são exigentes.

## Próximos temas (para o lote 2)

Calígula · Átila, o Huno · A queda de Constantinopla · Os astecas e Hernán Cortés · Gengis Khan · O naufrágio do Vasa · Joana d'Arc · A Grande Muralha · Os gladiadoras (mulheres na arena) · O Exército de Terracota · A Inquisição · Os piratas da era de ouro · Rasputin · Chernobyl · O Titanic
