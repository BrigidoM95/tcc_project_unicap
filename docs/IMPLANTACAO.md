# Instalação, implantação e manutenção

Atualizado em 18/10/2026 (v4). Consulte também `LEIA-ME-PRIMEIRO.md`.

**Atualização local v4 concluída em 18/10/2026:** cinco migrações aplicadas após autorização, estáticos atualizados e base conferida. Em outras instalações, faça um backup novo com o utilitário corrigido e ensaie as migrações antes de atualizar. O instalador e o Compose aplicam migrações automaticamente.

## Desenvolvimento local

`INSTALAR_WINDOWS.cmd` prepara dependências, configuração, backup e migrações. `INICIAR_WEB_WINDOWS.cmd` usa `tcc-web/venv` quando disponível e `.venv` como alternativa. O processo de operação inicia oculto e termina junto com a janela do backend.

Para iniciar manualmente, no diretório `tcc-web` e com o Python do ambiente:

```powershell
python manage.py runserver 127.0.0.1:8000
# Outro terminal, mantido aberto:
python manage.py processar_operacao --continuo
```

Em outro terminal, na raiz:

```powershell
flutter run -d chrome --web-port=8080 --dart-define=API_URL=http://127.0.0.1:8000/
```

`processar_operacao` executa uma passagem; `--continuo` repete a cada 30 segundos. Gera viagens, encerra ciclos esquecidos após as 03:00 sem consolidação mensal. A escolha abre por padrão às 08:00 (`RESERVA_ABRE_AS=08:00`). O fuso padrão da operação é `America/Campo_Grande`, configurável em `DJANGO_TIME_ZONE`.

## Compilação e aparelhos

```powershell
flutter analyze
flutter test
flutter build web --no-web-resources-cdn --base-href /app/
flutter build apk --debug --target-platform android-arm64
```

A pasta `build/web` deve ser servida por HTTP/HTTPS, não aberta por duplo clique. A produção web usa a API na mesma origem quando `API_URL` é omitida. Para outro servidor, acrescente `--dart-define=API_URL=https://SEU_DOMINIO/`; não acrescente `/api/` ao endereço.

No emulador Android, o padrão local aponta para `http://10.0.2.2:8000/`. No celular físico, configure o endereço acessível do servidor. Para teste na rede local, o Django deve escutar `0.0.0.0:8000` e seu IP deve estar em `DJANGO_ALLOWED_HOSTS`. A câmera/GPS do navegador requer HTTPS ou localhost; para piloto, use HTTPS. O modo debug Android permite HTTP apenas para desenvolvimento.

Release Android exige sua chave privada e `android/key.properties`, usando o arquivo de exemplo como referência. Execute `flutter build apk --release --dart-define=API_URL=https://SEU_DOMINIO/`. O identificador configurado é `br.org.unicap.transporte`. Se houver aplicativo já publicado com outro identificador, preserve a identidade/assinatura da publicação antes de distribuir uma atualização.

iOS exige macOS, Xcode e assinatura da equipe Apple. Configure `ios/Runner.xcworkspace`. O projeto declara câmera, localização e modo de localização em segundo plano. Android configura serviço em primeiro plano com notificação durante a viagem. Continuidade com tela bloqueada, restrições de bateria, permissão negada e aplicativo encerrado pelo sistema precisam de teste físico.

## Servidor PostgreSQL com HTTPS

Os arquivos em `deploy/` preparam PostgreSQL, Django/Gunicorn, Caddy, operação e backup. Requerem Docker Compose em servidor Linux, domínio apontado e portas 80/443 acessíveis. Esta revisão não criou servidor ou publicou um domínio.

1. Compile o web e disponibilize código e `build/web` no servidor.
2. Execute `python3 scripts/configurar.py --producao`. Revise `deploy/.env` sem compartilhar seus segredos.
3. Inicie:

```bash
cd deploy
docker compose config --quiet
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py check --deploy
docker compose ps
```

O serviço web aplica migrações e coleta estáticos. `operacao` executa a manutenção contínua e depende da saúde do web. Caddy publica painel `/`, aplicativo `/app/` e saúde `/health/`. O banco não publica porta na internet. O SSL desabilitado entre contêineres aplica-se apenas à rede interna; banco externo exige a configuração do provedor.

Em atualização, preserve código, banco, fotos e `.env`. Faça backup antes de migrar. Confirme cadastros mínimos das rotas. Não crie demonstração numa base real.

## Backup local e restauração

Na raiz, usando o ambiente instalado:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py backup_antes_atualizacao --destino backups
```

SQLite usa a API de backup e inclui fotos. PostgreSQL utiliza `pg_dump` quando encontrado. Sem esse utilitário, a instalação local gera uma cópia consistente das tabelas Django em SQLite com manifesto/hash e um ZIP das fotos. O destino dessa alternativa deve ficar dentro do projeto. Ela conserva PKs, relações e hashes de senha, mas não é um backup completo de roles, extensões ou tabelas externas ao Django. Guarde os arquivos de forma privada.

A cópia portátil pode ser aberta configurando `DB_ENGINE=sqlite` e `SQLITE_PATH` para uma cópia do arquivo. Para retornar a PostgreSQL, ensaie exportação/importação em base vazia. Não execute importação por cima de uma base em uso. Para restaurar um dump completo, use `pg_restore` numa base vazia compatível e restaure as fotos correspondentes. Preserve o estado atual até verificar a restauração.

Para reversão de versão, código, banco e fotos devem corresponder à mesma revisão. Restaurar apenas código antigo sobre banco migrado não é um procedimento de recuperação.

## Backup de produção

O serviço `backup` produz dump PostgreSQL e arquivo de fotos a cada 24 horas em `deploy/backups`, remove arquivos completos com mais de 30 dias e tenta uma restauração por mês em um banco temporário de nome próprio. Após restaurar, consulta as migrações e remove somente essa base temporária. O usuário do serviço precisa de permissão para criar essa base; falhas ficam nos logs.

Valide agendamento, retenção, restauração e cópia externa após implantar. Backup no mesmo servidor não cobre perda do servidor. Para restauração operacional, pare `web`, `operacao` e `backup` e preserve o estado atual antes de restaurar em uma base separada.

Agende também `python manage.py flushexpiredtokens`. Defina com a associação a retenção de auditoria e localização.

## Mapas

O painel conserva Leaflet e o aplicativo usa flutter_map, com atribuição OpenStreetMap visível. O backend permite `MAP_TILE_URL`, `MAP_ATTRIBUTION` e `MAP_ATTRIBUTION_URL` no `.env`; o Flutter recebe `MAP_TILE_URL` por `--dart-define` na compilação. Ao trocar provedor, ajuste sua atribuição conforme os termos correspondentes.

O desenho mostra o percurso GPS observado. Pontos cadastrados têm nome/endereço, sem coordenadas. O app recebe uma amostra de até aproximadamente 400 posições, preservando o histórico completo no banco. Previsão de chegada e passagem por pontos não são calculadas. Sem dados de localização, o mapa informa que aguarda GPS. Não há download em massa ou promessa de cartografia offline.
