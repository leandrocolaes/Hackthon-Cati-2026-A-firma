# Requisitos e Histórias de Usuário — Leilão Online

**Projeto:** Leilão Online

**Equipe:** A firma

**Data:** 14 de novembro de 2026

**Versão:** 2 (revisada contra o documento da banca `Requisitos_Leilao_Hackathon.pdf`)

## 1. Contexto

### Problema

Construir, em um hackathon de 8 horas ininterruptas, uma plataforma de leilão online em tempo real que continue correta quando vários usuários agem simultaneamente e quando o tempo dos leilões avança.

### Objetivo

Entregar uma plataforma web de leilão online simulado, hospedada em uma VM, na qual usuários se cadastram, anunciam itens, participam de leilões com lances ao vivo e acompanham a abertura, o encerramento e o resultado dos leilões.

A plataforma é uma simulação: não há transações reais e vencer um leilão conta como compra concluída.

### Escopo

Esta versão abrange somente o Núcleo obrigatório definido pela banca:
- Cadastro, login e controle de sessões.
- Criação e cancelamento de leilões.
- Fotos de itens armazenadas no serviço de nuvem fornecido pela organização.
- Listagem pública de leilões e acesso autenticado às salas.
- Sala em tempo real com estado, preço, líder, tempo restante e histórico recente de lances.
- Validação, registro e comunicação de lances, inclusive em concorrência e reenvios.
- Cálculo do lance mínimo e prorrogação de leilões.
- Abertura e encerramento automáticos, inclusive após reinicialização.
- Publicação do sistema completo em uma VM e preparação da demonstração.

### Fora do escopo desta versão

Os itens abaixo só contam depois do Núcleo funcionando de ponta a ponta. Ficam fora desta versão para concentrar as 8 horas nas garantias obrigatórias; podem entrar se sobrar tempo, e o pitch deve explicar o que ficou de fora e por quê.
- **Nível 2:** busca com filtros (RF21), perfil público do comitente (RF22), política completa de edição e cancelamento (RF23), reconexão sem perda de estado (RF24), modo espectador (RF25), aviso de lance superado (RF26), página "Minhas participações" (RF27), relistagem (RF28) e limite de frequência de lances (RF13).
- **Bônus:** pontuação, habilitação de comitente e crédito com reserva (RF29–RF32); extras de nuvem e operação (banco gerenciado, HTTPS com domínio, subida com um comando, deploy automatizado, várias instâncias do back-end, registros e métricas, teste de carga).

### Usuários e stakeholders

- Comprador: papel que todo usuário recebe ao se cadastrar; pode participar de leilões de outros usuários.
- Comitente: usuário que também anuncia itens; no Núcleo, qualquer usuário autenticado pode anunciar, sem habilitação adicional.
- Participante: usuário presente na sala que pode dar lances, respeitando as regras de elegibilidade.
- Visitante: pessoa sem login, que pode visualizar as listagens públicas, mas não entrar em uma sala.
- Organização e banca: fornecem a VM e o serviço de armazenamento em nuvem e avaliam o sistema publicado.

## 2. Levantamento de requisitos

### Necessidades identificadas

- Disponibilizar um fluxo completo e demonstrável de leilão online.
- Permitir que compradores acompanhem e disputem um leilão em tempo real, sem atualizar manualmente a página.
- Garantir que lances inválidos não sejam aceitos.
- Garantir consistência quando lances do mesmo leilão chegam simultaneamente.
- Evitar a duplicação de lances quando uma tentativa é reenviada.
- Usar o horário do servidor como autoridade para abertura, prorrogação e fechamento.
- Manter corretos os estados e os resultados após reinicialização do sistema.
- Permitir que a banca use todos os fluxos do Núcleo pela interface web publicada.

### Regras e restrições

