# Correções do painel e aplicativo — 26/10/2026

As alterações foram aplicadas ao projeto existente, preservando Django, Flutter, estilo visual e fluxo de QR Code. Neste repositório, `tcc-web/` contém o painel/API e o aplicativo chamado tcc-Flutter no pedido fica na raiz (`lib/`, `test/`, `android/`, `ios/`).

Backup do código anterior: `backups/correcoes-2026-10-26/codigo-antes-20261026T151914Z.zip`. O backup exclui segredos, bancos e diretórios de compilação. Nenhuma nova migração é necessária e os registros reais não foram alterados por esta revisão. Os testes PostgreSQL usaram schema aleatório separado, removido ao final.

## 1. Painel web: alterações e teste manual por item

| Item | O que foi feito | Como testar manualmente |
|---|---|---|
| **1. Senhas** | Ação Redefinir senha na lista e no detalhe do usuário. Formulário com confirmação e validadores Django: mínimo de oito caracteres, sem senha comum, inteiramente numérica ou semelhante ao cadastro. Revogação dos tokens anteriores e auditoria sem registrar a senha. | 1) Entre como administrador. 2) Abra Usuários → Redefinir senha para um associado, motorista e fiscal de teste. 3) Tente senha curta e confirmação diferente: devem ser recusadas. 4) Informe uma senha válida duas vezes. 5) Entre no app com ela; a antiga e os tokens anteriores devem falhar. |
| **2. Inativação de ônibus** | Confirmação lista as rotas ativas vinculadas. A operação inativa ônibus e rotas numa transação. Mantida a proteção de viagens em andamento. Reativar ônibus mantém rotas inativas. | 1) Escolha um ônibus sem viagem em andamento e com duas rotas. 2) Clique Inativar e confira os nomes. 3) Cancele e confira que nada mudou. 4) Confirme e confira ônibus/rotas inativos. 5) Reative o ônibus e confira rotas ainda inativas. 6) Com viagem em andamento, a tentativa deve explicar o bloqueio. |
| **3. Filtro de situação** | Ônibus e Rotas usam o mesmo componente Ativos / Inativos / Todos, preservando busca e reiniciando a paginação. | 1) Em ambas as telas, alterne os três filtros. 2) Faça uma busca e troque o filtro. 3) Confira apresentação igual, busca preservada e resultados coerentes. |
| **4. Embarques** | Ao entrar sem data, seleciona a data da última viagem efetivamente iniciada e mostra sua identificação. Agendadas ou encerradas automaticamente sem início real não substituem essa referência. Preservadas as viagens dessa data e os filtros manuais. | 1) Abra Embarques num dia sem novas viagens. 2) Confira a data e o nome da última viagem iniciada. 3) Selecione outra data e aplique. 4) Use Hoje e Última viagem para alternar. 5) Confira registros, sentido e poltronas. |
| **5. Layout de relatórios** | Despesas e Baixar PDF ficam juntos no cabeçalho. | 1) Abra Relatórios. 2) Confira os dois botões agrupados e alinhados. 3) Reduza a janela e confira que continuam acessíveis. |
| **6. Baixar PDF** | Tela e exportação usam os mesmos filtros; o PDF inclui o ponto informado. Download autenticado validado por testes, com PostgreSQL somente leitura e no navegador. A quebra original não foi reproduzida; sua causa específica continua não confirmada. | 1) Selecione período com registros, ônibus, associado e ponto. 2) Aplique filtros e clique Baixar PDF. 3) Abra o arquivo e compare filtros, totais, associado e ponto com a tela. 4) Repita com período vazio. Se houver falha em outro ambiente, registre o erro completo e os filtros para reproduzi-la. |
| **7a. Ponto no relatório** | O ponto aparece nos resultados e no PDF. Preserva o nome histórico; quando vazio, usa o vínculo existente, sem inventar dados. | 1) Escolha um ponto e aplique. 2) Confira Filtros aplicados e a coluna Ponto informado. 3) Exporte e confira o mesmo ponto no PDF. |
| **7b. Associado no relatório** | Uma única busca por nome, e-mail ou RUA, no formulário principal; aplica-se aos resultados e ao PDF. Instituição fica no mesmo formulário. | 1) Busque um associado pelo nome. 2) Repita por e-mail e RUA. 3) Confira frequência, registros e PDF. A ocupação da viagem considera todos os passageiros, como informa a tela. |
| **7c. Rotas no relatório** | Removido o seletor independente de rota. Escolher um ônibus inclui suas rotas. URLs antigas continuam compatíveis. | 1) Selecione um ônibus com mais de uma rota no período. 2) Confira os registros de todas as suas rotas. 3) Troque o ônibus e confirme que os resultados acompanham a seleção. |
| **8. Destaque do menu** | Operação das viagens e Pontos de embarque usam o mesmo indicador laranja das demais opções, inclusive nas páginas internas. | 1) Abra Operação das viagens e uma intervenção. 2) Abra Pontos de embarque e a edição de um ponto. 3) Confira o destaque correspondente. |
| **9. Pontos dentro de Gestão** | Atalho permanente abaixo de Gestão na navegação e cartão no painel Gestão. | 1) Após entrar, abra Gestão diretamente. 2) Confira cartão e submenu Pontos. 3) Navegue para outras telas e retorne: a opção deve continuar disponível. |

