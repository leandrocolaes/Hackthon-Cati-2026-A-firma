# Requisitos e Historias de Usuario - Leilao Online - Fase 2

**Projeto:** Leilao Online  
**Equipe:** A firma  
**Data:** 14 de novembro de 2026  
**Versao:** 1

## 1. Objetivo e escopo

Esta fase evolui o Nucleo ja implementado com descoberta de leiloes, perfil publico, edicao controlada, acompanhamento como espectador, notificacao de lance superado, participacoes, relistagem e limite de frequencia de lances.

O Nucleo permanece a fonte de verdade: o PostgreSQL decide dinheiro, horarios, estado, elegibilidade e ordem de processamento; a interface somente apresenta e solicita acoes. Fotos e armazenamento de fotos ficam explicitamente fora do escopo desta fase por enquanto.

### Itens desta fase

- RF13 - Limite de frequencia de lances.
- RF21 - Busca, filtros e ordenacao do catalogo.
- RF22 - Perfil publico do comitente.
- RF23 - Edicao controlada e politica de cancelamento.
- RF24 - Reconexao da sala sem perda do estado.
- RF25 - Modo espectador.
- RF26 - Aviso de lance superado.
- RF27 - Pagina Minhas participacoes.
- RF28 - Relistagem.

### Fora do escopo

- Upload, armazenamento e validacao de fotos.
- Pagamentos, credito, reserva de saldo e avaliacao.
- E-mail e notificacao do navegador para lance superado.
- Busca textual por relevancia, tolerancia a erro de digitacao ou sinonimos.
- Espectador de leiloes encerrados.

## 2. Regras do Nucleo mantidas e atualizadas

### 2.1 Sessao

A sessao expira apos **2 horas de inatividade**. Acoes autenticadas renovam o prazo; leituras automaticas da sala nao o renovam.

### 2.2 Incremento minimo por faixa

O primeiro lance pode ser igual ao preco inicial. Havendo lider, o lance minimo e o preco atual confirmado acrescido do incremento correspondente a sua faixa:

| Preco atual confirmado | Incremento |
|---|---:|
| Ate R$ 99,99 | R$ 1,00 |
| R$ 100,00 a R$ 499,99 | R$ 5,00 |
| R$ 500,00 a R$ 999,99 | R$ 10,00 |
| R$ 1.000,00 a R$ 4.999,99 | R$ 50,00 |
| R$ 5.000,00 a R$ 24.999,99 | R$ 100,00 |
| A partir de R$ 25.000,00 | R$ 500,00 |

O usuario pode oferecer valor maior ou igual ao minimo. A faixa e calculada pelo estado confirmado no servidor, nunca pelo valor exibido anteriormente no navegador.

### 2.3 Prorrogacao e hard end

Um lance aceito com menos de 1 minuto restante leva o termino vigente para **1 minuto depois daquele lance**. Exemplo: em um leilao cujo termino vigente e 10:00, um lance aceito em 9:03 leva o termino a 10:03.

O termino nunca ultrapassa o **hard end**, definido como termino original + 10 minutos. Ao atingir esse teto, nenhum novo lance prorroga o leilao.

A sala deve mostrar o horario do hard end enquanto houver possibilidade de prorrogacao e deve apresentar aviso persistente quando o teto for atingido, deixando claro que o encerramento sera definitivo naquele horario.

## 3. Requisitos funcionais

### RF13 - Limite de frequencia de lances

Um participante pode enviar no maximo um lance a cada **2 segundos**, por leilao.

- A verificacao ocorre no backend, pelo relogio do servidor.
- A tentativa dentro do intervalo e recusada claramente, informando quantos segundos faltam para novo lance.
- Nao ha bloqueio temporario de conta, punicao ou exclusao automatica.
- A regra nao substitui validacao de minimo, sessao, lider, comitente e estado do leilao.

### RF21 - Busca, filtros e ordenacao

A pagina publica de catalogo continua exibindo somente leiloes Agendados e Em andamento e passa a oferecer os recursos abaixo, combinaveis entre si.

