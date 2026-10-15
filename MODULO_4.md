> Registro histórico da entrega parcial do Módulo 4. Para instalar a versão consolidada, siga LEIA-ME-PRIMEIRO.md e docs/VALIDACAO.md.

# Módulo 4 — Gerenciamento de Embarque

Implementação integrada ao Módulo 3. Cada embarque pertence a uma viagem, com sentido de ida ou retorno. Não é necessário recriar usuários, ônibus ou rotas existentes.

## Instalar no Windows (PowerShell)

1. Faça uma cópia de segurança da pasta atual, principalmente `tcc-web/db.sqlite3` e arquivos de mídia. Feche os servidores antes de trocar os arquivos.
2. Extraia este projeto para uma pasta nova fora do OneDrive. O pacote não inclui ambientes virtuais, histórico Git, builds ou cache do navegador. O banco e a mídia enviados foram mantidos sem alterações. Se o banco do seu PC estiver mais atualizado, use a sua cópia em vez do banco do pacote.
3. Na raiz extraída, inicie o backend:

```powershell
cd tcc-web
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

Caso a política do PowerShell bloqueie a ativação, use diretamente `.\venv\Scripts\python.exe -m pip install -r requirements.txt` e substitua `python` por `.\venv\Scripts\python.exe` nos comandos seguintes.

4. Abra outro terminal na raiz do projeto Flutter:

```powershell
flutter pub get
flutter analyze
flutter test
flutter run -d chrome --web-port 5000
```

O backend continua em `http://127.0.0.1:8000/`. Use o frontend em `http://localhost:5000/`. Para uso em celulares, ajuste o IP em `lib/services/api_service.dart` e a configuração de hosts/CORS do Django conforme seu ambiente. A câmera no navegador depende de permissão e contexto seguro (localhost ou HTTPS). O fluxo com código colado permite testar mesmo sem câmera.

## Demonstrar com dois perfis

1. No painel administrativo, tenha um motorista, um fiscal e pelo menos dois associados ativos. O ônibus deve estar ativo e vinculado ao motorista; a rota também deve estar ativa.
2. Entre no aplicativo como motorista e inicie uma viagem de ida ou retorno, usando a tela existente do Módulo 3.
3. Em outro navegador ou janela anônima, entre como fiscal. Na Home, clique em **Gerenciar embarque** ou no menu de embarques no topo. Escolha a viagem.
4. O fiscal apresenta o QR Code gerado. Ele dura cinco minutos. **Gerar novo QR Code** invalida imediatamente o anterior. A tela atualiza vagas e presenças a cada 15 segundos.
5. Em outra janela, entre como associado. Abra **Fazer check-in** (ou o menu do topo), permita a câmera e leia o QR. Alternativamente, copie o texto `UNIBUS:M4:...` exibido pelo fiscal e cole no campo.
6. A confirmação apresenta nome, RUA, ônibus, placa, rota, sentido e horário. **Meus embarques** mostra o histórico do próprio associado.
7. Como administrador, acesse **Embarques** na Home web ou `/embarques/`, e filtre por viagem.
8. Finalize a viagem pelo motorista. O QR Code deixa de permitir embarques. Uma nova viagem de retorno admite novo check-in do mesmo associado.

## Regras implementadas