## 2. Flutter: alterações e teste manual por item

Para os testes de reserva, use dois ônibus A/B com viagens do mesmo dia, pontos de ida/volta, instituição atendida e vagas; contas distintas de associado, motorista e fiscal. A escolha abre às 08:00 no fuso da operação ou antes se o motorista iniciar a rota. Faça testes de cadastro e senha em contas de teste.

| Item | O que foi feito | Como testar manualmente |
|---|---|---|
| **1. Menu da conta** | Removidas a opção, tela e chamada de alteração de senha. O menu contém somente Sair. A API antiga de senha responde 410 orientando procurar a administração. | 1) Entre em cada perfil. 2) Abra Opções de conta. 3) Confira somente Sair. 4) Saia e confira retorno ao login. |
| **2. Login** | Removidos Continuar como e restauração automática de credenciais. Tokens ficam em memória; a fila offline por usuário é preservada. | 1) Entre e saia. 2) Feche e reabra o app. 3) Confira que exige identificação e senha, sem Continuar como. 4) Com uma operação pendente em ambiente de teste, entre novamente na mesma conta e confira a fila preservada; outra conta não deve receber essa fila. |
| **3. GPS** | Mensagens específicas para serviço desligado, permissão negada/bloqueada e contexto web sem HTTPS. Captura/envio periódico, atualização do mapa e erros de envio visíveis. Aceita precisão até 100 m; posição aproximada é indicada. Reenvio idempotente, motivos de recusa e fim do rastreamento ao encerrar. | 1) Em telefone real, negue a permissão e confira orientação. 2) Ative localização precisa e permita o acesso. 3) Inicie a rota e desloque o aparelho em área aberta. 4) Confira atualização no app e em Acompanhar viagens no web. 5) Teste segundo plano, tela bloqueada, perda/retorno de rede e encerramento. Captura usual: 10 s em percurso e 60 s no destino, além do tempo da leitura/envio; erro tenta novamente após 20 s. |
| **4. Poltrona e QR** | Antes da escolha: Escolher poltrona. Com escolha: Alterar escolha, sem duplicação. Durante embarque aberto, aparece Ler QR Code. Após confirmar, o sentido fica bloqueado e aparece comprovante. Cancelamento explícito dos sentidos ainda sem check-in. | 1) Entre como associado sem reserva. 2) Escolha ponto, trajeto e poltrona. 3) Confira somente Alterar escolha. 4) Abra o embarque pelo motorista e confira Ler QR Code. 5) Confirme o check-in: Escolher/Alterar desaparecem para aquele sentido. 6) Tente alterar por outra sessão: o servidor deve recusar. |
| **5. Vínculos** | Backend filtra motorista/fiscal por vínculo; fiscal não vê nem assume viagem sem atribuição. Viagens agendadas acompanham motorista, fiscal e ônibus configurados no painel. Histórico e operação iniciada preservam responsáveis; mudanças durante operação usam Intervir. Troca de ônibus da rota com reservas agendadas exige liberar as reservas. | 1) Vincule A ao motorista/fiscal A e B aos de B. 2) Entre nos quatro perfis e confira somente suas viagens. 3) Antes do início, troque o vínculo no web e atualize o app: o antigo perde acesso e o novo recebe a viagem. 4) Tente URL/ID de outra viagem: deve ser recusado. 5) Em operação, altere responsável pela intervenção administrativa e confira o acesso. |
| **6. Abertura e fechamento do check-in** | Mantido: INICIAR ROTA abre embarque de ida; INICIAR VIAGEM fecha para todos. QR diário, idempotência, validação da janela e fila offline preservados. | 1) Antes de iniciar a rota, confira que QR não está liberado. 2) Inicie a rota pelo motorista; fiscal obtém QR e associado com escolha vê Ler QR Code. 3) Confirme um embarque. 4) Inicie a viagem e tente outra leitura: o servidor deve recusar por embarque encerrado. 5) Repita o fluxo da volta após chegada. |
| **7. Uma ida e uma volta por dia** | Validação transacional por pessoa/dia/sentido, inclusive em requisições simultâneas. Ida e volta em A bloqueiam B; somente ida em A permite somente volta em B, e vice-versa. Conflitos explicam o motivo e preservam a reserva anterior. Cancelar/alterar libera os sentidos removidos. Vagas por sentido evitam esconder uma volta disponível quando a ida está lotada. | 1) Reserve ida e volta em A e tente ida/volta em B: ambas bloqueadas, com explicação. 2) Altere A para só ida e reserve volta em B: deve funcionar. 3) Inverta os sentidos e repita. 4) Cancele a escolha e confira os sentidos livres novamente. 5) Confirme a ida e tente nova ida em B: deve falhar. 6) Com ida de B lotada e volta livre, escolha somente volta em B. |

