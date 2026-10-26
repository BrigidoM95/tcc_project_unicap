# Validação — versão 4 de 18/10/2026

Este documento conserva a validação da entrega de 18/10. A validação das correções posteriores está em [CORRECOES_2026-10-26.md](CORRECOES_2026-10-26.md).

## Resultados finais

| Verificação | Resultado |
|---|---|
| Backend SQLite | **156 testes aprovados**, 31,295 s. Base de teste separada. |
| Backend PostgreSQL | **156 testes aprovados**, 41,359 s. Schema aleatório isolado, sem public no search_path, removido ao terminar. |
| Flutter | **22 testes aprovados**: API, JWT/cache, fila offline/GPS, login e telas dos três perfis. |
| Análise Flutter | Sem ocorrências. |
| Build Flutter web | Release concluída em `build/web`, base `/app/`, sem CDN de recursos. |
| Migrações de modelos | `makemigrations --check --dry-run`: nenhuma alteração pendente. |
| Ensaio de migração | Cinco migrações v4 aplicadas numa cópia nova; 27 tabelas comparadas, integridade e chaves estrangeiras válidas. |
| Migração real | **Cinco migrações aplicadas após autorização.** Sem pendências; `check` e `makemigrations --check --dry-run` aprovados. |
| Banco real e backup final | 29 tabelas comparadas diretamente, incluindo horários; integridade e chaves estrangeiras válidas. |
| Páginas após migração | Onze páginas renderizadas com status 200 na base real; consultas em transação somente de leitura. Instituições ativas conferidas no formulário. |
| Utilitário de backup | Um teste adicional de regressão aprovado: cópia fiel de todas as tabelas e arquivo de origem inalterado. |
| Estáticos | `collectstatic`: 3 arquivos atualizados, 171 preservados e 440 processados. |
| Revisão mobile | 29 capturas regeneradas. Mapas de 16/46 lugares sem rolagem em 390 × 844; motorista também verificado em 360 px. |
| Revisão web | Navegador local com base exclusivamente fictícia: visão geral, nova instituição selecionável no cadastro, embarques por sentido e busca de frequência por RUA. Capturas em `docs/previas-web`. |

Ambiente: Windows, Python 3.14.8, Flutter 3.47.7 e Dart 3.13.5. Não foi produzido um APK novo nesta revisão; eventual APK anterior não representa a v4. Não houve publicação em servidor ou loja.

## Cobertura relevante

O backend cobre os horários 07:59/08:00, abertura antecipada pelo motorista, persistência após dez minutos, escolha de ida/volta, colisão de poltrona, pontos inválidos/inativos, troca entre ônibus, cancelamento, fim da ida, retorno antecipado, apenas volta, origem online/offline, justificativas manuais, reserva do próprio associado vista pelo fiscal e auditoria.

Também cobre exclusividade transacional, autenticação e acesso por perfil, GPS, geração/encerramento das viagens, remoção de campos/telas, senha gerada sem troca obrigatória, instituição/curso, paginação de embarques, indicadores distintos e filtros de frequência no HTML/PDF.

O teste de migração comprova que uma reserva já vencida continua vencida, enquanto uma vigente é adaptada para a virada das 03:00. O ensaio compara os valores das colunas comuns das tabelas preservadas; `expira_em` é excluído do hash por sofrer adaptação intencional, coberta pelo teste. Tabelas internas de migrações, permissões e tipos de conteúdo também são excluídas. As únicas tabelas de domínio removidas são as previstas para matrícula anual e fechamento mensal.

Os testes Flutter verificam pontos obrigatórios mesmo com GPS, mapa completo, horário de abertura no fuso da operação, bloqueio após partida mesmo com ônibus cheio, tela do QR, fila pendente/confirmada/recusada e login direto. A câmera é simulada; a imagem de erro de permissão na prévia não é um teste óptico.

## Evidências locais