- Identidade vem do usuário autenticado via JWT. O cliente não escolhe o associado do registro.
- Somente fiscais ativos geram QR; somente associados ativos fazem check-in.
- Token aleatório UUID, validado no servidor, com validade de cinco minutos. O QR não contém nomes, senhas ou JWT.
- Viagem em andamento, rota e ônibus ativos são obrigatórios. O fiscal emissor também deve continuar ativo.
- Um check-in por associado por viagem, protegido também por restrição única no banco.
- Vagas calculadas pela capacidade cadastrada do ônibus e pelos embarques confirmados da viagem.
- Cada registro ocupa uma vaga interna única. Essa vaga é controle de capacidade, não reserva de assento numerado.
- Transação iniciada por escrita na viagem serializa embarques; restrições únicas impedem reutilização da mesma vaga. SQLite pode responder “Sistema ocupado” em concorrência; confira o histórico e repita. PostgreSQL utiliza bloqueios de linha.
- Nome, RUA, código e placa são copiados para o registro para manter a identificação original mesmo após alterações cadastrais.
- Histórico do associado limitado aos 100 embarques mais recentes. Consulta administrativa mostra até 500 registros e lista as 200 viagens mais recentes no filtro.
- Fiscal consulta as presenças da viagem cujo QR atual foi gerado por ele. Como não há vínculo fiscal–ônibus no sistema original, qualquer fiscal ativo pode escolher uma viagem disponível. Gerar QR por outro fiscal transfere o controle e invalida o anterior.
- O banco guarda instantes com fuso horário. O aplicativo os apresenta no horário local do dispositivo; o painel web usa o fuso configurado em `TIME_ZONE`.

## Limites e decisões para a apresentação

Mensalidade e advertência não foram adicionadas nem usadas para bloquear embarque: não existe regra formalizada/modelo financeiro no projeto enviado. A geração do QR exige que o motorista tenha iniciado a viagem, conforme o ciclo já existente no Módulo 3. Se a associação desejar abrir embarque antes de iniciar o deslocamento, será necessária uma fase própria de “embarque aberto”.

Este check-in registra a confirmação autenticada via QR. Ele não comprova presença física automaticamente: um QR válido pode ser fotografado e compartilhado durante a validade. A conferência visual pelo fiscal continua necessária. Não foram implementados desembarque, cancelamento, liberação de vagas durante a viagem, localização obrigatória do associado ou reserva numerada de assentos.

Não há atribuição permanente de fiscal ao ônibus; essa regra precisa ser definida antes de limitar o acesso por frota. Presenças de uma viagem finalizada continuam no histórico e no painel administrativo.

## Arquivos principais

- `tcc-web/embarques/`: modelos, APIs, consulta web, administração de leitura, testes e migration `0001_initial.py`.
- `tcc-web/config/settings.py` e `urls.py`: instalação e roteamento do app.
- `tcc-web/requirements.txt`: Pillow acrescentado para o campo de foto já existente.
- `tcc-web/paginas/templates/paginas/home.html` e `rotas/templates/rotas/base.html`: acesso às presenças.
- `lib/services/api_service.dart`: chamadas de embarque usando o mecanismo de renovação JWT existente.
- `lib/home.dart`: acesso por perfil.
- `lib/screens/fiscal/`: lista de viagens, QR e presenças.
- `lib/screens/associado/`: leitura, confirmação e histórico.
- Android Manifest / iOS Info.plist: declaração de uso da câmera.

## Explicação curta para estudar

“O fiscal seleciona uma viagem ativa e solicita ao Django um código aleatório com validade de cinco minutos. O Flutter converte esse código em QR Code. O associado autenticado lê o QR e envia somente o código para a API. O servidor identifica o associado pelo JWT, confere a sessão, os perfis, a viagem, as vagas e a ausência de duplicidade. Dentro de uma transação, grava a presença com ônibus e horário. O fiscal acompanha os confirmados, o associado consulta seu histórico e o administrador consulta presenças por viagem. Ida e retorno são viagens distintas.”

## Validação desta entrega

- Django 6.0.5, Python 3.14: 42 testes passaram, incluindo 18 testes do Módulo 4.
- `manage.py check` sem problemas; migration do Módulo 4 gerada.
- Migrations iniciais também geradas para os modelos vazios preexistentes `Associado` e `Pagina`, que ainda não tinham migrations, para manter o projeto consistente.
- Código Dart formatado. `flutter analyze`, `flutter test`, build web e uso de câmera real ainda precisam ser executados no seu PC; a inicialização do SDK foi bloqueada neste ambiente. Não considerar o aplicativo validado em dispositivo.
