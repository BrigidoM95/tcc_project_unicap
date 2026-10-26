# UNICAP — versão 4 com correções de 26/10/2026

Atualização de 18/10/2026, baseada nos documentos funcionais, nos mockups dos três perfis e nos Prompts de Implementação v4 de 17/10/2026.

As correções solicitadas em 26/10 estão descritas em [CORRECOES_2026-10-26.md](docs/CORRECOES_2026-10-26.md), com arquivos alterados e testes manuais por item. Elas não exigem novas migrações. Reinicie o backend e o aplicativo para carregar a versão atualizada.

## Situação da atualização

Código, testes e compilação web atualizados. **As cinco migrações v4 foram aplicadas ao PostgreSQL real em 18/10/2026, após autorização.** Não há migrações pendentes. Os estáticos foram atualizados e onze páginas foram conferidas com a base real, em transação somente de leitura.

A cópia final `backups/v4/aplicacao-real/depois-v4-verificado.sqlite3` foi comparada com as 29 tabelas Django da base real, incluindo os horários. O utilitário de backup recebeu uma correção; os detalhes e o reparo comprovado pela auditoria estão em `docs/VALIDACAO.md`.

Os backups desta revisão estão em `backups/v4/`. A lista de mudanças e migrações está em [ALTERACOES_V4.md](docs/ALTERACOES_V4.md); os resultados, em [VALIDACAO.md](docs/VALIDACAO.md).

## Iniciar o projeto

1. Abra `INICIAR_WEB_WINDOWS.cmd` e mantenha a janela aberta. O processo de geração e encerramento de viagens acompanha o backend.
2. Abra `INICIAR_APP_WINDOWS.cmd` em outra janela.
3. Acesse o painel em <http://127.0.0.1:8000/> e o aplicativo em <http://localhost:8080/>.
4. Complete as pendências indicadas na visão geral usando as informações corretas da associação.

Neste computador o ambiente Python é `.venv`. Os iniciadores também reconhecem `tcc-web/venv` quando disponível em outras instalações.

O aplicativo aceita e-mail ou RUA e senha, exigidos a cada nova sessão. O RUA persistente tem formato `802.NNN`; identificadores anteriores continuam reconhecidos. A senha inicial gerada no cadastro continua disponível. Para redefinir a senha, o administrador abre Usuários → Redefinir senha, informa uma senha de pelo menos oito caracteres e a confirma. O aplicativo oferece apenas Sair no menu da conta; não permite alterar senhas.

## Preparar os cadastros

Cadastre instituições, cursos e pontos; em seguida, usuários, motorista, ônibus e rota. Todas as instituições ativas aparecem no cadastro de usuário, mesmo quando ainda não têm cursos. Nesse caso, o formulário informa a ausência e mostra o caminho para cadastrar um curso. Para vincular um associado, selecione uma instituição e um curso dela.

Na rota, informe destino, dias, horários, instituições atendidas, fiscal e pontos em ordem para ida e volta. Motorista e fiscal acessam somente as viagens vinculadas a eles. Vínculos de viagens agendadas acompanham o painel; durante a operação, use a intervenção administrativa. Os pontos têm nome/endereço e não exigem coordenadas. O GPS é obtido do motorista durante a operação. A capacidade máxima permanece em 46 lugares.

## Fluxo diário

1. O serviço gera uma viagem por rota e dia operacional, com ida e volta no mesmo ciclo.
2. A escolha abre às **08:00 no fuso America/Campo_Grande**, ou antes se o motorista já iniciou a rota. Esse horário pode ser configurado por `RESERVA_ABRE_AS`.
3. O associado escolhe **Só ida**, **Só volta** ou **Ida e volta**, os pontos de cada sentido e a poltrona. Quando existe apenas um ponto, ele é selecionado automaticamente. Ida e volta usam a mesma poltrona, que precisa estar livre nos dois sentidos.
4. A escolha permanece salva, sem expiração após cinco minutos. Seu limite é a virada operacional das 03:00, mas o início de cada viagem fecha a escolha e o check-in daquele sentido. Escolher uma poltrona não confirma presença.
5. Após o motorista abrir o embarque e o fiscal assumir, o associado lê o QR Code diário. A resposta do servidor confirma o check-in. Sem internet, a leitura aparece como pendente até ser sincronizada.
6. O fiscal acompanha a lista, registra exceções manualmente com poltrona, ponto e motivo e, quando estudante, registra o próprio embarque com justificativa.
7. **Iniciar viagem** fecha a ida. **Finalizar viagem** registra a chegada e abre o embarque da volta. O motorista pode **Iniciar caminho de volta** após a chegada, inclusive antes do horário previsto. A última finalização encerra o ciclo e o GPS.
8. Quem escolheu **Ida e volta** precisa confirmar a ida para manter o direito à volta dessa escolha. **Só volta** dispensa embarque anterior na ida.

O servidor garante exclusividade da poltrona, uma reserva de ida e uma de volta por pessoa/dia, e no máximo um check-in válido por sentido. Para trocar de ônibus, cancele a escolha anterior ou remova dela o sentido desejado. Ida no ônibus A e volta no B são permitidas; ida e volta no A bloqueiam ambos os sentidos no B. Após o check-in, o sentido confirmado fica bloqueado. Cancelamentos preservam histórico e justificativa. Leituras offline usam o instante da leitura e continuam sujeitas à validação da janela e da ocupação.

Mantenha o processo de operação em execução. Ele encerra viagens esquecidas após as 03:00 com indicação de revisão.

## Instalação nova

Requer Python 3.12 ou superior e Flutter com os SDKs de destino. Execute `INSTALAR_WINDOWS.cmd` e consulte [IMPLANTACAO.md](docs/IMPLANTACAO.md). Em base vazia, crie o primeiro administrador:

```powershell
.\.venv\Scripts\python.exe tcc-web\manage.py createsuperuser
```

Para uma base separada de demonstração, com `DEBUG=true`, use `criar_demonstracao`. O comando solicita uma senha e recusa bases com usuários. Não o execute na base usada pela associação.

Veja as [prévias mobile](docs/previas-mobile/index.html), os [resultados dos testes](docs/VALIDACAO.md) e o [alinhamento do TCC](docs/ATUALIZACAO_TCC.md). Para reverter uma atualização, restaure código, banco e fotos compatíveis entre si.
