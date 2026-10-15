# Alinhamento do TCC com o sistema entregue

Use estas informações para atualizar metodologia, descrição dos módulos, screenshots e avaliação. Elas não afirmam que o piloto ou a implantação já ocorreram.

## Descrição da implementação

O sistema integra um painel administrativo desenvolvido em Django, uma API REST e uma aplicação Flutter. A administração mantém usuários, instituições, cursos, matrículas anuais, veículos, motoristas, rotas e pontos. O motorista inicia e encerra viagens de ida e retorno e envia posições do dispositivo durante o uso do painel. Fiscais geram um QR Code e um código manual vinculados à viagem e ao ponto de embarque informado. O associado registra o embarque após validação no servidor. A administração consulta relatórios de frequência, utilização, ocupação, vagas, pontos e despesas, com exportação em PDF.

## Precisões necessárias no texto

| Assunto | Descrição coerente com a implementação |
|---|---|
| Banco de dados | SQLite para desenvolvimento local; configuração PostgreSQL para implantação. Só afirmar uso operacional de PostgreSQL depois de implantado. |
| Exclusão de cadastro | Inativação e preservação de histórico nos fluxos normais. |
| Check-in duplicado | Bloqueio por associado e viagem, permitindo ida e retorno separados no mesmo dia. |
| GPS em tempo real | Atualização periódica aproximadamente a cada 10 segundos enquanto o painel estiver ativo; aviso quando a última leitura tiver mais de 60 segundos. |
| Precisão do GPS | Valor reportado pelo aparelho; precisa ser medido no percurso real. |
| Rotas no mapa | Pontos cadastrados e percurso observado pelo GPS; sem cálculo de caminho otimizado. |
| Senhas | Armazenadas por hash pelo Django, sem armazenamento em texto puro. |
| Sessão | JWT com renovação e rotação no aplicativo, expiração e revogação; sessão web com CSRF e logout via POST. |
| HTTPS | Configuração de implantação fornecida; depende de domínio e servidor ativos. |
| Matrícula anual | Registro por ano; matrícula de outro ano não autoriza o embarque atual. Migração não inventa o histórico anterior. |
| Cache temporário | Consultas de ônibus/histórico em memória por até cinco minutos durante a sessão, com aviso. Não confirma check-in offline. |
| Assentos | Controle da quantidade de vagas, sem reserva de número de poltrona. |
| Estado/despesas dos veículos | Cadastro do estado atual, despesas, cancelamento preservado e relatório PDF. Não equivale a mensalidades dos associados. |
| Auditoria | Registros de login, consultas administrativas e alterações relevantes a partir desta versão; não reconstrói operações antigas. |

O item da entrevista sobre carteirinhas virtuais existentes exige definir o formato e a integração com o fornecedor. Esta versão usa o QR do fiscal e o código manual descritos nos módulos 4 e 5. Não declarar integração com carteirinhas externas nem pagamentos automáticos.

## Resultados a relatar

Consulte `VALIDACAO.md` e identifique separadamente testes automatizados, ensaios no navegador e homologação com a associação. Tempo de check-in, simultaneidade, disponibilidade, consumo de bateria e precisão são requisitos de avaliação; ainda não são resultados comprovados de campo.

Atualize as figuras com as telas executadas no computador de apresentação. Remova dados pessoais e identifique dados fictícios. Descreva o piloto como atividade futura até sua efetiva execução.
