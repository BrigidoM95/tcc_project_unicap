# Alinhamento do TCC com a versão 4

Revisão de 18/10/2026. O sistema integra painel Django, API REST e aplicativo Flutter. O administrador mantém cadastros, frota, rotas, operação, relatórios, despesas e auditoria. O motorista conduz um ciclo diário de ida e volta e compartilha GPS. O fiscal apresenta o QR diário, acompanha ocupação e registra exceções justificadas. O associado escolhe trajeto, pontos e poltrona e confirma presença pela leitura do QR.

| Tema | Implementação atual |
|---|---|
| Acesso | E-mail ou RUA persistente 802.NNN; senha gerada permite acesso direto, com troca voluntária. |
| Viagem | Um ciclo por rota/dia, com etapas e horários de ida e volta. |
| Escolha | Abre às 08:00 no fuso da operação, ou antes com início da rota; permanece salva até a partida/encerramento, limitada pela virada das 03:00. |
| Trajeto | Só ida, Só volta ou Ida e volta; a última opção usa a mesma poltrona nos dois sentidos. |
| Retorno | Ida e volta exige ida confirmada; Só volta não exige. Motorista pode iniciar após a chegada, antes do horário previsto. |
| Exclusividade | Poltrona protegida por transação e um check-in válido por pessoa/sentido/dia. |
| Offline | A leitura aguarda validação do servidor e pode confirmar ou ser recusada. |
| GPS | Posições do motorista com fila em lotes; pontos cadastrados não têm coordenadas. |
| Mapas | Trilha GPS observada, sem previsão de chegada calculada a partir dos pontos. |
| Ocupação | Atualizada por consultas periódicas de dois segundos. |
| Histórico | Cancelamento lógico e snapshots preservam comprovação. |
| Relatórios | Frequência com busca e instituição, embarques diários, ocupação por viagem, registros e despesas; exportação PDF. |
| Banco | PostgreSQL e SQLite testados; cinco migrações v4 aplicadas ao banco real após autorização. |

Use as capturas regeneradas em `previas-mobile`, identificadas como dados fictícios. Testes automatizados e revisão visual constam de [VALIDACAO.md](VALIDACAO.md). Piloto, 500 usuários simultâneos, tempo de check-in, precisão GPS e bateria só devem ser apresentados como resultados após medição real. Hospedagem e publicação nas lojas não foram realizadas nesta revisão.