- O sistema deve ser executado na VM fornecida e ficar acessível pelo navegador durante a apresentação.
- A organização fornece um serviço de armazenamento em nuvem para as fotos; as fotos não podem ser armazenadas no banco de dados nem no disco da VM.
- Cada item anunciado tem nome, descrição, categoria e pelo menos 3 fotos.
- Um leilão tem preço inicial, horário de início e duração. O preço inicial é o mínimo admitido para o primeiro lance.
- Um item pode ter vários leilões ao longo do tempo.
- Todo usuário é comprador e qualquer usuário autenticado pode anunciar; não há administrador no Núcleo.
- O comitente nunca pode dar lance em seu próprio leilão.
- Listagens são públicas, mas a entrada em uma sala requer login.
- Lances aceitos não podem ser desfeitos.
- Um leilão com lances não pode ser cancelado.
- O lance mínimo atual é calculado pelo sistema, cresce a cada lance aceito e o primeiro lance pode ser igual ao preço inicial.
- O horário válido é o do servidor, não o contador exibido no navegador.
- Dinheiro deve ser tratado sem erros de arredondamento; horários devem ser consistentes entre fusos, com exibição no fuso de quem visualiza.
- Os estados e transições permitidos do leilão estão registrados na seção 3.3.

### Decisões da equipe

Os itens a seguir estão expressamente abertos à equipe no documento da banca. A garantia obrigatória permanece válida independentemente da escolha. Cada decisão vai para o README com uma ou duas frases de justificativa (seção 6), e as mais importantes aparecem no pitch.

Status: **Definida** = decidida pela equipe. **⚠️ PROPOSTA TEMPORÁRIA** = valor padrão sugerido para destravar o desenvolvimento; precisa ser revisado e confirmado pela equipe antes da entrega.

| Ref. | Decisão | Escolha | Status |
|---|---|---|---|
| RF02 | Duração da sessão e renovação pelo uso | A sessão expira após 2 horas sem atividade; cada ação autenticada renova o prazo. | Definida |
| RF14 | Regra de incremento do lance mínimo | Incremento fixo: lance mínimo = preço inicial (sem lances) ou maior lance aceito + R$ 1,00. | Definida (valor de R$ 1,00 a confirmar) |
| RF15 | Janela de prorrogação, extensão aplicada e limite acumulado | Um lance aceito com menos de 1 minuto restante leva o término para 1 minuto depois do lance. A prorrogação acumulada não passa de 10 minutos além do término original. | Definida |
| RF05 | Categorias e limites de criação | Categorias: Eletrônicos, Casa e decoração, Moda, Esportes e lazer, Colecionáveis, Livros e mídia, Outros. Nome: 3 a 100 caracteres. Descrição: 10 a 2.000 caracteres. Fotos: 3 a 10 no padrão final; `ITEM_MIN_PHOTOS=0` permitido temporariamente na versão mínima/desenvolvimento. Preço inicial: a partir de R$ 1,00. Antecedência do início: de 1 minuto a 30 dias. Duração: de 1 minuto a 7 dias. Todos os limites ficam em configuração (RF06). | Definida (F00; implementação nos cartões correspondentes) |
| RF07 | Tipos e tamanhos de foto | JPEG, PNG e WebP, até 5.242.880 bytes (5 MiB) por arquivo. O tipo é verificado pelo conteúdo do arquivo, e não só pela extensão. | Definida (F00; implementação nos cartões correspondentes) |
| RF09 | Tempo real, lances recentes e identificação do líder | WebSocket, com uma sala por leilão. A sala mostra os últimos 10 lances. Cada participante recebe um apelido estável dentro do leilão ("Participante 1", "Participante 2"…); o próprio usuário se vê como "Você". O vencedor é exibido da mesma forma. | Definida (F00; implementação nos cartões correspondentes) |
| RF20 | Listagem pública | Cartões com foto principal, nome, categoria, preço atual (ou inicial), estado e horário de início ou término. Leilões Em andamento aparecem primeiro, pelo término mais próximo; depois os Agendados, pelo início mais próximo. Paginação de 20 por página. | Definida (F00; implementação nos cartões correspondentes) |
| RNF01 | Organização dos componentes na VM | Proxy reverso (Nginx) servindo o front-end e encaminhando a API e o WebSocket para um back-end; PostgreSQL na própria VM; processo de fundo que, a cada poucos segundos, lê do banco os leilões com horário vencido e aplica as transições. Tudo orquestrado com Docker Compose. | ⚠️ PROPOSTA TEMPORÁRIA |

#### Evoluções planejadas (fora do Núcleo)