- `tmp/testes-v4-completos.log`
- `tmp/testes-postgres-v4.log`
- `tmp/flutter-analyze-v4-final.log`
- `tmp/flutter-test-v4.log`
- `tmp/flutter-build-v4.log`
- `tmp/migracao-copia-v4-final.log`
- `tmp/v4-validacao-final.validacao.json`
- [Galeria mobile](previas-mobile/index.html)
- [Instituição recém-criada no cadastro](previas-web/v4-instituicao-no-cadastro.png)
- [Visão geral](previas-web/v4-visao-geral.png)
- [Embarques](previas-web/v4-embarques.png)
- [Frequência filtrada](previas-web/v4-frequencia.png)

## Conferência do banco real e correção do backup

A migração foi aplicada às 23:26 UTC de 18/10/2026 após a confirmação do usuário. Contas e perfis existentes foram conservados. A cópia final é `backups/v4/aplicacao-real/depois-v4-verificado.sqlite3`; os relatórios `verificacao.json` e `integracao.json` registram a comparação direta de 29 tabelas com o PostgreSQL.

A validação anterior em cópia não detectava dois defeitos do gerador: migrações históricas podiam operar sobre a origem e datas automáticas eram regeneradas somente na cópia. O utilitário foi corrigido para materializar o schema sem executar RunPython e conservar essas datas. O novo teste `scripts/test_backup_portatil.py` passou e verifica também que o hash da origem não muda.

O efeito sobre duas viagens e um check-in foi reparado com base nos registros anteriores de auditoria: viagens 7/8 voltaram a ciclo completo, viagem 8 a `no_destino`, e check-in 1 a `retorno`, sem indicação de legado. Três registros novos documentam o reparo. O comparativo com o backup antigo exclui apenas as datas que aquela versão do utilitário havia regenerado e as adaptações previstas; a conferência final usa a cópia corrigida e inclui todos os campos e horários.

Não foi iniciado o processo contínuo nem executada a manutenção de viagens na base real durante esta conferência; ela ocorrerá normalmente ao iniciar o sistema. A página de operação, que executa essa manutenção, ficou fora das onze consultas somente de leitura.

## Repetir

No diretório `tcc-web`:

```powershell
$env:DB_ENGINE='sqlite'
$env:DJANGO_DEBUG='true'
& ../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
& ../.venv/Scripts/python.exe manage.py test --settings=config.test_settings --noinput
```

Em outro terminal com as variáveis do PostgreSQL configuradas:

```powershell
$env:DB_ENGINE='postgres'
& ../.venv/Scripts/python.exe manage.py test --settings=config.test_postgres_schema --noinput
```

O runner cria e remove somente seu schema temporário. Não aceita `--parallel` nem `--keepdb`. As configurações de teste não devem iniciar o sistema normal.

Na raiz do Flutter:

```powershell
flutter analyze
flutter test --dart-define=CAPTURAR_TELAS=true
flutter build web --no-web-resources-cdn --base-href /app/
& ./.venv/Scripts/python.exe scripts/gerar_previas.py
```

Neste ambiente a ferramenta Flutter foi executada pelo snapshot do SDK, equivalente aos comandos acima, para contornar a espera do script de inicialização por bloqueio de cache. As capturas usam dados fictícios. O teste adicional do backup pode ser repetido com `.venv/Scripts/python.exe scripts/test_backup_portatil.py`.

Para repetir o ensaio de dados, use `scripts/validar_copia_v4.py BACKUP DESTINO_NOVO.sqlite3`, com destino novo dentro do projeto. Não use a base de operação como destino.

## Homologação física

Ainda precisam de teste em aparelho: leitura óptica do QR, permissões, GPS no percurso, tela bloqueada, economia de bateria, perda/recuperação de sinal, sincronização ao reabrir o app e abertura real às 08:00 em America/Campo_Grande. Os limites de precisão GPS, carga de 500 usuários, check-in em dois segundos e disponibilidade dependem de medição em operação.

Docker/HTTPS, restauração do dump em produção, assinatura release e iOS não foram executados nesta revisão. O backup local disponível é uma cópia consistente das tabelas Django com manifesto e mídia, pois pg_dump não está instalado; não inclui roles/extensões externas ao Django.