- **Busca:** campo unico que procura parte do nome do item, sem diferenciar maiusculas de minusculas. Nao busca descricao nesta fase.
- **Categoria:** selecao unica entre Todas e as categorias configuradas.
- **Estado:** Todos, Em andamento ou Agendados.
- **Faixa de preco:** preco minimo e/ou maximo inclusivos, aplicados ao preco atual confirmado. Para Agendados, preco atual equivale ao preco inicial.
- **Ordenacao:**
  1. Padrao: Em andamento por termino mais proximo; depois Agendados por inicio mais proximo.
  2. Termina primeiro.
  3. Comeca primeiro.
  4. Menor preco.
  5. Maior preco.
- **Paginacao:** 20 resultados por pagina. Toda mudanca de filtro ou ordenacao volta para a primeira pagina.
- **URL:** filtros, ordenacao e pagina ficam nos parametros da URL para permitir compartilhar a consulta.

Exemplo: `/leiloes?busca=relogio&categoria=Colecionaveis&estado=em_andamento&preco_min=100&preco_max=1000&ordenar=preco_asc&pagina=1`.

### RF22 - Perfil publico do comitente

Cada comitente possui perfil publico acessivel a partir dos seus leiloes.

O perfil mostra:

- nome de exibicao;
- leiloes em andamento e agendados do comitente;
- resumo publico de leiloes encerrados.

O perfil nao mostra e-mail, sessoes, identificadores internos, dados de login ou qualquer dado privado.

### RF23 - Edicao controlada e cancelamento

O cancelamento ja segue esta politica e ela permanece valida:

- somente o comitente pode cancelar;
- um leilao Agendado pode ser cancelado;
- um leilao Em andamento so pode ser cancelado se ainda nao houver lances e o termino nao tiver passado;
- cancelar nao apaga o registro;
- cancelamento concorre com lance e fechamento sob a mesma trava do leilao.

A Fase 2 acrescenta edicao somente para leilao **Agendado e sem lances**.

- O comitente pode alterar nome, descricao, categoria, preco inicial, inicio e duracao nesse estado.
- Depois que o leilao iniciar ou receber lance, nenhuma dessas propriedades pode ser editada.
- A gravacao deve detectar conflito de versao: se o leilao mudou desde que o formulario foi aberto, o comitente recebe aviso e revisa antes de salvar.

### RF24 - Reconexao sem perda de estado

Ao cair ou recarregar a pagina, a sala deve voltar ao estado confirmado mais recente.

- Na reconexao, o cliente busca snapshot atual da sala e abre novamente o canal em tempo real.
- O snapshot possui versao; o cliente nunca substitui estado mais novo por versao mais antiga.
- Enquanto o canal em tempo real estiver indisponivel, a tela usa polling de reserva.
- Reconexao nao cria lance, nao duplica participante e nao renova sessao apenas por assistir.

### RF25 - Modo espectador

Leiloes Em andamento podem ser assistidos sem login.

- Visitante sem login entra como espectador, sem criar registro de participante.
- Usuario autenticado tambem pode escolher a opcao Assistir, sem se tornar participante.
- Espectador ve preco atual, lance minimo, lider anonimizado, historico recente, tempo restante e resultado quando houver.
- Espectador nao recebe controles de lance, cancelamento ou outros menus exclusivos de participante/comitente.
- Inicialmente, o modo espectador so existe para leiloes Em andamento; leiloes encerrados permanecem fora desse modo.
- A API publica de espectador nunca devolve dados privados ou identificadores internos desnecessarios.

### RF26 - Aviso de lance superado

Quando um participante que esta presente na sala deixa de ser lider devido a lance aceito de outra pessoa, a sala apresenta mensagem instantanea.

- O aviso aparece somente para quem esta na sala naquele momento.
- Cada usuario recebe no maximo **um aviso de lance superado por leilao**. Se ja foi avisado uma vez, novos lances superados nao geram novas notificacoes.
- O aviso e interno a sala; nao ha e-mail, push ou notificacao do navegador nesta fase.
- A decisao de lider vem do snapshot confirmado no servidor.

### RF27 - Minhas participacoes

Usuario autenticado possui pagina com quatro grupos de leiloes em que entrou como participante:

1. **Em disputa:** Agendados e Em andamento.
2. **Vencidos:** leiloes Vendidos cujo lance vencedor pertence ao usuario.
3. **Nao vencidos:** leiloes Vendidos cujo vencedor e outro participante, e Encerrados sem lances quando aplicavel.
4. **Cancelados/encerrados:** leiloes Cancelados e demais resultados finais que nao pertencem aos grupos anteriores.