Intenções registradas pela equipe para depois que o Núcleo estiver funcionando. Não fazem parte desta versão:
- **RF14 — incremento por faixa e por prorrogação:** trocar o incremento fixo por um incremento que dependa da faixa de preço e cresça conforme o número de prorrogações já ocorridas, para desestimular prorrogações sucessivas. A regra continua válida para o RF14 porque o número de prorrogações faz parte do estado do leilão.
- **RF15 — lance final às cegas:** após o limite de prorrogação, abrir uma janela final em que cada participante pode dar um último lance sem ver os demais, para definir o resultado e dar oportunidade a todos. **Atenção:** antes de implementar, verificar a compatibilidade com o RF09 (todos veem as mudanças na hora), com o RF10 (o líder não pode dar lance; o lance é validado contra o mínimo vigente) e com o RN01 (só existem os cinco estados). Provavelmente exige justificar a mudança no pitch como extensão das regras da banca.

Também precisam ser escolhidos os mecanismos técnicos de autenticação, processamento concorrente, identificação de tentativas repetidas, persistência, agendamento e comunicação em tempo real. A banca estabelece os resultados obrigatórios, mas não determina essas tecnologias.

## 3. Requisitos

### 3.1 Requisitos funcionais

#### RF01 — Cadastro e login

**Descrição:** O usuário pode se cadastrar com nome de exibição, e-mail e senha e depois fazer login. Cada e-mail identifica uma única conta.

**Condições:** O e-mail não pode identificar mais de uma conta.

**Resultado esperado:** Conta cadastrada e possibilidade de autenticação.

#### RF02 — Sessões para ações protegidas

**Descrição:** Todas as ações protegidas, inclusive cada lance, exigem uma sessão válida. A sessão deve expirar.

**Condições:** Duração e renovação conforme a decisão RF02 (seção 2).

**Resultado esperado:** Ações protegidas só são executadas com sessão válida; sessões expiradas não autorizam essas ações.

#### RF03 — Papéis no Núcleo

**Descrição:** Todo usuário é comprador e todo usuário autenticado pode anunciar itens, sem habilitação prévia.

**Condições:** Não existe papel de administrador no Núcleo. A habilitação de comitente por regra é Bônus (RF30).

**Resultado esperado:** Um usuário autenticado pode acessar os fluxos de comprador e comitente.

#### RF04 — Acesso às listagens e salas

**Descrição:** As listagens de leilões são públicas; a entrada em uma sala exige login. O comitente não pode dar lance no próprio leilão.

**Condições:** Visitante sem login; comitente tentando dar lance no próprio leilão.

**Resultado esperado:** Visitante visualiza a listagem, mas não entra na sala; lance do próprio comitente é recusado.

#### RF05 — Criação de leilão

**Descrição:** O usuário cria um leilão informando nome, descrição, categoria, pelo menos 3 fotos, preço inicial, horário de início e duração.

**Condições:** Categorias e limites conforme a decisão RF05 (seção 2).

**Resultado esperado:** Leilão criado com as informações exigidas, respeitando os limites definidos.

#### RF06 — Limites configuráveis

**Descrição:** Os limites usados na criação de leilões devem ser fáceis de alterar, permitindo leilões curtos na demonstração.

**Condições:** Os limites devem permitir, por exemplo, abertura em 1 minuto e duração de 3 minutos (valores ilustrativos da banca).

**Resultado esperado:** Os limites ficam em configuração (arquivo ou variáveis de ambiente) e podem ser alterados sem mudar código.

#### RF07 — Fotos na nuvem

**Descrição:** Fotos devem ser armazenadas no serviço de armazenamento em nuvem fornecido pela organização, e arquivos enviados devem ser validados.

**Condições:** Fotos não são salvas no banco de dados nem no disco da VM; tipos e tamanhos conforme a decisão RF07 (seção 2).

**Resultado esperado:** Uploads aceitos obedecem às regras e ficam no serviço em nuvem; uploads inválidos são recusados.

#### RF08 — Cancelamento de leilão

**Descrição:** O comitente pode cancelar o próprio leilão se estiver Agendado ou Em andamento sem lances.

**Condições:** Leilão com lances não pode ser cancelado. Só o comitente cancela o próprio leilão. O cancelamento não apaga o registro.

**Resultado esperado:** Leilão elegível passa a Cancelado e continua registrado; cancelamento inelegível é recusado.

#### RF09 — Sala em tempo real

**Descrição:** Enquanto o leilão estiver Em andamento, todos na sala recebem, sem recarregar a página, atualizações do preço atual, lance mínimo atual, líder, tempo restante, total de lances e últimos lances. Ao final, todos veem o resultado.

**Condições:** Tecnologia, quantidade de lances recentes e identificação do líder conforme a decisão RF09 (seção 2).

