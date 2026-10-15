# Instalação, servidor e manutenção

## Execução local manual (Windows)

A partir da raiz, como alternativa aos arquivos CMD:

```powershell
py -3 scripts\instalar_local.py
.\.venv\Scripts\python.exe tcc-web\manage.py createsuperuser
.\.venv\Scripts\python.exe tcc-web\manage.py runserver
```

Em outro terminal:

```powershell
flutter pub get
flutter run -d chrome --web-port=8080 --dart-define=API_URL=http://127.0.0.1:8000/
```

Não execute demonstração e criação de superusuário nessa sequência no mesmo banco novo: escolha uma das opções do guia. Não use `runserver` em produção.

## Celular na mesma rede

O endereço 127.0.0.1 no celular refere-se ao próprio celular. Para acessar um backend no PC, configure o IP real do PC em `DJANGO_ALLOWED_HOSTS` e `DJANGO_CORS_ORIGINS` (origem completa do aplicativo), e inicie `runserver 0.0.0.0:8000`. Não use `*` para resolver hosts em produção.

Câmera e geolocalização pelo navegador exigem contexto seguro: HTTPS ou localhost no mesmo aparelho. Acessar um IP da rede com HTTP pelo celular pode permitir login e código manual, mas impedir câmera/GPS. Para o piloto com aparelhos físicos, utilize o servidor HTTPS descrito abaixo.

O aplicativo permite `--dart-define=API_URL=https://SEU_DOMINIO/` em execução e compilação. Em versão web de produção, se essa opção for omitida, a API usa a mesma origem do aplicativo. Não coloque `/api/` no fim de `API_URL`.

## Compilar Flutter Web

```powershell
flutter pub get
flutter analyze
flutter test
flutter build web --no-web-resources-cdn --base-href /app/
```

Uma compilação desta entrega já está incluída em `build/web`. Recompile com os comandos acima depois de alterar o aplicativo. Publique a pasta inteira. Não abra `index.html` com duplo clique. `--no-web-resources-cdn` inclui o renderizador localmente; as fontes Roboto também estão no pacote, com licença; o mapa continua dependendo do provedor de mapas e de internet.

## Servidor com PostgreSQL e HTTPS

Arquivos preparados para um servidor Linux com Docker e Compose. O domínio deve apontar para o servidor e as portas 80/443 devem estar acessíveis. A configuração não compra domínio nem contrata hospedagem.

1. Compile o Flutter conforme acima e envie código e `build/web` ao servidor. Não envie dados fictícios, `.venv`, caches ou um SQLite como se fossem banco de produção.
2. Na raiz, execute `python3 scripts/configurar.py --producao`. Informe seu domínio. Isso cria `deploy/.env` com chave e senha aleatórias; não as compartilhe nem versione.
3. Revise o domínio e as configurações em `deploy/.env`.
4. Execute:

```bash
cd deploy
docker compose config --quiet
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py check --deploy
docker compose ps
```

O contêiner web aplica migrations, coleta arquivos estáticos e inicia Gunicorn. O Caddy configura HTTPS para o domínio. Painel: `https://SEU_DOMINIO/`. Aplicativo: `https://SEU_DOMINIO/app/`. Saúde: `https://SEU_DOMINIO/health/`.

O PostgreSQL não publica sua porta na internet. `POSTGRES_SSLMODE=disable` neste Compose vale somente para a comunicação entre contêineres na rede interna. Para banco gerenciado externo, use o modo SSL exigido pelo provedor e ajuste conexão/rede.

Se seu banco já é PostgreSQL, mantenha suas credenciais e faça um `pg_dump` antes de atualizar. O instalador local interrompe esse caminho deliberadamente porque o backup de SQLite não protege PostgreSQL.

## Levar dados do SQLite para PostgreSQL

Faça primeiro uma migração de ensaio. Interrompa gravações durante a migração final. Use cópia de segurança e não importe por cima de um PostgreSQL em uso.

