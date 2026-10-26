# Módulo de embarques — versão 4

Atualizado em 26/10/2026: uma reserva de ida e uma de volta por pessoa/dia. Outro ônibus só permite os sentidos livres; mudar de ônibus exige cancelar ou remover o sentido anterior. A interface distingue Escolher, Alterar e Ler QR Code, bloqueando a escolha após o check-in daquele sentido. Detalhes e testes em [CORRECOES_2026-10-26.md](docs/CORRECOES_2026-10-26.md).

A escolha de ônibus, trajeto, pontos e poltrona abre às 08:00 no fuso da operação, ou quando o motorista inicia a rota antes desse horário. As opções são Só ida, Só volta e Ida e volta. Para ida e volta, a mesma poltrona deve estar livre nos dois sentidos.

A escolha fica salva até a operação encerrar ou o sentido partir, com limite na virada das 03:00. Não há contador de cinco minutos. Ela não representa um embarque: o associado precisa ler o QR diário do fiscal enquanto o embarque está aberto. O check-in online utiliza a poltrona e o ponto da escolha salva no servidor.

A tela de escolha mantém todos os lugares visíveis em 390 × 844 para capacidades de 16 e 46. A tela do QR prioriza a câmera e mostra a poltrona escolhida, o ônibus, o ponto e a ação de trocar poltrona ou ponto.

O fiscal registra exceções e o próprio embarque com justificativa. O início da ida impede novas confirmações naquele sentido. A chegada abre a volta; o motorista pode sair antes do horário previsto. Ida e volta exige uma ida confirmada; Só volta permite embarcar apenas no retorno.

Sem internet, a leitura permanece pendente em armazenamento seguro. O servidor usa o instante original da leitura e confirma ou recusa na sincronização. Há no máximo um registro válido por estudante, sentido e dia, inclusive entre ônibus. Cancelamentos mantêm histórico.

Consulte [ALTERACOES_V4.md](docs/ALTERACOES_V4.md), [LEIA-ME-PRIMEIRO.md](LEIA-ME-PRIMEIRO.md) e [VALIDACAO.md](docs/VALIDACAO.md).