**Resultado esperado:** Participantes veem informações atualizadas e, ao encerrar, o estado Vendido com vencedor e valor ou Encerrado sem lances.

#### RF10 — Validação e recusa de lances

**Descrição:** Cada lance só é aceito se todas as condições abaixo forem verdadeiras no momento do processamento:

1. O autor tem sessão válida e está na sala do leilão.
2. O leilão está Em andamento e não ultrapassou o horário vigente de término.
3. O autor não é o comitente nem o líder atual.
4. O valor é maior ou igual ao lance mínimo vigente no momento do processamento, e não ao valor mostrado quando o usuário clicou.

**Condições:** Todas as quatro verificações são obrigatórias.

**Resultado esperado:** Lances válidos são aceitos. Todo lance recusado informa ao autor o motivo e o lance mínimo atual. Lances aceitos são irrevogáveis.

#### RF11 — Lances simultâneos

**Descrição:** Lances processados simultaneamente em um mesmo leilão nunca deixam o sistema inconsistente. A tentativa que chega primeiro tem prioridade.

**Condições:** Nunca são aceitos dois lances que, juntos, violem a regra de valor. A sala só recebe o novo estado depois que o lance foi gravado de forma definitiva.

**Resultado esperado:** O registro de lances e o estado exibido na sala correspondem apenas aos lances efetivamente gravados.

#### RF12 — Reenvio de lances

**Descrição:** O reenvio da mesma tentativa de lance não cria um segundo lance.

**Condições:** O reenvio pode ocorrer por clique duplo, falha de rede ou sessão expirada.

**Resultado esperado:** O sistema devolve o resultado original da tentativa e não duplica o registro.

#### RF14 — Cálculo do lance mínimo

**Descrição:** O sistema calcula o lance mínimo atual; a tela apenas exibe o valor. A regra deve dar sempre o mesmo resultado para o mesmo estado do leilão, crescer a cada lance aceito e depender só do estado do leilão.

**Condições:** O primeiro lance pode ser igual ao preço inicial. Regra conforme a decisão RF14 (seção 2).

**Resultado esperado:** O sistema exibe e usa o lance mínimo vigente para validar lances.

#### RF15 — Prorrogação

**Descrição:** Ninguém pode vencer com um lance de último segundo sem dar chance de resposta aos outros, e o leilão não pode se estender para sempre.

**Condições:** Janela, extensão e limite acumulado conforme a decisão RF15 (seção 2).

**Resultado esperado:** A regra prorroga o término quando aplicável e respeita o limite total.

#### RF16 — Horário do servidor

**Descrição:** A validade dos horários e lances é determinada pelo relógio do servidor, não pela contagem visual do navegador.

**Condições:** Um lance chega após o horário vigente de término.

**Resultado esperado:** O lance é recusado, mesmo que o navegador ainda mostre segundos restantes.

#### RF17 — Abertura e fechamento automáticos

**Descrição:** Todo leilão deve iniciar no horário agendado e encerrar no horário vigente, consideradas as prorrogações, sem intervenção humana.

**Condições:** O leilão chega ao horário de início ou término.

**Resultado esperado:** Ao encerrar, passa a Vendido se houver lance aceito, com o maior lance vencedor, ou a Encerrado sem lances, se não houver lances.

#### RF18 — Recuperação após reinício e atomicidade do fechamento

**Descrição:** Abertura e encerramento devem continuar corretos após reinicialização do sistema, inclusive quando horários já passaram durante a indisponibilidade.

**Condições:** O sistema reinicia antes ou durante leilões; um lance e o fechamento podem ser processados ao mesmo tempo.

**Resultado esperado:** Ao voltar, leilões que deveriam estar abertos abrem e os que já passaram do término fecham. Fechar duas vezes não duplica o resultado. Nunca existe lance aceito depois do fechamento, nem fechamento no meio do processamento de um lance.

#### RF19 — Precisão monetária e fusos horários

**Descrição:** Valores em dinheiro não podem sofrer erros de arredondamento, e os horários devem representar instantes consistentes para qualquer pessoa e fuso.

**Condições:** Pessoas em diferentes fusos consultam o mesmo leilão.

**Resultado esperado:** Valores permanecem exatos e cada pessoa visualiza os horários em seu próprio fuso, sem alterar os instantes reais do leilão.

#### RF20 — Listagem pública