1. Atualize o SQLite com as migrations desta entrega e confira os dados.
2. Com a configuração apontando para o SQLite atualizado, exporte para arquivo (o `--output` evita problemas de codificação do redirecionamento do PowerShell):

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py dumpdata --natural-foreign --natural-primary --exclude=contenttypes --exclude=auth.permission --exclude=sessions --exclude=admin.logentry --exclude=token_blacklist --exclude=gestao.cacheentry --output=dados-migracao.json
```

3. Aplique migrations num PostgreSQL **vazio**, sem executar demonstração ou criar usuários antes da importação.
4. Importe o arquivo com `python manage.py loaddata /CAMINHO/dados-migracao.json` usando a configuração do destino. No Compose, copie-o com `docker compose cp ../dados-migracao.json web:/tmp/dados-migracao.json` e execute `docker compose exec web python manage.py loaddata /tmp/dados-migracao.json`.
5. Copie `tcc-web/media` para o volume `media` do servidor. Confira permissões de escrita do usuário UID 10001 usado pelo contêiner.
6. Compare quantidades, vínculos, fotos, relatórios e um novo embarque. Todos entram novamente: sessões/tokens antigos não são migrados.
7. Após verificar e preservar o backup privado, remova a cópia de trânsito `dados-migracao.json` do servidor e da pasta do projeto; ela contém dados pessoais e hashes de senha.

Este roteiro precisa de ensaio no servidor escolhido. O relatório de validação distingue os testes locais da implantação que ainda precisa ser executada.

## Backups e restauração

Local SQLite:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py backup_local --destino C:\Backups\UNICAP
```

O comando usa a API de backup do SQLite, inclui `media` e gera um `.tar.gz`. Para restaurar, pare o sistema, extraia em uma pasta temporária, confira `db.sqlite3` e `media`, preserve o estado atual e copie os arquivos para os caminhos corretos. Use o código correspondente ao backup e só então aplique atualizações. Preserve `.env` separadamente, com acesso restrito.

No Compose, o serviço `backup` gera um dump PostgreSQL e um arquivo de fotos a cada 24 horas em `deploy/backups`. Não há exclusão automática de arquivos: acompanhe o espaço em disco, retenção e cópia externa. O backup no mesmo servidor não protege contra perda do servidor.

Para restauração PostgreSQL, pare `web` e `backup`, preserve o estado atual e restaure o dump numa base vazia compatível com `pg_restore --no-owner --dbname=... arquivo.dump`, seguido das fotos do mesmo backup. Verifique contagens e vínculos antes de liberar o acesso. Não use opções de limpeza/exclusão em uma base que ainda precisa preservar.

Faça periodicamente um ensaio de restauração. Valide permissões, agendamento e arquivos gerados após hospedar.

## Matrículas e manutenção

O check-in exige matrícula ativa no ano atual, independentemente de um agendamento. Na virada do ano, renove as matrículas em Gestão. Para registrar o encerramento das antigas e preservar o histórico:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py encerrar_matriculas_antigas
```

Agende no servidor a manutenção `python manage.py flushexpiredtokens` para remover tokens expirados. Auditoria e GPS continuam no banco; defina com a associação o período necessário de retenção e acesso.

## Android e iOS

Android: use Android Studio/SDK e execute `flutter doctor`, depois `flutter run --dart-define=API_URL=https://SEU_DOMINIO/` com aparelho conectado. Para distribuição release, configure `android/key.properties` a partir do exemplo com sua própria chave e execute `flutter build apk --release --dart-define=API_URL=https://SEU_DOMINIO/`. A chave privada não acompanha a entrega. O identificador atual `com.example.aulas_flutter` precisa ser definido antes de publicação em loja; preserve-o se já existe uma versão distribuída com esse identificador.

iOS: requer macOS, Xcode e assinatura da equipe Apple. Abra `ios/Runner.xcworkspace`, configure assinatura e siga o fluxo de compilação Flutter para o aparelho. Permissões de câmera e localização estão declaradas. Binários Android/iOS não foram gerados nesta entrega.

O GPS funciona com o painel do motorista ativo. Ao minimizar/bloquear o aparelho, o envio pode ser pausado. Rastreamento contínuo em segundo plano é uma evolução separada. A precisão é informada pelo dispositivo e exibida no mapa; não há garantia de 10 metros em qualquer condição.

## Mapas

O painel usa Leaflet 1.9.4 distribuído em `rotas/static/rotas/vendor/leaflet`, com licença. O aplicativo usa flutter_map. A camada padrão é OpenStreetMap com atribuição visível. `MAP_TILE_URL`, `MAP_ATTRIBUTION` e `MAP_ATTRIBUTION_URL` permitem trocar o provedor pelo `.env`. Não faça download em massa nem prometa funcionamento offline dos mapas. Para ampliar o piloto, avalie as condições e limites do provedor escolhido.

Os pontos cadastrados são ligados esquematicamente; não há cálculo de melhor caminho ou navegação curva a curva. O traçado do ônibus vem das leituras GPS. O mapa apresenta até 300 posições recentes por viagem, mantendo os registros anteriores no banco.
