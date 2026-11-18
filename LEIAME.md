# Clipador

Pega a sua live de GTA na Twitch, acha os momentos sozinho, reenquadra pro vertical
e deixa o clipe pronto com titulo, legenda e hashtags.

Roda de dois jeitos: no navegador, sem instalar nada, ou no seu Mac.

## Jeito 1: no navegador, sem instalar nada (recomendado)

O proprio GitHub roda o app numa maquina na nuvem e mostra a tela no seu navegador.

1. Nesta pagina do repositorio, clique no botao verde **Code**.
2. Aba **Codespaces**, botao **Create codespace on main**.
3. Espera de 3 a 5 minutos na primeira vez. Ele instala tudo sozinho.
4. A tela do Clipador abre numa aba de visualizacao do lado. Se nao abrir,
   va na aba **PORTS** embaixo, porta 8777, e clique no icone de globo.

Pra pegar os clipes prontos: no explorador de arquivos da esquerda, abra
`clipador-dados/clipes`, clique com o botao direito no MP4 e escolha **Download**.

Quando terminar, volte em **Code > Codespaces** e pare o codespace, pra nao
gastar as horas gratuitas (60 horas por mes numa maquina de 2 nucleos).

Diferenca pro Mac: na nuvem nao tem o chip da Apple, entao a transcricao e o
render usam processador comum e demoram mais. Um clipe de 2min30 leva uns 4
minutos pra montar em vez de menos de um.

## Jeito 2: no seu Mac

Baixe o `Instalar Clipador.command`, clique nele com o botao direito e escolha
Abrir. Se o macOS bloquear mesmo assim, va em Ajustes do Sistema, Privacidade e
Seguranca, role ate o aviso sobre o arquivo e clique em **Abrir Assim Mesmo**.

Rodando no Mac ele fica bem mais rapido: usa o encoder de video do chip e a
transcricao no Neural Engine.

## Antes da primeira live

Liga o guardar de VOD na Twitch, senao nao sobra nada pra clipar:

Twitch no navegador > Painel de criador > Configuracoes > Transmissao >
**Armazenar transmissoes anteriores**. So da pra ligar pela web, nao pelo PS5
nem pelo celular. O VOD fica 7 dias em conta comum, 14 em afiliado e 60 em
parceiro, Turbo ou Prime.

## Como usar

**Fonte.** Escreve o nome do seu canal e clica em Ver o canal. Ele diz se voce
esta ao vivo e lista os VODs guardados.

**Dois modos, voce escolhe na tela:**

- *Depois da live*: baixa o VOD e processa com a maquina livre. E o recomendado
  pro seu caso, porque durante a transmissao o Mac ja esta jogando a tela da
  Twitch pro TikTok.
- *Durante a live*: copia a transmissao em pedacos de 5 minutos sem recodificar
  nada (gasta quase nada de processador) e vai achando os momentos enquanto
  voce joga. O chat e lido ao vivo nos dois modos quando a live esta no ar.

**Momentos.** Cada cartao mostra a nota, a duracao, por que aquilo foi marcado
(chat acelerou, voce levantou a voz, estouro grave, tomou dano, nivel de procurado
subiu) e o que voce falou. Voce mexe no inicio e no fim, corrige o titulo, e so
clica em Montar no que quiser. Nada e renderizado antes disso.

**Fila.** Clipe pronto, com horario e redes marcados, pra voce baixar e subir.

## Como ele acha os momentos

Ele nao olha so volume, que era o erro do clipador antigo. Junta:

- chat da Twitch ao vivo: velocidade das mensagens, risada (kkkk, LUL), susto
  (nossa, caralho, mano, que isso), caixa alta e pedido explicito de clipe
- audio: subida rapida de volume, energia na faixa da voz, estouro grave de
  explosao e tiro
- imagem: corte de cena, quantidade de movimento, clarao
- GTA: leitura do texto na tela (WASTED, BUSTED, MISSAO CONCLUIDA, ELIMINADO),
  nivel de procurado subindo e barra de vida caindo

Tudo isso vira uma curva unica e os picos dessa curva sao os momentos.

## Duracao do clipe

Alvo de 2min30, mas respira: comeca no corte de cena antes do sinal subir e
termina depois do desfecho, com 2 segundos de folga. Preso entre 45s e 3min,
que e o que cabe em TikTok, Reels e Shorts. Tudo isso se muda em Ajustes.

## GTA VI

O perfil de HUD do GTA VI vem marcado como nao calibrado, porque o jogo saiu
agora e a posicao do minimapa e das estrelas ainda nao esta mapeada. A leitura
de texto ja funciona sem calibrar.

Pra calibrar: Ajustes > Calibrar com um print. Voce solta um print do jogo,
escolhe a regiao na lista, arrasta um retangulo em cima dela e salva. Dois
minutos, uma vez so.

## O que mudou em relacao ao clipador antigo

- acha momento por varios sinais, nao so por volume
- le o chat da Twitch, que e o sinal mais forte
- le o que o GTA escreve na tela
- corte com inicio e fim escolhidos pelo conteudo, nao janela fixa
- tempo de cada palavra vindo do proprio Whisper, entao a legenda e o bipe de
  palavrao caem no lugar certo
- transcreve uma vez so, e por padrao so em volta dos candidatos
- sai em 60fps, nao em 30
- volume equalizado de verdade (EBU R128, duas passadas)
- legenda fora da area dos botoes do TikTok
- titulo numa caixa so, com quebra certa, sem invadir o gameplay
- minimapa entra como inserto no canto quando o corte vertical o deixaria de fora
- capa gerada junto
- seu estilo fica salvo, sem perguntar nada a cada leva
- fila de clipes, nao um de cada vez
- apaga o video bruto quando voce manda, pra nao entupir o disco

## Postar sozinho

Ainda nao, e o motivo nao e tecnico. TikTok e YouTube so liberam post publico
por aplicativo depois de uma auditoria que leva de dias a semanas, e o Instagram
exige que o app esteja ligado na hora da publicacao. Por isso a fila deixa tudo
pronto e voce sobe. Quando quiser encarar a auditoria, da pra ligar.

## Pastas

Tudo fica em `~/Clipador`:

- `clipes`: os MP4 montados
- `capas`: as capas
- `bruto`: VOD e pedacos da live (e isso que voce apaga pelo botao)
- `dados`: banco, chat e sinais
- `perfis`: perfis de HUD

## Se der problema

Abre o Terminal e roda `~/Clipador/venv/bin/python <pasta>/clipador.py`. A tela
e a mesma e o terminal mostra o erro.