Cada cartao mostra item, estado, preco atual ou final, termino e atalho para detalhe ou sala quando ela estiver acessivel.

### RF28 - Relistagem

O comitente pode criar nova listagem a partir de leilao finalizado ou cancelado.

- A relistagem abre formulario novo, pre-preenchido com os dados reutilizaveis do item e do anuncio anterior.
- O comitente pode alterar todos os campos antes de confirmar.
- Datas, horarios e prazo anterior nao sao herdados: a nova listagem exige novo inicio e nova duracao.
- A nova listagem nao herda lances, lider, participantes, vencedor, resultado, termino vigente, prorrogacoes ou qualquer historico de disputa.
- Ao confirmar, cria novo leilao Agendado, com novo identificador e preco inicial escolhido no formulario.
- Relistagem so e permitida para Vendido, Encerrado sem lances e Cancelado; nunca para Agendado ou Em andamento.

## 4. Historias de usuario

### HU14 - Encontrar leiloes

Como visitante, quero buscar, filtrar e ordenar leiloes publicos para encontrar rapidamente itens relevantes.

**Aceitacao:** combinacoes de busca, categoria, estado e faixa de preco funcionam; a URL preserva os criterios; a paginacao respeita os filtros.

### HU15 - Conhecer o comitente

Como visitante, quero consultar perfil publico do comitente para conhecer seus leiloes sem expor seus dados privados.

**Aceitacao:** perfil exibe somente dados publicos definidos no RF22.

### HU16 - Editar antes da disputa

Como comitente, quero corrigir meu anuncio antes de ele iniciar para manter a informacao correta.

**Aceitacao:** somente Agendado sem lances pode ser editado; conflito de versao pede revisao; leilao iniciado ou com lances recusa edicao.

### HU17 - Acompanhar como espectador

Como visitante ou usuario autenticado, quero assistir a disputa sem participar para acompanhar o leilao ao vivo.

**Aceitacao:** espectador de leilao Em andamento ve o estado completo permitido, mas nao cria participante nem pode dar lance.

### HU18 - Saber que fui superado

Como participante presente, quero receber aviso imediato quando deixo de ser lider para entender a situacao da disputa.

**Aceitacao:** aviso aparece dentro da sala uma unica vez por usuario/leilao e somente apos mudanca confirmada de lider.

### HU19 - Rever minhas participacoes

Como usuario autenticado, quero separar minhas disputas em andamento, vencidas, nao vencidas e encerradas para acompanhar meus resultados.

**Aceitacao:** os quatro grupos seguem RF27 e cada item leva ao detalhe ou sala disponivel.

### HU20 - Relistar um item

Como comitente, quero reaproveitar informacoes de um item finalizado para anuncia-lo novamente sem contaminar o novo leilao com a disputa anterior.

**Aceitacao:** nova listagem possui novo identificador, agenda e historico vazio; o formulario permite revisar dados antes de confirmar.

### HU21 - Evitar envio excessivo de lances

Como participante, quero receber motivo claro se tento enviar lance cedo demais para saber quando posso tentar novamente.

**Aceitacao:** backend recusa tentativa antes de 2 segundos e informa o tempo restante; apos o intervalo, demais regras usuais continuam valendo.

## 5. Validacao e prioridades

1. Testar cada limite de faixa de incremento, inclusive R$ 99,99, R$ 100,00, R$ 499,99, R$ 500,00 e demais fronteiras.
2. Testar prorrogar a menos de 1 minuto e confirmar hard end em termino original + 10 minutos, com aviso na sala.
3. Testar filtros isolados e combinados, pagina e URL compartilhada.
4. Testar que perfil publico nao expoe e-mail ou dados internos.
5. Testar duas edicoes concorrentes e recusa de edicao apos inicio ou lance.
6. Interromper conexao da sala e confirmar que snapshot/versao recuperam estado correto sem criar nova participacao.
7. Abrir espectador sem login e confirmar ausencia de controles de lance/cancelamento.
8. Fazer usuario perder lider mais de uma vez e confirmar que recebe somente um aviso interno.
9. Testar os quatro grupos de Minhas participacoes.
10. Relistar cada estado permitido e confirmar que lance, lider, participantes e prazos antigos nao reaparecem.
11. Enviar dois lances do mesmo usuario em menos de 2 segundos e verificar recusa com tempo restante.