**Descrição:** Uma página pública lista leilões Agendados e Em andamento, permitindo acessar seus detalhes e a sala de cada leilão.

**Condições:** Dados, ordenação e comportamento com muitos leilões conforme a decisão RF20 (seção 2). A entrada na sala continua exigindo login.

**Resultado esperado:** O visitante vê os leilões elegíveis e pode consultar seus detalhes; usuários autenticados podem entrar nas salas.

### 3.2 Requisitos não funcionais

#### RNF01 — Hospedagem na VM

**Descrição:** Front-end, back-end, banco de dados e processos de fundo devem compor um sistema completo hospedado em uma VM, acessível por navegador durante a apresentação.

**Critério de verificação:** A banca acessa o sistema publicado na VM e realiza seus fluxos. A organização dos componentes segue a decisão RNF01 (seção 2).

#### RNF02 — Fluxos pela interface web

**Descrição:** Todos os fluxos do Núcleo precisam funcionar pela interface web, sem depender de Postman, console do navegador ou outras ferramentas externas.

**Critério de verificação:** A banca executa cadastro, login, criação, acompanhamento, lances, cancelamento quando permitido e encerramento pela interface.

#### RNF03 — Ambiente reproduzível

**Descrição:** Deve ser possível recriar o ambiente do zero seguindo o README.

**Critério de verificação:** As instruções do README permitem reinstalar e iniciar o sistema.

#### RNF04 — Dados de demonstração

**Descrição:** O sistema deve poder ser populado com dados de demonstração contendo pelo menos 1 comitente, 3 compradores e leilões em estados diferentes.

**Critério de verificação:** A preparação da demonstração cria dados suficientes para testar os fluxos do Núcleo.

#### RNF05 — README de entrega

**Descrição:** O README traz o endereço do sistema publicado, como recriar o ambiente do zero, as contas de demonstração e todas as decisões da equipe (seção 2) com uma ou duas frases de justificativa cada.

**Critério de verificação:** Um avaliador encontra no README cada um desses itens.

### 3.3 Regras de negócio

#### RN01 — Estados e transições do leilão

**Descrição:** Todo leilão tem exatamente um dos cinco estados: Agendado, Em andamento, Vendido, Encerrado sem lances ou Cancelado.

**Transições permitidas:**
- Agendado → Em andamento (chega o horário de início).
- Agendado → Cancelado (cancelamento pelo comitente antes do início).
- Em andamento → Cancelado (cancelamento pelo comitente, apenas sem lances).
- Em andamento → Vendido (término com lances aceitos).
- Em andamento → Encerrado sem lances (término sem lances).

Vendido, Encerrado sem lances e Cancelado são estados finais: deles não sai nenhuma transição. Um leilão Em andamento com lances só pode terminar Vendido.

#### RN02 — Item e leilão

**Descrição:** Item é o bem anunciado, com nome, descrição, categoria e ao menos 3 fotos. Leilão é a venda de um item, com início, duração e preço inicial. Um item pode ter vários leilões ao longo do tempo.

#### RN03 — Papéis

**Descrição:** Todo usuário cadastrado é comprador. Um usuário também pode ser comitente ao anunciar itens. Participante é o usuário na sala que pode disputar lances, observadas as restrições.

#### RN04 — Líder e preço inicial

**Descrição:** O líder é o autor do maior lance aceito até o momento. O preço inicial corresponde ao mínimo aceito para o primeiro lance. O líder não pode dar um novo lance enquanto permanecer líder.

#### RN05 — Lances aceitos

**Descrição:** Lances aceitos são irrevogáveis. O comitente não pode disputar seu próprio leilão. No fechamento com lances, o maior lance aceito é vencedor e o leilão termina Vendido.

#### RN06 — Tempo e prorrogação

**Descrição:** A prorrogação aumenta o horário vigente de término quando um lance chega perto do encerramento, conforme a decisão RF15, sujeita a um limite máximo acumulado.

### 3.4 Requisitos de sistema

#### RS01 — Aplicação publicada

**Descrição:** O sistema completo, incluindo interface web, servidor de aplicação, banco de dados e processos de fundo, opera na VM fornecida pela organização.

#### RS02 — Armazenamento de fotos

**Descrição:** As fotos são armazenadas no serviço de nuvem fornecido pela organização; não no banco de dados nem no disco da VM.

#### RS03 — Persistência e recuperação