## 3. Validação executada

- Backend SQLite: **200 testes aprovados**, 48,118 s, base temporária.
- Backend PostgreSQL: **200 testes aprovados**, 62,533 s, schema isolado removido ao término.
- Casos incluem concorrência entre pessoas pela mesma poltrona e da mesma pessoa em dois ônibus, preservação da reserva em conflito, troca/cancelamento de sentidos, permissões, janela do QR, GPS, relatórios/PDF, redefinição de senha e cascata de inativação.
- A intervenção de fiscal preserva embarques, horários e etapa; o fiscal anterior perde acesso e o novo passa a gerar QR dentro da mesma janela. Para executar: Operação → Intervir → Alterar fiscal da viagem → selecionar fiscal ativo e informar motivo. Em viagem ainda agendada, altere os vínculos no cadastro da rota/ônibus.
- Flutter: **33 testes aprovados**, incluindo widgets, API, fila offline e GPS com permissões/posições simuladas. Análise estática sem ocorrências. Capturas dos estados de escolha e da volta disponível com ida lotada conferidas visualmente.
- Flutter web recompilado em `build/web`, base `/app/`; estáticos do Django atualizados.
- Android debug compilado em `build/app/outputs/flutter-apk/app-debug.apk`. O endereço padrão é do emulador Android (`http://10.0.2.2:8000/`); para telefone físico, gere com `--dart-define=API_URL=ENDERECO_ACESSIVEL_DO_SERVIDOR`.
- Navegador com banco exclusivamente fictício: relatório filtrado por ônibus/RUA/ponto, download real do PDF, data automática dos embarques, confirmação de inativação, filtros iguais, formulário de senha, Gestão/Pontos e destaque de Operação.
- GPS no navegador: uma posição fictícia de 35 m enviada pela API apareceu em Acompanhar viagens, com horário, círculo de precisão e aviso de posição aproximada. Isso comprova a integração de exibição; não representa uma medição em aparelho real.
- PDF baixado: três páginas renderizadas e conferidas visualmente, sem sobreposição; RUA e ponto presentes.

## 4. Arquivos alterados

Os caminhos abaixo são relativos a `D:/Projetos/tcc-ChatGPT/tcc_project_unicap`. A relação separa fontes/testes de arquivos gerados.

### tcc-web

