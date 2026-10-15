# UNICAP — sistema integrado de transporte universitário
Entrega consolidada de 12/10/2026 · Alfredo Sanabria e Brigido Mathias

Este pacote reúne o código dos cinco módulos, o painel Django, a API REST e o aplicativo Flutter. Ele substitui o pacote parcial do Módulo 5: não é necessário aplicar os dois. O banco real, as fotos cadastradas e suas senhas não acompanham esta distribuição. Preserve os arquivos do seu projeto anterior conforme a atualização abaixo.

## 1. Abrir no Windows

Pré-requisitos: Python 3.12 ou superior, Flutter 3.38.1 (versão usada nesta validação) e Chrome. Use uma pasta local, por exemplo `C:\UNICAP\tcc_project_unicap`, fora do OneDrive. Não execute os arquivos dentro do ZIP.

1. Extraia o pacote.
2. Se já tem dados, siga a seção 3 **antes** de instalar.
3. Execute `INSTALAR_WINDOWS.cmd`. O instalador cria `.venv`, instala dependências, configura `.env`, faz backup de um SQLite existente e aplica as migrations. Não é necessário ativar o ambiente virtual nem mudar a política do PowerShell.
4. Crie o acesso usando uma das opções abaixo.
5. Abra `INICIAR_WEB_WINDOWS.cmd` e mantenha a janela aberta.
6. Abra `INICIAR_APP_WINDOWS.cmd` em outra janela.

Painel administrativo: http://127.0.0.1:8000/ . Aplicativo: http://localhost:8080/ . O aplicativo usa **e-mail e senha**. O RUA continua sendo o identificador do associado, e não o login desta versão.

### Banco novo: dados fictícios para apresentação

No PowerShell, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py criar_demonstracao
```

Informe uma senha forte quando solicitado. Serão criados quatro acessos que usam a senha escolhida:

| Perfil | E-mail |
|---|---|
| Administrador | administrador@demo.unicap |
| Motorista | motorista@demo.unicap |
| Fiscal | fiscal@demo.unicap |
| Associado | associado@demo.unicap |

O comando cria ônibus, rota, pontos e despesa fictícios. Ele só funciona em banco vazio com `DEBUG=true`; não modifica cadastros existentes. Não gera embarques nem localização simulada automaticamente. Use janelas ou perfis separados do navegador para testar os três papéis ao mesmo tempo.

### Banco novo: começar com cadastros reais

Em vez da demonstração:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py createsuperuser
```

Esse usuário acessa o painel web. Cadastre instituições e cursos em Gestão; depois usuários, motorista, ônibus, rota e pontos. Para novos associados, o cadastro cria a matrícula do ano atual. A tela informa os dados de acesso quando uma senha temporária é gerada. O associado pode alterar sua senha no aplicativo.

## 2. Conferência do fluxo principal

1. Motorista entra no aplicativo e inicia a **ida** de sua rota. Autoriza localização e mantém o painel aberto.
2. Fiscal entra, abre **Gerenciar embarque**, escolhe a viagem e o ponto de embarque. A tela gera QR Code e código manual.
3. Associado entra, toca em **Fazer check-in** e lê o QR ou informa o código manual. O servidor confirma identidade, matrícula do ano, viagem, duplicidade e capacidade.
4. Fiscal confere a lista de presentes e vagas. Associado consulta **Meus embarques** e **Acompanhar viagens**.
5. Administrador abre **Mapa**, **Relatórios** e **Gestão**. Consulta período, frequência, ocupação e pontos; exporta os relatórios em PDF.
6. Motorista finaliza a ida. Para a volta, inicia uma viagem de **retorno**; o fiscal gera outro código.

Uma ida e uma volta são duas viagens e dois embarques válidos. A proteção impede duplicidade **na mesma viagem**. Falta de check-in não é contada automaticamente como falta escolar. Capacidade de assentos significa controle quantitativo de vagas; esta versão não reserva uma poltrona numerada.

## 3. Atualizar o projeto anterior mantendo os dados