**Descrição:** Estados dos leilões, lances aceitos e resultados precisam permanecer corretos após reinicialização do sistema. Abertura e fechamento são conduzidos a partir do que está gravado no banco, e não de temporizadores mantidos só em memória.

#### RS04 — Atualizações da sala

**Descrição:** O sistema propaga aos usuários presentes as mudanças de preço, lance mínimo, líder, tempo restante, quantidade e histórico recente de lances e resultado final, sem recarregar a página, sempre depois de a mudança estar gravada.

#### RS05 — Tempo e valores

**Descrição:** O servidor é a referência para decisões temporais; instantes permanecem consistentes entre fusos, e valores monetários não podem apresentar erros de arredondamento.

## 4. Histórias de usuário

As histórias abaixo organizam o Núcleo sob a perspectiva dos usuários. Os critérios derivam das garantias da banca e das decisões registradas na seção 2.

### HU01 — Cadastrar conta

Como visitante, gostaria de criar uma conta para acessar as funcionalidades de comprador e comitente.

**Critérios de aceitação:**
- É possível cadastrar nome de exibição, e-mail e senha.
- Tentar cadastrar um e-mail já existente é recusado com mensagem clara.
- Após o cadastro, a conta pode ser usada para login.

**Referências:** RF01, RF03.

### HU02 — Fazer login e acessar ações protegidas

Como usuário, gostaria de fazer login para acessar salas e realizar ações protegidas.

**Critérios de aceitação:**
- O usuário pode autenticar-se com sua conta.
- Uma ação protegida sem sessão válida é recusada.
- Depois de 2 horas sem atividade, a sessão expira e ações protegidas, inclusive lances, são recusadas; enquanto o usuário age, o prazo é renovado.

**Referências:** RF01, RF02.

### HU03 — Criar um leilão

Como comitente, gostaria de criar um leilão para que outros usuários possam disputar meu item.

**Critérios de aceitação:**
- Qualquer usuário autenticado pode anunciar, sem aprovação de administrador.
- A criação solicita nome, descrição, categoria, preço inicial, horário de início e duração.
- Valores fora dos limites da decisão RF05 são recusados com o motivo.
- Alterar um limite na configuração muda o comportamento sem mudar código (por exemplo, permitir abertura em 1 minuto e duração de 3 minutos).
- O leilão criado fica Agendado até o horário de início.

**Referências:** RF03, RF05, RF06, RN01, RN02.

### HU04 — Enviar as fotos do item

Como comitente, gostaria de enviar as fotos do meu item para que os compradores vejam o que estão disputando.

**Critérios de aceitação:**
- O leilão só é criado com pelo menos 3 fotos válidas.
- Fotos aceitas ficam no serviço de nuvem fornecido; nada é gravado no banco de dados nem no disco da VM além da referência à foto.
- Arquivos com tipo ou tamanho fora da decisão RF07 são recusados com o motivo.

**Referências:** RF05, RF07, RS02.

### HU05 — Consultar leilões públicos

Como visitante, gostaria de ver leilões agendados e em andamento para conhecer os itens anunciados.

**Critérios de aceitação:**
- Sem login, a listagem mostra os leilões Agendados e Em andamento, e só eles.
- É possível acessar os detalhes do leilão a partir da listagem.
- Ao tentar entrar em uma sala sem login, o visitante é levado ao login.
- Dados, ordenação e paginação seguem a decisão RF20.

**Referências:** RF04, RF20.

### HU06 — Acompanhar um leilão em tempo real

Como participante, gostaria de acompanhar as informações da sala para saber a situação da disputa sem recarregar a página.

**Critérios de aceitação:**
- Com dois navegadores na mesma sala, um lance aceito em um aparece no outro sem recarregar: preço, lance mínimo, líder, tempo restante, total de lances e lances recentes.
- O líder é identificado conforme a decisão RF09, sem divulgação do nome completo.
- No término, a sala mostra Vendido com vencedor e valor ou Encerrado sem lances.

**Referências:** RF09, RS04.

### HU07 — Enviar um lance

Como participante, gostaria de dar lances válidos para disputar um item, com a garantia de que a disputa é justa mesmo quando vários usuários dão lances ao mesmo tempo.