```text
tcc-web/embarques/tests.py
tcc-web/embarques/test_v4.py
tcc-web/embarques/views.py
tcc-web/embarques/templates/embarques/presencas.html
tcc-web/gestao/revisao.py
tcc-web/gestao/tests.py
tcc-web/gestao/test_v4.py
tcc-web/gestao/test_correcoes_painel.py                         [novo]
tcc-web/gestao/templates/gestao/detalhe.html
tcc-web/gestao/templates/gestao/painel.html
tcc-web/gestao/templates/gestao/intervir.html
tcc-web/onibus/models.py
tcc-web/onibus/views.py
tcc-web/onibus/templates/onibus/listar.html
tcc-web/onibus/templates/onibus/confirmar_status.html          [novo]
tcc-web/paginas/static/paginas/admin.css
tcc-web/paginas/templates/paginas/base.html
tcc-web/paginas/templates/paginas/filtro_status.html            [novo]
tcc-web/relatorios/forms.py
tcc-web/relatorios/services.py
tcc-web/relatorios/views.py
tcc-web/relatorios/pdf.py
tcc-web/relatorios/tests.py
tcc-web/relatorios/templates/relatorios/painel.html
tcc-web/relatorios/static/relatorios/relatorios.css
tcc-web/rotas/api_v3.py
tcc-web/rotas/mapa.py
tcc-web/rotas/models.py
tcc-web/rotas/operacao.py
tcc-web/rotas/test_operacao.py
tcc-web/rotas/test_correcoes_operacao.py                        [novo]
tcc-web/rotas/views.py
tcc-web/rotas/templates/rotas/listar.html
tcc-web/rotas/templates/rotas/mapa.html
tcc-web/rotas/static/rotas/mapa.js
tcc-web/usuarios/views.py
tcc-web/usuarios/test_acesso_v3.py
tcc-web/usuarios/templates/usuarios/listar.html
tcc-web/usuarios/templates/usuarios/redefinir_senha.html        [novo]
tcc-web/usuarios/templates/usuarios/senha_acesso.html
```

### tcc-Flutter (raiz)

```text
lib/login.dart
lib/services/api_service.dart
lib/services/fila_offline.dart
lib/services/rastreamento.dart
lib/screens/viagens.dart
lib/screens/associado/fluxo.dart
lib/screens/motorista/viagem.dart
lib/ui/mapa_viagem.dart
lib/screens/alterar_senha.dart                                 [removido]
test/widget_test.dart
test/rastreamento_test.dart                                   [novo]
```

### Documentação e resultados gerados

```text
README.md
LEIA-ME-PRIMEIRO.md
MODULO_4.md
docs/VALIDACAO.md                                              [nota para esta revisão]
docs/CORRECOES_2026-10-26.md                                   [novo]
scripts/gerar_previas.py
docs/previas-mobile/index.html e capturas                      [atualizados]
docs/previas-mobile/15-alterar-senha.png                        [removido; substituído pelo menu só Sair]
docs/previas-web/correcoes-20261026/*.png                       [novos]
build/web/                                                    [compilação atualizada]
build/app/outputs/flutter-apk/app-debug.apk                    [compilação atualizada]
tcc-web/staticfiles/                                          [collectstatic]
```

## 5. Limites e pendências

**Web 6 — causa original do erro de PDF:** não foi reproduzida. O download atual funciona nos testes HTTP, com dados reais consultados somente em leitura e pelo navegador com dados fictícios. A consistência dos filtros foi corrigida; não é possível atribuir o erro anterior a uma causa específica sem seu traceback/ambiente original.

**Mobile 3 — validação física:** permissões, captura, envio, recepção e mapas foram corrigidos e cobertos por testes; GPS real, continuidade em segundo plano/restrições de bateria e câmera física precisam ser conferidos em aparelho. Não houve teste de deslocamento real nem compilação iOS neste Windows. O APK debug valida a compilação Android; não é uma publicação de produção.

As demais alterações solicitadas estão implementadas. Não houve publicação em servidor/loja. Para usar o código local, reinicie backend e aplicativo com os iniciadores existentes. Para dispositivo físico, configure um endereço de API acessível e use HTTPS no navegador para permitir câmera/localização.

## Evidências

- [Galeria mobile](previas-mobile/index.html)
- [Relatórios e ações agrupadas](previas-web/correcoes-20261026/relatorios.png)
- [Data automática dos embarques](previas-web/correcoes-20261026/embarques.png)
- [Confirmação de inativação](previas-web/correcoes-20261026/inativar-onibus.png)
- [Redefinição de senha](previas-web/correcoes-20261026/redefinir-senha.png)
- [Operação com menu ativo](previas-web/correcoes-20261026/operacao-menu.png)
- [Pontos de embarque no menu](previas-web/correcoes-20261026/pontos-menu.png)
- [GPS recebido pela API e exibido no mapa — posição fictícia](previas-web/correcoes-20261026/mapa-gps.png)

Logs do backend: `tmp/testes-correcoes-20261026-sqlite.log` e `tmp/testes-correcoes-20261026-postgres.log`. Logs de compilação: `tmp/flutter-build-correcoes-20261026.log` e `tmp/flutter-build-android-correcoes-20261026.log`.
