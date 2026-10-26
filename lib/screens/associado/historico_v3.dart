import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../services/fila_offline.dart';
import '../../ui/componentes.dart';
import '../../ui/tema.dart';
import 'fluxo.dart';

class HistoricoV3 extends StatefulWidget {
  final String token;
  final VoidCallback onViagens;
  const HistoricoV3({super.key, required this.token, required this.onViagens});
  @override
  State<HistoricoV3> createState() => _HistoricoV3State();
}

class _HistoricoV3State extends State<HistoricoV3> {
  DateTime mes = DateTime(DateTime.now().year, DateTime.now().month);
  List<Dados> itens = [];
  Dados frequencia = {};
  String? erro;
  bool carregando = true;
  int? proxima;
  static const meses = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];
  @override
  void initState() {
    super.initState();
    carregar();
  }

  Future<void> carregar({bool mais = false}) async {
    setState(() => carregando = true);
    try {
      final d = await ApiService.requisicao(
        'api/me/embarques/?mes=${mes.year}-${mes.month.toString().padLeft(2, '0')}${mais ? '&pagina=$proxima' : ''}',
        widget.token,
        cache: true,
      );
      if (mounted) {
        setState(() {
          itens = mais
              ? [...itens, ...mapas(d['checkins'])]
              : mapas(d['checkins']);
          frequencia = Map<String, dynamic>.from(d['frequencia'] as Map);
          proxima = d['proxima'] as int?;
          erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dias = (frequencia['dias'] as num? ?? 0).toInt(),
        total = (frequencia['dias_com_viagem'] as num? ?? 0).toInt();
    return TelaUnicap(
      titulo: 'Meus embarques',
      subtitulo: '${meses[mes.month - 1]} de ${mes.year}',
      topoAcao: PopupMenuButton<int>(
        tooltip: 'Selecionar mês',
        onSelected: (i) {
          setState(
            () => mes = DateTime(DateTime.now().year, DateTime.now().month - i),
          );
          carregar();
        },
        itemBuilder: (_) => List.generate(12, (i) {
          final d = DateTime(DateTime.now().year, DateTime.now().month - i);
          return PopupMenuItem(
            value: i,
            child: Text('${meses[d.month - 1]} de ${d.year}'),
          );
        }),
      ),
      rodape: BarraAbas(
        indice: 1,
        onChanged: (i) {
          if (i == 0) widget.onViagens();
        },
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (erro != null) ...[
            Aviso(erro!),
            Botao('Tentar novamente', contorno: true, onPressed: carregar),
          ],
          Cartao(
            cor: const Color(0xFFF7F8FA),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Frequência do mês',
                            style: TextStyle(fontSize: 11, color: cinzaUnicap),
                          ),
                          Text(
                            '$dias dias',
                            style: const TextStyle(
                              fontSize: 23,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '${frequencia['idas'] ?? 0} idas • ${frequencia['voltas'] ?? 0} voltas',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'de $total dias com viagem',
                          style: const TextStyle(
                            fontSize: 11,
                            color: cinzaUnicap,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: total == 0 ? 0 : (dias / total).clamp(0, 1),
                    minHeight: 6,
                    color: azulUnibus,
                    backgroundColor: bordaUnicap,
                  ),
                ),
              ],
            ),
          ),
          for (final p in FilaOffline.instancia.itens.where(
            (x) => x['tipo'] == 'checkin' && x['estado'] != 'confirmado',
          )) ...[
            const SizedBox(height: 10),
            InkWell(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => CheckinPendente(
                    viagem: Map<String, dynamic>.from(p['resumo'] as Map),
                    poltrona: p['corpo']['poltrona'] as int,
                  ),
                ),
              ),
              child: Aviso(
                '${p['estado'] == 'recusado' ? 'Recusado' : 'Pendente de envio'} • ${p['resumo']['onibus_nome']} • poltrona ${p['corpo']['poltrona']}',
              ),
            ),
          ],
          const TituloSecao('Últimos registros'),
          if (carregando) const LinearProgressIndicator(),
          if (!carregando && itens.isEmpty)
            const Text('Nenhum embarque registrado neste mês.'),
          for (final c in itens) registro(c),
          if (proxima != null)
            Botao(
              'Carregar anteriores',
              contorno: true,
              onPressed: carregando ? null : () => carregar(mais: true),
            ),
        ],
      ),
    );
  }

  Widget registro(Dados c) {
    final d =
        DateTime.tryParse('${c['data']}') ??
        DateTime.parse('${c['registrado_em']}').toLocal();
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 13),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: bordaUnicap)),
      ),
      child: Row(
        children: [
          Container(
            width: 46,
            padding: const EdgeInsets.symmetric(vertical: 9),
            decoration: BoxDecoration(
              color: fundoSuave,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Text(
                  '${d.day}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
                Text(
                  meses[d.month - 1].substring(0, 3).toUpperCase(),
                  style: const TextStyle(fontSize: 9, color: cinzaUnicap),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      '${c['onibus_nome']}',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        decoration: c['cancelado'] == true
                            ? TextDecoration.lineThrough
                            : null,
                      ),
                    ),
                    Etiqueta(
                      sentidoNome(c['sentido']),
                      fundo: c['sentido'] == 'retorno'
                          ? const Color(0xFFFFE8DB)
                          : const Color(0xFFE9EFF8),
                    ),
                    if (c['origem'] != 'qr') Etiqueta('${c['origem']}'),
                  ],
                ),
                const SizedBox(height: 5),
                Text(
                  'Poltrona ${c['poltrona'] ?? 'não registrada'} • ${c['ponto_nome']}',
                  style: const TextStyle(fontSize: 10, color: cinzaUnicap),
                ),
                if (c['cancelado'] == true)
                  Text(
                    'Cancelado: ${c['motivo_cancelamento']}',
                    style: const TextStyle(fontSize: 10, color: vermelhoUnicap),
                  ),
              ],
            ),
          ),
          Text(
            hora(c['registrado_em']),
            style: const TextStyle(fontSize: 10, color: cinzaUnicap),
          ),
        ],
      ),
    );
  }
}