**Critérios de aceitação:**
- Um lance só é aceito se a sessão for válida e o usuário estiver na sala.
- Lances são recusados se o leilão não estiver Em andamento ou se tiver ultrapassado o término vigente pelo relógio do servidor, mesmo que o navegador ainda mostre segundos restantes.
- Lances do próprio comitente ou do líder atual são recusados.
- O valor precisa atender ao mínimo vigente no instante do processamento: o preço inicial, se não houver lances, ou o maior lance aceito + R$ 1,00.
- Em caso de recusa, a resposta informa o motivo e o mínimo atual.
- Um lance aceito não pode ser desfeito.
- Dois participantes enviam ao mesmo tempo lances iguais ao mínimo vigente: exatamente um é aceito, e o outro é recusado informando o novo mínimo.
- A sala só mostra o novo estado depois que o lance foi gravado.

**Referências:** RF04, RF10, RF11, RF14, RF16.

### HU08 — Reenviar uma tentativa sem duplicar o lance

Como participante, gostaria que a repetição de uma mesma tentativa não criasse lances adicionais.

**Critérios de aceitação:**
- Reenviar a mesma tentativa devolve seu resultado original.
- Clique duplo, falha de rede ou sessão expirada não provocam a criação de um segundo lance para a mesma tentativa.

**Referências:** RF12.

### HU09 — Cancelar um leilão elegível

Como comitente, gostaria de cancelar meu leilão quando as regras permitirem.

**Critérios de aceitação:**
- O comitente consegue cancelar o próprio leilão Agendado.
- O comitente consegue cancelar o próprio leilão Em andamento sem lances.
- Não é possível cancelar leilão com lances aceitos.
- Um usuário não consegue cancelar leilão de outro comitente.
- O cancelamento altera o estado para Cancelado sem apagar o registro, e o leilão sai da listagem pública.

**Referências:** RF08, RN01.

### HU10 — Ter chance de responder a um lance de último segundo

Como participante, gostaria que lances próximos do término permitissem uma oportunidade de resposta, sem prolongar indefinidamente o leilão.

**Critérios de aceitação:**
- Um lance aceito com menos de 1 minuto restante leva o término para 1 minuto depois do lance.
- Um lance aceito com 1 minuto ou mais restante não altera o término.
- O término nunca passa de 10 minutos além do término original, mesmo com novos lances na janela.
- A sala mostra o novo horário de término e o tempo restante atualizado.

**Referências:** RF09, RF15, RF16, RN06.

### HU11 — Ver o leilão abrir e fechar sozinho

Como participante, gostaria que o leilão abrisse e fechasse nos horários certos e que o resultado fosse mostrado, sem depender de ninguém.

**Critérios de aceitação:**
- O leilão passa de Agendado para Em andamento no horário de início, sem intervenção humana.
- O leilão fecha no horário vigente de término, considerando as prorrogações.
- Se tiver lances aceitos, encerra como Vendido com o maior lance vencedor; se não tiver, encerra como Encerrado sem lances.
- Um lance que chega durante o fechamento é aceito antes do fechamento ou recusado; nunca é aceito depois.
- O resultado é mostrado na sala.

**Referências:** RF09, RF17, RF18, RN01.

### HU12 — Manter os leilões corretos após reinício

Como participante, gostaria que uma reinicialização do sistema não alterasse os leilões nem os lances já aceitos.

**Critérios de aceitação:**
- Leilões cujo início passou durante a indisponibilidade abrem quando o sistema volta.
- Leilões cujo término passou durante a indisponibilidade fecham com o resultado correto quando o sistema volta.
- Processar o fechamento duas vezes não duplica o resultado.
- Nenhum lance aceito antes do reinício é perdido.

**Referências:** RF18, RS03.

### HU13 — Ver valores e horários corretos

Como participante, gostaria de ver valores exatos e horários no meu fuso para não me confundir durante a disputa.

**Critérios de aceitação:**
- Valores com centavos (por exemplo, R$ 0,10 + R$ 0,20) são somados, comparados e exibidos sem erro de arredondamento.
- Dois navegadores configurados em fusos diferentes mostram o horário de início e de término de um mesmo leilão no fuso de cada um, correspondendo ao mesmo instante.

**Referências:** RF19, RS05.

## 5. Validação

### Revisão dos requisitos

Cenários que podem ser preparados a partir do Núcleo (a banca executará vários deles ao vivo, inclusive lances simultâneos, horário de término e reinício):

