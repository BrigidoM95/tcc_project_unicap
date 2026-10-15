# Validação da entrega — 12/10/2026

## Verificações executadas

| Verificação | Resultado e alcance |
|---|---|
| Django | 99 testes aprovados, incluindo autenticação, permissões, viagens, GPS, matrícula anual, check-in, duplicidade, lotação, histórico, relatórios, PDF, despesas e auditoria. |
| Flutter | 13 testes aprovados: login, widgets, sessão, renovação concorrente de token, cache de consulta, logout e falha de rede no check-in. |
| Análise Flutter | `flutter analyze`: nenhuma ocorrência. |
| Flutter Web | Compilação release concluída com Flutter 3.38.1 / Dart 3.10.0. Renderizador e fontes distribuídos localmente. |
| Migrations | Modelos sem alterações pendentes; banco original atualizado sem perda nas contagens conferidas. Repetição de migrate concluída sem novas alterações. |
| Backup SQLite | Arquivo gerado, banco extraído e `PRAGMA integrity_check` aprovado; contagens iguais às da origem. |
| Configuração Django | `check`, `check --deploy` com configuração de produção e `collectstatic` concluídos. |
| Painel no navegador | Home, mapa, gestão, matrículas, auditoria, cadastro de usuários/ônibus e relatórios carregaram. Telas verificadas em computador e telas selecionadas em 390 × 844, sem transbordamento horizontal nos resultados registrados. |
| Aplicativo no navegador | Login do motorista, início de viagem, localização simulada enviada à API, mapa, login fiscal, QR, login associado, check-in manual e consulta ao histórico executados. |
| Integração com relatório | O embarque feito pela interface apareceu no relatório administrativo e a exportação PDF respondeu corretamente. |

As contagens da cópia original permaneceram: 3 contas de autenticação, 1 perfil cadastrado, 1 ônibus, 1 rota, 6 viagens e 0 check-ins. As validações funcionais no navegador usaram outra base, com dados fictícios.

O mapa do navegador foi verificado com geolocalização simulada e respostas locais para as imagens da camada cartográfica. Isso verifica marcadores, interface e integração com a API; não é homologação do serviço externo de mapas nem de GPS/câmera físicos. O código manual foi testado pela interface; leitura óptica de QR precisa de aparelho e câmera reais.

Ambiente do backend: Python 3.12.14, Django 6.0.5, Django REST Framework 3.18.0 e SQLite. PostgreSQL/Docker não foram executados neste ambiente. O projeto inclui configuração de implantação e workflow de CI com PostgreSQL; esse workflow ainda precisa rodar no repositório.

## Executar os testes no seu computador

Na raiz do projeto, após instalar:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe tcc-web\manage.py test --settings=config.test_settings --noinput
flutter analyze
flutter test
flutter build web --no-web-resources-cdn --base-href /app/
```

Use o comando com `config.test_settings` somente para testes. Ele utiliza hash de senha rápido e cache temporário para os testes; não é configuração de execução normal ou produção. Os testes do Django criam um banco de testes separado.

## Homologação com a associação

Antes do piloto de um ônibus e aproximadamente dez pessoas:

1. Instale em servidor HTTPS e execute a suíte também no PostgreSQL escolhido.
2. Confira cadastros, perfis, telefones, motorista vinculado, matrícula anual, capacidade e pontos com coordenadas corretas.
3. Faça o fluxo de ida e retorno em aparelhos físicos, incluindo câmera, código manual, GPS, permissões negadas e recuperação de rede.
4. Verifique bloqueios de duplicidade e lotação com tentativas simultâneas no servidor do piloto.
5. Compare lista do fiscal, histórico do associado, relatório e PDF com os embarques reais.
6. Verifique backup agendado e restaure uma cópia em ambiente separado.
7. Meça tempo de resposta, precisão GPS e consumo de bateria no percurso; registre ocorrências para correção.

Requisitos quantitativos do TCC — 500 usuários simultâneos, até 2 segundos por check-in, 99% de disponibilidade e precisão de GPS de 10 metros — não foram comprovados por esta validação. Não devem ser apresentados como resultados já alcançados.

A compilação Android, a compilação iOS, a assinatura/publicação em lojas e a hospedagem em domínio real continuam dependentes dos ambientes e contas correspondentes. O GPS desta versão depende de manter o painel do motorista ativo; rastreamento em segundo plano não foi implementado.
