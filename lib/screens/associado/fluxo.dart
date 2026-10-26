import 'dart:async';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../../services/api_service.dart';
import '../../services/fila_offline.dart';
import '../../ui/componentes.dart';
import '../../ui/mapa_viagem.dart';
import '../../ui/tema.dart';

class DetalheAssociado extends StatefulWidget {
  final Dados viagem;
  final String token;
  const DetalheAssociado({
    super.key,
    required this.viagem,
    required this.token,
  });
  @override
  State<DetalheAssociado> createState() => _DetalheAssociadoState();
}

class _DetalheAssociadoState extends State<DetalheAssociado> {
  late Dados v;
  Timer? timer;
  String? erro;
  bool buscando = false, cancelando = false;
  @override
  void initState() {
    super.initState();
    v = widget.viagem;
    atualizar();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => atualizar());
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> atualizar() async {
    if (buscando) return;
    buscando = true;
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/?sentido=${v['sentido']}',
        widget.token,
        cache: true,
      );
      if (mounted) {
        setState(() {
          v = d;
          erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      buscando = false;
    }
  }

  Future<void> escolher({bool alterar = false}) async {
    final r = v['minha_reserva'];
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) =>
            r != null &&
                !alterar &&
                v['embarque_aberto'] == true &&
                v['fiscal_id'] != null
            ? ConfirmarEmbarque(
                viagem: v,
                reserva: Map<String, dynamic>.from(r as Map),
                token: widget.token,
              )
            : SelecionarPoltrona(viagem: v, token: widget.token),
      ),
    );
    if (mounted) atualizar();
  }

  Future<void> cancelarEscolha() async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Cancelar escolha?'),
        content: const Text(
          'A poltrona e os trechos ainda não confirmados serão liberados para uma nova escolha.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Manter escolha'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Cancelar escolha'),
          ),
        ],
      ),
    );
    if (confirmado != true || !mounted) return;
    setState(() => cancelando = true);
    try {
      await ApiService.requisicao(
        'api/viagens/${v['id']}/minha-escolha/',
        widget.token,
        delete: true,
      );
      await atualizar();
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => cancelando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final trajetos = v['trajetos_disponiveis'] as List?;
    final vagas = v['vagas_por_sentido'] as Map?;
    final semVagas = trajetos == null || vagas == null
        ? (v['vagas_disponiveis'] as num? ?? 0) == 0
        : trajetos.isNotEmpty &&
              !trajetos.any((trajeto) {
                final ida = (vagas['ida'] as num? ?? 0) > 0;
                final volta = (vagas['retorno'] as num? ?? 0) > 0;
                return switch (trajeto) {
                  'ida' => ida,
                  'volta' => volta,
                  'ida_volta' => ida && volta,
                  _ => false,
                };
              });
    final cheio =
        semVagas &&
        v['minha_escolha'] == null &&
        v['minha_reserva'] == null &&
        v['meu_embarque'] == null;
    if (cheio && v['escolha_aberta'] == true) {
      return OnibusLotado(viagem: v, token: widget.token);
    }
    final pontos = mapas(v['pontos']);
    final local = v['localizacao'] as Map?;
    final temEscolha = v['minha_escolha'] != null || v['minha_reserva'] != null;
    final podeEscolher =
        v['escolha_aberta'] == true &&
        (trajetos == null || trajetos.isNotEmpty) &&
        !cancelando;
    return TelaUnicap(
      titulo: '${v['onibus_nome']}',
      subtitulo: direcaoDestino(v),
      acoes: [
        if (v['meu_embarque'] != null)
          Botao(
            'Ver comprovante',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ComprovanteEmbarque(
                  viagem: v,
                  checkin: Map<String, dynamic>.from(v['meu_embarque'] as Map),
                ),
              ),
            ),
          )
        else ...[
          Botao(
            temEscolha ? 'Alterar escolha' : 'Escolher poltrona',
            icone: Icons.event_seat_outlined,
            onPressed: podeEscolher ? () => escolher(alterar: true) : null,
          ),
          if (v['minha_reserva'] != null &&
              v['embarque_aberto'] == true &&
              v['fiscal_id'] != null)
            Botao(
              'Ler QR Code',
              icone: Icons.qr_code_scanner,
              onPressed: cancelando ? null : () => escolher(),
            ),
        ],
        Botao(
          'Voltar',
          voltar: true,
          icone: Icons.arrow_back,
          onPressed: () => Navigator.pop(context),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (erro != null) Aviso(erro!),
          if (trajetos != null &&
              trajetos.isEmpty &&
              v['meu_embarque'] == null &&
              v['escolha_aberta'] == true)
            Aviso(
              ((v['bloqueios_trajeto'] as Map?)?.values.toSet() ??
                      {'Você já tem uma escolha para estes trechos.'})
                  .join('\n'),
            ),
          FotoOnibus(v),
          const SizedBox(height: 14),
          GradeDados({
            'Embarque': pontos
                .where((p) => p['sentido'] == v['sentido'])
                .map((p) => p['nome'])
                .join(', '),
            'Desembarque': pontos
                .where((p) => p['sentido'] != v['sentido'])
                .map((p) => p['nome'])
                .join(', '),
            'Saída': '${v['horario_ida']}',
            'Retorno': '${v['horario_retorno']}',
          }),
          const SizedBox(height: 12),
          MapaDaViagem(v),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Etiqueta(
                local == null
                    ? 'Aguardando GPS'
                    : local['atrasada'] == true
                    ? 'Sem sinal desde ${hora(local['capturada_em'])}'
                    : 'GPS do motorista • ${hora(local['capturada_em'])}',
                icone: Icons.gps_fixed,
              ),
              Etiqueta(
                'Capacidade ${v['ocupados']}/${v['capacidade']}',
                fundo: const Color(0xFFFFE8DB),
              ),
            ],
          ),
          if (v['minha_escolha'] != null) ...[
            const SizedBox(height: 12),
            Cartao(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Sua poltrona ${v['minha_escolha']['poltrona'].toString().padLeft(2, '0')}',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(trajetoNome(v['minha_escolha']['trajeto'])),
                  if (v['minha_escolha']['ponto_ida_nome'] != null)
                    Text('Ida: ${v['minha_escolha']['ponto_ida_nome']}'),
                  if (v['minha_escolha']['ponto_volta_nome'] != null)
                    Text('Volta: ${v['minha_escolha']['ponto_volta_nome']}'),
                  if (v['escolha_aberta'] == true && v['meu_embarque'] == null)
                    TextButton(
                      onPressed: cancelando ? null : cancelarEscolha,
                      child: Text(
                        cancelando ? 'Cancelando…' : 'Cancelar escolha',
                      ),
                    ),
                ],
              ),
            ),
          ],
          if (v['escolha_aberta'] != true) ...[
            const SizedBox(height: 12),
            Aviso(
              (v['sentido'] == 'ida'
                          ? v['partida_ida_em']
                          : v['partida_volta_em']) !=
                      null
                  ? 'Check-in encerrado: o ônibus já partiu.'
                  : v['status'] == 'finalizada' || v['status'] == 'cancelada'
                  ? 'Esta viagem está encerrada.'
                  : 'A escolha de poltrona abre às ${horaOperacao(v['escolha_abre_em'])}.',
            ),
          ],
          if (v['fiscal_id'] == null) ...[
            const SizedBox(height: 16),
            const Aviso('Aguardando um fiscal assumir esta viagem.'),
          ],
        ],
      ),
    );
  }
}