1. Pare os servidores Django/Flutter. Faça uma cópia completa da pasta antiga em outro local.
2. Extraia esta entrega em uma **nova pasta**, sem apagar o projeto anterior.
3. Se o projeto anterior utiliza SQLite, copie somente `tcc-web\db.sqlite3` e a pasta `tcc-web\media` para os mesmos caminhos da pasta nova. Caso o SQLite esteja em outro caminho, configure `SQLITE_PATH` no `.env`.
4. Preserve qualquer `.env` antigo em seu backup. Compare-o com `tcc-web\.env.example`: mantenha as credenciais e endereços reais, mas incorpore as novas opções. Não copie `settings.py`, ambientes virtuais, caches nem pastas de build antigas sobre esta entrega.
5. Execute `INSTALAR_WINDOWS.cmd`. Ele também gera um backup de banco e fotos em `backups` antes das migrations. Leia as mensagens; se houver erro, interrompa a abertura do servidor até corrigi-lo.
6. Use os acessos existentes. Não execute `criar_demonstracao` num banco com usuários.
7. Confira usuários, ônibus, rotas, viagens, fotos e relatórios. Faça um embarque de teste identificado como teste.

As migrations são incrementais, inclusive para quem já aplicou o Módulo 5. Os associados existentes recebem um registro inicial de matrícula do ano da migração, seguindo o estado ativo/inativo da conta. Revise a autorização de cada associado antes do uso real. Isso não reconstrói matrículas antigas.

Viagens antigas sem capacidade registrada e embarques antigos sem ponto continuam identificados como dados não registrados. Não se inventa ocupação histórica. A base enviada originalmente tinha seis viagens e nenhum check-in; sem novas presenças, os relatórios de embarque ficam vazios.

Para voltar à versão anterior, pare a nova aplicação e restaure **juntos** o código, o banco e as fotos da cópia anterior. Não substitua só o código depois de migrar o banco.

## 4. Código incluído

| Módulo | Entrega |
|---|---|
| 1 — Usuários | Perfis e permissões, cadastro/edição, inativação, RUA, telefone, instituições/cursos, matrículas anuais, troca de senha e sessão JWT. |
| 2 — Ônibus | Cadastro/edição, capacidade, foto, motorista, estado do veículo e integração com o aplicativo. |
| 3 — Rotas | Rotas, pontos, ida/retorno, início/fim de viagem, envio de GPS e mapa no painel/aplicativo. |
| 4 — Embarque | QR e código manual, ponto informado pelo fiscal, validação do associado e matrícula, duplicidade, lotação, painel fiscal e histórico. |
| 5 — Relatórios | Frequência, embarques, ocupação/vagas, utilização por ônibus, pontos, filtros, gráficos e PDF. |
| Gestão complementar | Despesas dos veículos e PDF, cancelamento com histórico, auditoria, banco PostgreSQL configurável e backups. |

A captura de capacidade no início da viagem preserva a comparação histórica. Inativar cadastros preserva os vínculos com viagens/embarques. O GPS é mostrado apenas para usuários autenticados com perfil permitido.

## 5. Validação e limites de entrega

Veja `docs/VALIDACAO.md` para os resultados verificados e o roteiro de homologação. Veja `docs/IMPLANTACAO.md` para PostgreSQL, domínio, HTTPS, backup e Android/iOS. Veja `docs/ATUALIZACAO_TCC.md` para alinhar a descrição acadêmica ao comportamento implementado.

O código está integrado. A entrega não representa hospedagem já contratada/ativada, aplicativo publicado em loja ou homologação de GPS/câmera em aparelhos físicos. Requisitos de 500 usuários simultâneos, 2 segundos de check-in, 99% de disponibilidade e precisão de GPS de 10 m precisam ser medidos no ambiente real.

Financeiro de mensalidades, pagamentos e integração com carteirinhas externas permanecem fora desta implementação, conforme o planejamento que os tratava como etapa futura. O cadastro de despesas refere-se aos veículos. Para bloquear o embarque de um associado, use sua situação de cadastro/matrícula; não existe conciliação automática de pagamentos.