1. Cadastrar conta e tentar cadastrar outra com o mesmo e-mail (RF01).
2. Tentar uma ação protegida sem sessão válida ou após expiração (RF02).
3. Visualizar listagem sem login e tentar entrar em uma sala (RF04).
4. Criar leilão com os dados obrigatórios e validar fotos no armazenamento de nuvem (RF05–RF07).
5. Cancelar leilão Agendado, Em andamento sem lances e tentar cancelar um com lances (RF08, RN01).
6. Abrir dois navegadores e conferir as atualizações da sala sem recarregar (RF09).
7. Testar lances abaixo do mínimo, após o término, do comitente e do líder atual (RF10, RF14, RF16).
8. Enviar lances simultâneos e conferir a consistência do resultado (RF11).
9. Reenviar a mesma tentativa de lance e verificar que não foi duplicada (RF12).
10. Fazer lance perto do fim e verificar a prorrogação e seu limite (RF15).
11. Verificar abertura e fechamento automáticos, inclusive depois de reiniciar o sistema, e enviar um lance no instante do fechamento (RF17–RF18).
12. Conferir valores monetários exatos e horários coerentes em diferentes fusos (RF19).
13. Executar os fluxos pela interface publicada na VM e reproduzir o ambiente com o README (RNF01–RNF03, RNF05).
14. Preparar dados de demonstração com pelo menos 1 comitente, 3 compradores e leilões em estados diferentes (RNF04).

### Revisão das histórias (INVEST)

Legenda: ✅ atende · ⚠️ atende com ressalva · ❌ não atende.

| HU | I | N | V | E | S | T | Observação |
|---|---|---|---|---|---|---|---|
| HU01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| HU02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Decisão RF02 definida |
| HU03 | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | Limites do RF05 ainda são proposta temporária; fotos separadas na HU04 |
| HU04 | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | Acoplada à HU03 (o leilão exige 3 fotos); tipos do RF07 ainda são proposta temporária |
| HU05 | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | Precisa de leilões existentes (dados de demonstração resolvem); listagem do RF20 ainda é proposta temporária |
| HU06 | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | Maior história de infraestrutura (tempo real); RF09 ainda é proposta temporária |
| HU07 | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ✅ | Núcleo da disputa; concentra validação e concorrência; regra do RF14 definida |
| HU08 | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | Depende da HU07 |
| HU09 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| HU10 | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | Depende da HU07; regra do RF15 definida |
| HU11 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| HU12 | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | Depende da HU11 |
| HU13 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |

As ressalvas de estimativa e teste restantes desaparecem quando as propostas temporárias da seção 2 forem confirmadas. As dependências restantes (HU07 → HU08, HU10; HU11 → HU12) são inerentes ao domínio e definem a ordem de trabalho sugerida: criar, abrir, dar lance e fechar primeiro; depois refinar.

### Ajustes definidos

Mudanças da versão 1 para a versão 2, feitas a partir da comparação com o documento da banca:
- RF11: a sala só recebe o novo estado depois que o lance foi gravado.
- RF14: a regra precisa crescer a cada lance aceito.
- RF18: incluída a garantia de que nunca há lance aceito depois do fechamento, nem fechamento no meio de um lance.
- RF15: descrição alinhada ao texto da banca.
- Incluída a lista do que fica fora do escopo (Nível 2 e Bônus).
- Incluído o RNF05 (conteúdo do README) e a seção 6 (entrega e apresentação).
- Regras de domínio renomeadas de RD para RN, de forma padronizada.
- Histórias reorganizadas: a criação de leilão foi dividida em HU03 (criar) e HU04 (fotos); a concorrência foi incorporada à HU07 (enviar lance), com um teste concreto; abertura/fechamento (HU11) e reinício (HU12) foram separados; criada a HU13 para o RF19; incluído na HU09 o critério de não cancelar leilão de outro usuário.
- Critérios vagos ("fáceis de alterar", "segue a política") substituídos por verificações observáveis.
- Listas numeradas corrigidas.

## 6. Entrega e apresentação

- **Repositório:** com README conforme o RNF05.
- **Pitch:** deve responder (1) qual a arquitetura na VM e por que foi escolhida; (2) quais foram as duas ou três decisões mais difíceis, o que foi considerado e o que cada escolha custou; (3) o que ficou de fora e por quê. A banca escolhe quem responde às perguntas.
- **Demo:** a banca executa cenários no sistema hospedado, inclusive lances simultâneos, horário de término e reinício do sistema, e pode pedir que qualquer membro conduza. Depois, a equipe mostra o que quiser.
