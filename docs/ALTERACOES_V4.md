# Alterações da versão 4 — 18/10/2026

Referência principal: UNICAP_Prompts_de_Implementacao_v4.pdf, de 17/10/2026. As especificações e os três cadernos anteriores permanecem como base onde não foram substituídos pela v4. A expansão opcional para 48 não foi aplicada, pois não há confirmação de frota acima de 46 lugares.

## Acesso e cadastros

- Senha gerada com três letras e três números permite acesso direto; retirada da exigência de troca no primeiro login. Mantidas troca voluntária, redefinição e revogação dos tokens.
- Removidos matrícula anual, seus dados contratuais/financeiros e telas correspondentes. A URL antiga retorna 404.
- Ônibus usa ativo/inativo; retirados os campos redundantes de situação, cor, ano, tipo e combustível. Despesas com combustível continuam existindo.
- Retirada a origem da rota e as coordenadas de pontos. Mantidos destino, pontos ordenados e GPS da viagem.
- Corrigido o seletor de instituição: instituições ativas aparecem independentemente de já possuírem cursos. Cursos são filtrados pela instituição; escolhas incompatíveis são recusadas no servidor. Instituição sem curso mostra orientação e link de cadastro.

## Escolha e embarque

- Abertura às 08:00 configurável por RESERVA_ABRE_AS, antecipada se o motorista iniciar a rota. Não depende de já existir fiscal.
- Escolha persistente de trajeto, ponto de cada sentido e poltrona; ida e volta reserva a mesma poltrona nas duas direções de forma atômica.
- Pontos obrigatórios conforme o trajeto; ponto único preenchido automaticamente. GPS não esconde o seletor.
- Troca entre ônibus libera a escolha anterior do mesmo sentido; erros não apagam a escolha válida anterior. Exclusividade e duplicidade protegidas por transações.
- Partida encerra a escolha/check-in do sentido. Ida e volta sem ida confirmada perde a reserva da volta; Só volta permanece válida.
- Chegada abre a volta; partida do retorno não precisa esperar o horário previsto. A virada operacional continua às 03:00.
- Check-in online utiliza ponto e poltrona salvos; offline preserva a validação pelo instante original da leitura. Exceções manuais e embarque do fiscal exigem motivo e geram auditoria.

## Aplicativo

- Escolha com trajeto, pontos e mapa adaptável de 16 a 46 lugares; todos visíveis sem rolagem em 390 × 844.
- Câmera ampliada no QR, leitura automática, cartão da poltrona e troca de escolha. Removidos contador, foto e informações redundantes dessa tela.
- Fluxo do fiscal usa o mesmo mapa para registro manual e mostra corretamente a reserva do associado selecionado.
- Horário de abertura exibido no fuso da operação; ônibus cheio após a partida mostra a mensagem de check-in encerrado.
- Preservados os fluxos do motorista, GPS, fila offline, comprovantes e histórico. Mapas mostram trilha GPS e pontos em texto, sem estimar posições ou chegada a partir dos cadastros.

## Painel web

- Visão geral com cinco atalhos, três indicadores, pendências de associados/rotas e vinte ações em abas de dez.
- Reservas do dia conta pessoas distintas com escolha ou check-in, sem duplicar ida e volta.
- Área de embarque agrupada por viagem/ônibus/sentido, com horário, filtros, ocupação e páginas de cinquenta registros.
- Relatórios preservam indicadores do período, embarques por dia, frequência, ocupação por viagem e registros. Busca e instituição filtram apenas frequência, também no PDF.
- Removidos fechamento mensal e os agrupamentos de utilização por ônibus e pontos. Gestão mantém instituições/cursos, despesas e auditoria.

## Migrações novas

Ordem observada no ensaio do Django (as dependências entre aplicativos são respeitadas automaticamente):

1. `rotas.0008_remove_ponto_latitude_remove_ponto_longitude_and_more`
2. `embarques.0006_reservaassento_ponto_reservaassento_trajeto`
3. `gestao.0004_delete_fechamentomensal`
4. `onibus.0005_remove_onibus_ano_fabricacao_and_more`
5. `usuarios.0007_remove_matriculaanual_matricula_associado_ano_unica_and_more`

Migrações antigas foram preservadas. A migração de reservas reconhece o retorno, preenche ponto quando existe uma única opção e amplia apenas escolhas ainda vigentes; não recupera reservas já vencidas.

## Backup e ensaio

Backup anterior: `backups/v4/codigo-antes-v4-20261018-193959.zip`, cópia consistente `20261018T224003305193Z-dados-django.sqlite3`, manifesto e arquivo de mídia correspondentes. A cópia contém 31 tabelas e 511 registros. Sem pg_dump disponível, o backup de dados é a alternativa portátil das tabelas Django, não um dump completo do servidor PostgreSQL.

`scripts/validar_copia_v4.py` aplicou as migrações numa cópia nova e comparou os valores das colunas preservadas em 27 tabelas, além de verificar integridade e chaves estrangeiras. O campo de expiração das reservas é comparado separadamente pela regra de adaptação; tabelas internas de migrações/permissões não entram no hash. Relatório: `tmp/v4-validacao-final.validacao.json`.

**Banco real: cinco migrações aplicadas em 18/10/2026 após confirmação expressa.** `migrate --check` não aponta pendências; `check` e `makemigrations --check --dry-run` aprovados. Recursos estáticos atualizados. As onze páginas verificadas responderam 200, e as instituições ativas estão disponíveis no cadastro.

Backup imediatamente anterior: `backups/v4/aplicacao-real/20261018T232600391770Z-dados-django.sqlite3`, acompanhado de manifesto e mídia. Cópia final recomendada para a v4: `backups/v4/aplicacao-real/depois-v4-verificado.sqlite3`. As 29 tabelas dessa cópia foram comparadas diretamente com o PostgreSQL real, inclusive todos os horários. Evidências: `verificacao.json` e `integracao.json` na mesma pasta.

### Correção do utilitário de cópia

A conferência posterior identificou que o utilitário antigo executava migrações históricas ao montar o SQLite e que algumas delas usavam implicitamente a conexão de origem. Também regenerava datas automáticas ao inserir a cópia. O utilitário agora cria o schema a partir do estado das migrações sem executar migrações de dados e conserva os valores de `auto_now`/`auto_now_add`. O novo teste de regressão compara todas as tabelas e o hash do arquivo de origem, confirmando que copiar não o altera.

Foram restaurados, com evidência da auditoria anterior, o ciclo das viagens 7 e 8, a etapa `no_destino` da viagem 8 e o sentido `retorno`/classificação atual do check-in 1. As correções têm três registros explícitos de auditoria; nenhum embarque foi removido. A comparação final confirma todos os demais valores preservados. As cópias antigas permanecem como evidência, mas suas datas automáticas não devem ser usadas como referência histórica; a cópia final conserva os horários reais.

## Conferência final

As referências funcionais aos modelos/campos removidos foram retiradas. Seus nomes permanecem nas migrações históricas e novas de remoção, testes que comprovam sua ausência e documentação do que mudou. `CheckIn.origem`, combustível de despesas e coordenadas de `LocalizacaoViagem` continuam, pois têm outra finalidade.

Testes, capturas e limitações estão em [VALIDACAO.md](VALIDACAO.md). As prévias usam dados fictícios. Câmera, GPS e abertura real das 08:00 ainda precisam de homologação em aparelho físico.
