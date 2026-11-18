# Clipador

Pega a sua live de GTA na Twitch, acha os momentos sozinho, reenquadra pro
vertical e deixa o clipe pronto com titulo, legenda e hashtags.

Roda dentro do GitHub, pelo navegador. Nao instala nada, nao importa se voce
esta no Mac, no Windows ou no Linux, e nao precisa ser sempre o mesmo
computador. So precisa estar logado na sua conta do GitHub, porque o
repositorio e privado.

## Como usar, de qualquer computador

1. Abra **github.com/alanmatosdebarros-png/clipador** e entre na sua conta.
2. Aba **Actions**, no topo.
3. Na lista da esquerda, **Clipar uma live**.
4. Botao **Run workflow**, no canto direito.
5. Cole o link do VOD da Twitch, escolha quantos clipes quer, confirme em
   **Run workflow**.
6. Pode fechar o navegador e ate desligar o computador. O processamento
   acontece na maquina do GitHub, nao na sua.
7. Quando terminar, volte em Actions e abra a execucao. No fim da pagina tem
   **Artifacts**, com um arquivo `clipes`. Baixa e pronto.

Dentro do `clipes` vem os MP4 em 9:16, as capas e um `textos.json` com titulo,
legenda e hashtags de cada clipe. Na propria pagina da execucao aparece uma
tabela com os momentos, a nota de cada um e por que foram marcados.

Uma live de 4 horas leva mais ou menos 1 hora. Os clipes ficam guardados por 5
dias, entao baixe dentro desse prazo.

## No celular

Funciona igual, pelo navegador ou pelo aplicativo do GitHub. Disparar a
execucao e acompanhar funciona bem; baixar o pacote de clipes e mais comodo no
computador.

## Antes da primeira live

Ligue o guardar de VOD na Twitch, senao nao sobra nada pra clipar:

Twitch no navegador, Painel de criador, Configuracoes, Transmissao,
**Armazenar transmissoes anteriores**. So da pra ligar pela web, nao pelo PS5
nem pelo celular. O VOD fica 7 dias em conta comum, 14 em afiliado e 60 em
parceiro, Turbo ou Prime.

## Titulo e legenda escritos pelo Claude

Opcional. Em Settings, Secrets and variables, Actions, crie um segredo chamado
`ANTHROPIC_API_KEY`. Sem ele o Clipador continua funcionando, so com texto mais
simples, montado a partir da propria transcricao.

## Como ele acha os momentos

Nao olha so volume. Junta varios sinais e tira os picos da soma deles:

- audio: subida rapida de volume, energia na faixa da voz, estouro grave de
  explosao e tiro
- imagem: corte de cena, quantidade de movimento, clarao
- GTA: leitura do texto na tela (WASTED, BUSTED, MISSAO CONCLUIDA, ELIMINADO),
  nivel de procurado subindo e barra de vida caindo
- chat da Twitch: velocidade das mensagens, risada, susto, caixa alta e pedido
  explicito de clipe (so quando o Clipador acompanha a live em tempo real)

## Duracao do clipe

Alvo de 2min30, mas respira: comeca no corte de cena antes do sinal subir e
termina depois do desfecho, com 2 segundos de folga. Preso entre 45s e 3min,
que e o que cabe em TikTok, Reels e Shorts.

## GTA VI

O perfil de HUD do GTA VI vem marcado como nao calibrado, porque o jogo saiu
agora e a posicao do minimapa e das estrelas ainda nao esta mapeada. A leitura
de texto na tela ja funciona sem calibrar.

## A tela do app, se um dia quiser mexer nela

O repositorio tambem traz o Clipador com interface, que roda numa maquina na
nuvem pelo **Code > Codespaces**, ou no seu proprio computador. Isso e
opcional: o caminho pelo Actions acima nao precisa de nada disso. O
`Instalar Clipador.command` na raiz e um instalador so pra macOS, de uma versao
anterior do plano, e pode ser ignorado.

## Postar sozinho

Ainda nao, e o motivo nao e tecnico. TikTok e YouTube so liberam post publico
por aplicativo depois de uma auditoria que leva de dias a semanas, e o
Instagram exige que o app esteja ligado na hora da publicacao. Por isso o
Clipador entrega tudo pronto e voce sobe.