class MapaPoltronas extends StatelessWidget {
  final List<Dados> assentos;
  final int? selecionada;
  final ValueChanged<int> onChanged;
  final double altura;
  const MapaPoltronas({
    super.key,
    required this.assentos,
    required this.selecionada,
    required this.onChanged,
    this.altura = 410,
  });
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, externo) => SizedBox(
      height: externo.hasBoundedHeight ? externo.maxHeight : altura,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
        decoration: BoxDecoration(
          color: fundoSuave,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          children: [
            Text(
              'FRENTE • ${assentos.length} POLTRONAS',
              style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: cinzaUnicap,
              ),
            ),
            const SizedBox(height: 6),
            Expanded(
              child: LayoutBuilder(
                builder: (context, box) {
                  final linhas = (assentos.length / 4).ceil();
                  if (linhas == 0) return const SizedBox.shrink();
                  const espaco = 2.0;
                  final h = ((box.maxHeight - (linhas - 1) * espaco) / linhas)
                      .clamp(30.0, 64.0);
                  final w = ((box.maxWidth - 42) / 4).clamp(1.0, h * 1.8);
                  final minimo = linhas * h + (linhas - 1) * espaco;
                  Widget grade(double altura) => SizedBox(
                    height: altura,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: List.generate(
                        linhas,
                        (linha) => Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            for (int col = 0; col < 4; col++) ...[
                              if (col == 2) const SizedBox(width: 30),
                              if (col == 1 || col == 3)
                                const SizedBox(width: 6),
                              if (linha * 4 + col < assentos.length)
                                poltrona(assentos[linha * 4 + col], w, h)
                              else
                                SizedBox(width: w, height: h),
                            ],
                          ],
                        ),
                      ),
                    ),
                  );
                  return minimo > box.maxHeight + 0.1
                      ? SingleChildScrollView(
                          key: const ValueKey('rolagem-poltronas'),
                          child: grade(minimo),
                        )
                      : grade(box.maxHeight);
                },
              ),
            ),
            const SizedBox(height: 6),
            const Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                Text('□ Livre', style: TextStyle(fontSize: 10)),
                Text(
                  '× Ocupada',
                  style: TextStyle(fontSize: 10, color: cinzaUnicap),
                ),
                Text(
                  '✓ Sua escolha',
                  style: TextStyle(fontSize: 10, color: verdeUnicap),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
  Widget poltrona(Dados a, double w, double h) {
    final n = a['numero'] as int, ocupada = a['estado'] == 'ocupada';
    final escolhida =
        !ocupada &&
        (n == selecionada || a['estado'] == 'reservada' && selecionada == null);
    final cor = escolhida
        ? Colors.white
        : ocupada
        ? cinzaUnicap
        : azulUnibus;
    return Semantics(
      label:
          'Poltrona $n, ${ocupada
              ? 'ocupada'
              : escolhida
              ? 'selecionada'
              : 'livre'}',
      selected: escolhida,
      button: true,
      enabled: !ocupada,
      child: InkWell(
        onTap: ocupada ? null : () => onChanged(n),
        borderRadius: BorderRadius.circular(7),
        child: Container(
          width: w,
          height: h,
          decoration: BoxDecoration(
            color: escolhida
                ? verdeUnicap
                : ocupada
                ? const Color(0xFFE2E5EA)
                : Colors.white,
            borderRadius: BorderRadius.circular(7),
            border: Border.all(
              color: ocupada
                  ? const Color(0xFFE2E5EA)
                  : escolhida
                  ? verdeUnicap
                  : azulUnibus,
            ),
          ),
          child: Stack(
            children: [
              Center(
                child: Text(
                  n.toString().padLeft(2, '0'),
                  style: TextStyle(
                    fontSize: (h * .32).clamp(10, 18),
                    fontWeight: FontWeight.bold,
                    color: cor,
                  ),
                ),
              ),
              if (ocupada || escolhida)
                Positioned(
                  top: 0,
                  right: 2,
                  child: Text(
                    ocupada ? '×' : '✓',
                    style: TextStyle(fontSize: 9, color: cor),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class SelecionarPoltrona extends StatefulWidget {
  final Dados viagem;
  final String token;
  final bool proprioFiscal;
  final Dados? passageiro;
  final String? motivo;
  const SelecionarPoltrona({
    super.key,
    required this.viagem,
    required this.token,
    this.proprioFiscal = false,
    this.passageiro,
    this.motivo,
  });
  @override
  State<SelecionarPoltrona> createState() => _SelecionarPoltronaState();
}

class _SelecionarPoltronaState extends State<SelecionarPoltrona> {
  late Dados v;
  List<Dados> assentos = [];
  int? selecionada, pontoIda, pontoVolta;
  late String trajeto;
  String? erro;
  bool ocupado = false, buscando = false;
  int geracao = 0;
  Timer? timer;
  final motivo = TextEditingController();
  bool get fiscal => widget.proprioFiscal || widget.passageiro != null;
  bool get idaPartiu =>
      v['partida_ida_em'] != null ||
      v['meu_embarque'] != null && v['sentido'] == 'ida';
  List<String> get trajetosDisponiveis => fiscal
      ? [v['sentido'] == 'retorno' ? 'volta' : 'ida']
      : v['trajetos_disponiveis'] is List
      ? List<String>.from(v['trajetos_disponiveis'] as List)
      : idaPartiu
      ? ['volta']
      : ['ida', 'volta', 'ida_volta'];
  @override
  void initState() {
    super.initState();
    v = Map<String, dynamic>.from(widget.viagem);
    final escolha = v['minha_escolha'];
    selecionada =
        escolha?['poltrona'] as int? ?? v['minha_reserva']?['poltrona'] as int?;
    trajeto = fiscal
        ? (v['sentido'] == 'retorno' ? 'volta' : 'ida')
        : idaPartiu
        ? 'volta'
        : escolha?['trajeto'] as String? ??
              (v['sentido'] == 'retorno' ? 'volta' : 'ida_volta');
    if (!trajetosDisponiveis.contains(trajeto) &&
        trajetosDisponiveis.isNotEmpty) {
      trajeto = trajetosDisponiveis.first;
    }
    pontoIda = escolha?['ponto_ida_id'] as int?;
    pontoVolta = escolha?['ponto_volta_id'] as int?;
    motivo.text = widget.motivo ?? '';
    ajustarPontos();
    carregar();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => carregar());
  }

  @override
  void dispose() {
    timer?.cancel();
    motivo.dispose();
    super.dispose();
  }

  void ajustarPontos() {
    int? escolher(String sentido, int? valor) {
      final p = mapas(
        v['pontos'],
      ).where((p) => p['sentido'] == sentido).toList();
      return p.length == 1
          ? p.first['id'] as int
          : p.any((p) => p['id'] == valor)
          ? valor
          : null;
    }

    pontoIda = escolher('ida', pontoIda);
    pontoVolta = escolher('retorno', pontoVolta);
  }

  Future<void> carregar() async {
    if (buscando) {
      return;
    }
    buscando = true;
    final versao = geracao;
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/assentos/?sentido=${v['sentido']}&trajeto=$trajeto',
        widget.token,
      );
      if (mounted && versao == geracao) {
        setState(() {
          v = Map<String, dynamic>.from(d['viagem'] as Map);
          assentos = mapas(d['assentos']);
          if (!trajetosDisponiveis.contains(trajeto) &&
              trajetosDisponiveis.isNotEmpty) {
            trajeto = trajetosDisponiveis.first;
            selecionada = null;
            assentos = [];
            geracao++;
          }
          ajustarPontos();
          if (selecionada != null &&
              assentos.any(
                (a) => a['numero'] == selecionada && a['estado'] == 'ocupada',
              )) {
            selecionada = null;
          }
        });
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      buscando = false;
      if (mounted && versao != geracao) carregar();
    }
  }

  void trocarTrajeto(String novo) {
    setState(() {
      trajeto = novo;
      selecionada = null;
      assentos = [];
      erro = null;
      geracao++;
    });
    carregar();
  }

  bool get valida =>
      trajetosDisponiveis.contains(trajeto) &&
      selecionada != null &&
      (trajeto == 'volta' || pontoIda != null) &&
      (trajeto == 'ida' || pontoVolta != null) &&
      (!fiscal || motivo.text.trim().isNotEmpty);
  Future<void> confirmar() async {
    if (ocupado || !valida) return;
    setState(() {
      ocupado = true;
      erro = null;
    });
    try {
      if (fiscal) {
        final d = await ApiService.requisicao(
          'api/viagens/${v['id']}/embarques/${widget.proprioFiscal ? 'fiscal' : 'manual'}/',
          widget.token,
          corpo: {
            'sentido': v['sentido'],
            'poltrona': selecionada,
            'ponto_id': v['sentido'] == 'retorno' ? pontoVolta : pontoIda,
            'motivo': motivo.text.trim(),
            if (widget.passageiro != null)
              'associado_id': widget.passageiro!['id'],
          },
        );
        if (!mounted) return;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => ComprovanteEmbarque(
              viagem: v,
              checkin: Map<String, dynamic>.from(d['checkin'] as Map),
            ),
          ),
        );
      } else {
        final d = await ApiService.requisicao(
          'api/viagens/${v['id']}/reservas/',
          widget.token,
          corpo: {
            'trajeto': trajeto,
            'poltrona': selecionada,
            'ponto_ida_id': pontoIda,
            'ponto_volta_id': pontoVolta,
          },
        );
        if (!mounted) return;
        final atual = Map<String, dynamic>.from(d['viagem'] as Map);
        final reservas = mapas(
          d['reservas'],
        ).where((r) => r['sentido'] == atual['sentido']);
        if (atual['embarque_aberto'] == true &&
            atual['fiscal_id'] != null &&
            reservas.isNotEmpty) {
          final r = reservas.first;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => ConfirmarEmbarque(
                viagem: atual,
                reserva: r,
                token: widget.token,
              ),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Escolha salva. Leia o QR Code quando o embarque abrir.',
              ),
            ),
          );
          Navigator.pop(context);
        }
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
      await carregar();
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Widget ponto(String sentido, String rotulo) => EscolhaPonto(
    viagem: v,
    sentido: sentido,
    rotulo: rotulo,
    selecionado: sentido == 'ida' ? pontoIda : pontoVolta,
    onChanged: (id) => setState(() {
      if (sentido == 'ida') {
        pontoIda = id;
      } else {
        pontoVolta = id;
      }
    }),
  );
  @override
  Widget build(BuildContext context) {
    final opcoes = trajetosDisponiveis;
    return TelaUnicap(
      titulo: '${v['onibus_nome']}',
      subtitulo: fiscal
          ? 'Escolha sua poltrona'
          : 'Escolha do dia • ${assentos.where((a) => a['estado'] == 'livre').length} livres de ${v['capacidade']}',
      rolar: false,
      compacto: true,
      acoes: [
        Botao(
          fiscal
              ? 'Confirmar embarque'
              : 'Confirmar poltrona ${selecionada?.toString().padLeft(2, '0') ?? '—'}',
          onPressed: valida ? confirmar : null,
          ocupado: ocupado,
        ),
        Botao(
          'Voltar',
          voltar: true,
          icone: Icons.arrow_back,
          onPressed: ocupado ? null : () => Navigator.pop(context),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!fiscal) ...[
            const Text(
              'Seu trajeto hoje',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 12,
                color: cinzaUnicap,
              ),
            ),
            const SizedBox(height: 6),
            if (opcoes.isNotEmpty)
              Seletor(
                itens: opcoes.map(trajetoNome).toList(),
                selecionado: opcoes.indexOf(
                  opcoes.contains(trajeto) ? trajeto : 'volta',
                ),
                onChanged: (i) {
                  if (!ocupado) trocarTrajeto(opcoes[i]);
                },
              ),
            if (v['bloqueios_trajeto'] is Map &&
                (v['bloqueios_trajeto'] as Map).isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  (v['bloqueios_trajeto'] as Map).values.toSet().join('\n'),
                  style: const TextStyle(fontSize: 11, color: cinzaUnicap),
                ),
              ),
          ] else
            TextField(
              controller: motivo,
              onChanged: (_) => setState(() {}),
              maxLength: 300,
              decoration: const InputDecoration(
                labelText: 'Motivo do registro',
                counterText: '',
              ),
            ),
          if (trajeto == 'ida_volta')
            LayoutBuilder(
              builder: (context, box) => MediaQuery.sizeOf(context).width >= 360
                  ? Row(
                      children: [
                        Expanded(child: ponto('ida', 'Ponto da ida')),
                        const SizedBox(width: 8),
                        Expanded(child: ponto('retorno', 'Ponto da volta')),
                      ],
                    )
                  : Column(
                      children: [
                        ponto('ida', 'Ponto da ida'),
                        ponto('retorno', 'Ponto da volta'),
                      ],
                    ),
            )
          else
            ponto(
              trajeto == 'ida' ? 'ida' : 'retorno',
              fiscal
                  ? 'Ponto de embarque'
                  : trajeto == 'ida'
                  ? 'Ponto da ida'
                  : 'Ponto da volta',
            ),
          if (erro != null) Aviso(erro!),
          Expanded(
            child: opcoes.isEmpty
                ? const Center(
                    child: Text(
                      'Nenhum trecho disponível para uma nova escolha.',
                    ),
                  )
                : assentos.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : MapaPoltronas(
                    assentos: assentos,
                    selecionada: selecionada,
                    onChanged: (n) => setState(() => selecionada = n),
                  ),
          ),
        ],
      ),
    );
  }
}

class ConfirmarEmbarque extends StatefulWidget {
  final Dados viagem, reserva;
  final String token;
  const ConfirmarEmbarque({
    super.key,
    required this.viagem,
    required this.reserva,
    required this.token,
  });
  @override
  State<ConfirmarEmbarque> createState() => _ConfirmarEmbarqueState();
}

class _ConfirmarEmbarqueState extends State<ConfirmarEmbarque> {
  String? erro;
  bool ocupado = false, camera = true;
  Future<void> ler(String codigo) async {
    if (ocupado) return;
    setState(() {
      ocupado = true;
      camera = false;
      erro = null;
    });
    final corpo = <String, dynamic>{
      'codigo': codigo,
      'viagem_id': widget.viagem['id'],
      'sentido': widget.viagem['sentido'],
      'poltrona': widget.reserva['poltrona'],
      'ponto_id': widget.reserva['ponto_id'],
      'lido_em': DateTime.now().toUtc().toIso8601String(),
    };
    try {
      final d = await ApiService.requisicao(
        'api/checkins/',
        widget.token,
        corpo: corpo,
      );
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => ComprovanteEmbarque(
            viagem: widget.viagem,
            checkin: Map<String, dynamic>.from(d['checkin'] as Map),
          ),
        ),
      );
    } catch (e) {
      if (ApiService.falhaTemporaria(e)) {
        corpo['offline'] = true;
        await FilaOffline.instancia.adicionar(
          'checkin',
          'api/checkins/sincronizar/',
          corpo,
          resumo: widget.viagem,
        );
        if (!mounted) return;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => CheckinPendente(
              viagem: widget.viagem,
              poltrona: widget.reserva['poltrona'] as int,
            ),
          ),
        );
      } else if (mounted) {
        setState(() => erro = ApiService.mensagemErro(e));
      }
    } finally {
      if (mounted) {
        setState(() {
          ocupado = false;
          camera = true;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = widget.viagem, r = widget.reserva;
    final numero = r['poltrona'].toString().padLeft(2, '0');
    return TelaUnicap(
      titulo: 'Ler QR Code',
      subtitulo: '${v['onibus_nome']}',
      rolar: false,
      compacto: true,
      acoes: [
        Botao(
          'Trocar poltrona ou ponto',
          voltar: true,
          icone: Icons.edit_outlined,
          onPressed: ocupado
              ? null
              : () => Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        SelecionarPoltrona(viagem: v, token: widget.token),
                  ),
                ),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  const ColoredBox(color: Color(0xFF172330)),
                  if (camera && !ocupado)
                    MobileScanner(
                      errorBuilder: (context, error, child) => const Center(
                        child: Padding(
                          padding: EdgeInsets.all(28),
                          child: Text(
                            'Não foi possível abrir a câmera. Confira a permissão ou peça check-in manual ao fiscal.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.white, fontSize: 13),
                          ),
                        ),
                      ),
                      onDetect: (capture) {
                        for (final b in capture.barcodes) {
                          if (b.rawValue != null) {
                            ler(b.rawValue!);
                            break;
                          }
                        }
                      },
                    ),
                  IgnorePointer(child: CustomPaint(painter: _MolduraScanner())),
                  if (ocupado)
                    const Center(
                      child: CircularProgressIndicator(color: laranjaUnibus),
                    ),
                  const Positioned(
                    left: 12,
                    right: 12,
                    bottom: 14,
                    child: Text(
                      'Aponte para o QR Code do dia no celular do fiscal',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: Colors.white),
                    ),
                  ),
                  if (erro != null)
                    Positioned(
                      left: 14,
                      right: 14,
                      bottom: 50,
                      child: Aviso(erro!),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFF0F7F3),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: verdeUnicap, width: 1.5),
            ),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 48,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: Colors.transparent,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    numero,
                    style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.bold,
                      color: verdeUnicap,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Sua poltrona $numero',
                        style: const TextStyle(
                          fontSize: 14,
                          color: verdeUnicap,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        '${v['onibus_nome']} • Ponto: ${r['ponto_nome'] ?? 'Não informado'}',
                        style: const TextStyle(
                          fontSize: 11,
                          color: cinzaUnicap,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MolduraScanner extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(
      28,
      size.height * .19,
      size.width - 56,
      size.height * .62,
    );
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke;
    for (final p in [
      rect.topLeft,
      rect.topRight,
      rect.bottomLeft,
      rect.bottomRight,
    ]) {
      final dx = p.dx == rect.left ? 1.0 : -1.0,
          dy = p.dy == rect.top ? 1.0 : -1.0;
      canvas.drawLine(p, p + Offset(25 * dx, 0), paint);
      canvas.drawLine(p, p + Offset(0, 25 * dy), paint);
    }
    canvas.drawLine(
      Offset(rect.left + 5, rect.center.dy),
      Offset(rect.right - 5, rect.center.dy),
      paint
        ..color = laranjaUnibus
        ..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class ComprovanteEmbarque extends StatelessWidget {
  final Dados viagem, checkin;
  const ComprovanteEmbarque({
    super.key,
    required this.viagem,
    required this.checkin,
  });
  @override
  Widget build(BuildContext context) => TelaUnicap(
    titulo: 'Embarque confirmado',
    subtitulo: 'Poltrona ${checkin['poltrona']} • ${viagem['onibus_nome']}',
    acoes: [
      Botao(
        'Voltar ao início',
        voltar: true,
        icone: Icons.arrow_back,
        onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
      ),
    ],
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FotoOnibus(viagem, altura: 150),
        const SizedBox(height: 8),
        const Center(
          child: CircleAvatar(
            radius: 31,
            backgroundColor: Color(0xFFE4F2EB),
            child: Icon(Icons.check, color: verdeUnicap, size: 34),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'Check-in finalizado',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 23, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 6),
        const Text(
          'Sua presença foi registrada pelo servidor.',
          textAlign: TextAlign.center,
          style: TextStyle(color: cinzaUnicap, fontSize: 11),
        ),
        const SizedBox(height: 16),
        GradeDados({
          'Rota': '${checkin['rota_nome']}',
          'Sentido': sentidoNome(checkin['sentido']),
          'Poltrona': '${checkin['poltrona'] ?? 'Não registrada'}',
          'Ponto': '${checkin['ponto_nome']}',
          'Data e hora': horarioLocal(checkin['registrado_em']),
          'Comprovante': '#${checkin['comprovante']}',
        }, suave: true),
      ],
    ),
  );
}

class CheckinPendente extends StatefulWidget {
  final Dados viagem;
  final int poltrona;
  const CheckinPendente({
    super.key,
    required this.viagem,
    required this.poltrona,
  });
  @override
  State<CheckinPendente> createState() => _CheckinPendenteState();
}

class _CheckinPendenteState extends State<CheckinPendente> {
  bool ocupado = false;
  @override
  void initState() {
    super.initState();
    FilaOffline.instancia.addListener(atualizar);
  }

  @override
  void dispose() {
    FilaOffline.instancia.removeListener(atualizar);
    super.dispose();
  }

  void atualizar() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final item = FilaOffline.instancia.checkin(
      widget.viagem['id'] as int,
      '${widget.viagem['sentido']}',
    );
    if (item?['estado'] == 'confirmado') {
      return ComprovanteEmbarque(
        viagem: widget.viagem,
        checkin: Map<String, dynamic>.from(item!['resposta']['checkin'] as Map),
      );
    }
    final recusado = item?['estado'] == 'recusado';
    return TelaUnicap(
      titulo: recusado ? 'Check-in recusado' : 'Check-in guardado',
      subtitulo: recusado
          ? 'Confira o motivo abaixo'
          : 'Sem internet no momento',
      acoes: [
        if (!recusado)
          Botao(
            'Tentar enviar agora',
            contorno: true,
            icone: Icons.sync,
            ocupado: ocupado,
            onPressed: () async {
              setState(() => ocupado = true);
              await FilaOffline.instancia.sincronizar();
              if (mounted) setState(() => ocupado = false);
            },
          ),
        Botao(
          'Voltar ao início',
          voltar: true,
          icone: Icons.arrow_back,
          onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 8),
          Center(
            child: CircleAvatar(
              radius: 36,
              backgroundColor: const Color(0xFFFFE8DB),
              child: Icon(
                recusado ? Icons.error_outline : Icons.cloud_off,
                color: recusado ? vermelhoUnicap : laranjaUnibus,
                size: 36,
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            recusado
                ? 'O servidor recusou o embarque'
                : 'Check-in pendente de envio',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            recusado
                ? '${item?['erro']}'
                : 'A leitura foi guardada no celular e será enviada assim que a internet voltar.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: cinzaUnicap, height: 1.5),
          ),
          const SizedBox(height: 20),
          GradeDados({
            'Ônibus':
                '${widget.viagem['onibus_nome']} • ${sentidoNome(widget.viagem['sentido'])}',
            'Poltrona': '${widget.poltrona}',
            'Lido às': hora(item?['corpo']?['lido_em']),
            'Situação': recusado ? 'Recusado' : 'Aguardando envio',
          }),
          const SizedBox(height: 12),
          const Aviso(
            'Se o servidor recusar\nPor exemplo, se o ônibus lotou antes do envio: o app avisa e a poltrona é liberada.',
            informativo: true,
          ),
        ],
      ),
    );
  }
}

class OnibusLotado extends StatefulWidget {
  final Dados viagem;
  final String token;
  const OnibusLotado({super.key, required this.viagem, required this.token});
  @override
  State<OnibusLotado> createState() => _OnibusLotadoState();
}

class _OnibusLotadoState extends State<OnibusLotado> {
  List<Dados> alternativas = [];
  String get sentido {
    final trajetos = widget.viagem['trajetos_disponiveis'] as List?;
    if (trajetos?.length == 1) {
      if (trajetos!.first == 'volta') return 'retorno';
      if (trajetos.first == 'ida') return 'ida';
    }
    return '${widget.viagem['sentido']}';
  }

  @override
  void initState() {
    super.initState();
    carregar();
  }

  Future<void> carregar() async {
    try {
      final d = await ApiService.requisicao(
        'api/viagens/hoje/?sentido=$sentido',
        widget.token,
      );
      if (mounted) {
        setState(
          () => alternativas = mapas(d['viagens'])
              .where(
                (v) =>
                    v['id'] != widget.viagem['id'] &&
                    v['destino'] == widget.viagem['destino'] &&
                    (v['vagas_disponiveis'] as num) > 0,
              )
              .toList(),
        );
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final v = widget.viagem;
    final vagas = (v['vagas_por_sentido'] as Map?)?[sentido] as num?;
    final ocupados = vagas == null
        ? v['ocupados']
        : (v['capacidade'] as num) - vagas;
    return TelaUnicap(
      titulo: 'Ônibus lotado',
      subtitulo: 'Escolha outro ônibus para continuar.',
      acoes: [
        Botao(
          'Voltar',
          voltar: true,
          icone: Icons.arrow_back,
          onPressed: () => Navigator.pop(context),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          FotoOnibus(v, altura: 160),
          const SizedBox(height: 12),
          Text(
            '${v['onibus_nome']}',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 10),
          Center(
            child: Etiqueta(
              '$ocupados/${v['capacidade']} lugares ocupados',
              cor: vermelhoUnicap,
              fundo: const Color(0xFFFDEDEB),
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'Este ônibus está lotado.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          Text(
            'Não há poltronas livres para a ${sentidoNome(sentido).toLowerCase()}.',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: cinzaUnicap),
          ),
          const TituloSecao('Outros ônibus da sua rota com vagas'),
          for (final a in alternativas)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: InkWell(
                onTap: () => Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        DetalheAssociado(viagem: a, token: widget.token),
                  ),
                ),
                child: Cartao(
                  child: Row(
                    children: [
                      SizedBox(width: 65, child: FotoOnibus(a, altura: 48)),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${a['onibus_nome']}',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              'Saída ${a['horario_ida']} • ${a['vagas_disponiveis']} vagas livres',
                              style: const TextStyle(
                                fontSize: 10,
                                color: cinzaUnicap,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right),
                    ],
                  ),
                ),
              ),
            ),
          if (alternativas.isEmpty)
            const Text(
              'Nenhum outro ônibus com vagas disponível agora.',
              style: TextStyle(color: cinzaUnicap, fontSize: 12),
            ),
        ],
      ),
    );
  }
}
