import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:screen_brightness/screen_brightness.dart';
import '../../services/api_service.dart';
import '../../services/armazenamento.dart';
import '../../ui/componentes.dart';
import '../../ui/tema.dart';
import '../associado/fluxo.dart';

class FluxoFiscal extends StatefulWidget {
  final Dados viagem, usuario;
  final String token;
  final int telaInicial;
  const FluxoFiscal({
    super.key,
    required this.viagem,
    required this.usuario,
    required this.token,
    this.telaInicial = 0,
  });
  @override
  State<FluxoFiscal> createState() => _FluxoFiscalState();
}

class _FluxoFiscalState extends State<FluxoFiscal> {
  late Dados v;
  late int tela;
  List<Dados> checkins = [], encontrados = [], assentos = [];
  Dados? qr, pessoa;
  final busca = TextEditingController(), motivo = TextEditingController();
  String? erro;
  int? poltrona, pontoId;
  bool ocupado = false, buscando = false, porPonto = false;
  String? sentidoConferencia;
  Timer? timer, debounce;
  int buscaVersao = 0;
  @override
  void initState() {
    super.initState();
    v = widget.viagem;
    tela = widget.telaInicial;
    atualizar();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => atualizar());
  }

  @override
  void dispose() {
    timer?.cancel();
    debounce?.cancel();
    busca.dispose();
    motivo.dispose();
    liberarTela();
    super.dispose();
  }

  Future<void> liberarTela() async {
    if (Armazenamento.emMemoria) return;
    try {
      await WakelockPlus.disable();
      if (!kIsWeb) {
        await ScreenBrightness.instance.resetApplicationScreenBrightness();
      }
    } catch (_) {}
  }

  Future<void> manterTela() async {
    if (Armazenamento.emMemoria) return;
    try {
      await WakelockPlus.enable();
      if (!kIsWeb) {
        await ScreenBrightness.instance.setApplicationScreenBrightness(1);
      }
    } catch (_) {}
  }

  String get sentido => sentidoConferencia ?? '${v['sentido']}';
  Future<void> atualizar() async {
    if (buscando) return;
    buscando = true;
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/embarques/${tela == 5 ? '?sentido=$sentido' : ''}',
        widget.token,
        cache: true,
      );
      if (mounted) {
        setState(() {
          v = Map<String, dynamic>.from(d['viagem'] as Map);
          if (tela == 2 &&
              (v['embarque_aberto'] != true ||
                  qr?['viagem']?['sentido'] != v['sentido'])) {
            qr = null;
            tela = 1;
            liberarTela();
          }
          checkins = mapas(d['checkins']);
          erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      buscando = false;
    }
  }

  Future<void> mostrarQr() async {
    if (ocupado) return;
    setState(() => ocupado = true);
    final chave = 'qr.${widget.usuario['id']}.${v['id']}.${v['sentido']}';
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/qr-do-dia/',
        widget.token,
        corpo: {'sentido': v['sentido']},
      );
      await Armazenamento.salvar(chave, d);
      if (mounted) {
        setState(() {
          qr = d;
          tela = 2;
          erro = null;
        });
      }
      await manterTela();
    } catch (e) {
      final salvo = await Armazenamento.ler(chave);
      if (ApiService.falhaTemporaria(e) &&
          salvo is Map &&
          DateTime.tryParse('${salvo['expira_em']}')?.isAfter(DateTime.now()) ==
              true) {
        if (mounted) {
          setState(() {
            qr = Map<String, dynamic>.from(salvo);
            tela = 2;
            erro =
                'Sem internet • contador atualizado às ${hora(v['atualizado_em'])}';
          });
        }
        await manterTela();
      } else if (mounted) {
        setState(() => erro = ApiService.mensagemErro(e));
      }
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  void mudar(int destino) {
    if (tela == 2 && destino != 2) liberarTela();
    setState(() {
      tela = destino;
      erro = null;
      if (destino != 5) sentidoConferencia = null;
    });
    atualizar();
  }

  void pesquisar(String valor) {
    debounce?.cancel();
    final versao = ++buscaVersao;
    debounce = Timer(const Duration(milliseconds: 300), () async {
      if (valor.trim().length < 3) {
        if (mounted) setState(() => encontrados = []);
        return;
      }
      try {
        final d = await ApiService.requisicao(
          'api/viagens/${v['id']}/associados/?q=${Uri.encodeQueryComponent(valor.trim())}&sentido=${v['sentido']}',
          widget.token,
        );
        if (mounted && versao == buscaVersao) {
          setState(() => encontrados = mapas(d['associados']));
        }
      } catch (e) {
        if (mounted) setState(() => erro = ApiService.mensagemErro(e));
      }
    });
  }

  Future<void> selecionar(Dados a) async {
    if (a['embarque'] != null) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ComprovanteEmbarque(
            viagem: v,
            checkin: Map<String, dynamic>.from(a['embarque'] as Map),
          ),
        ),
      );
      return;
    }
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/assentos/?sentido=${v['sentido']}&associado_id=${a['id']}',
        widget.token,
      );
      if (mounted) {
        setState(() {
          pessoa = a;
          assentos = mapas(d['assentos']);
          poltrona = null;
          final pontos = mapas(
            v['pontos'],
          ).where((p) => p['sentido'] == v['sentido']).toList();
          pontoId = pontos.length == 1 ? pontos.first['id'] as int : null;
          tela = 4;
          motivo.clear();
        });
      }
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    }
  }

  Future<void> registrar() async {
    if (ocupado || pessoa == null || poltrona == null) return;
    setState(() => ocupado = true);
    try {
      await ApiService.requisicao(
        'api/viagens/${v['id']}/embarques/manual/',
        widget.token,
        corpo: {
          'associado_id': pessoa!['id'],
          'poltrona': poltrona,
          'ponto_id': pontoId,
          'sentido': v['sentido'],
          'motivo': motivo.text.trim(),
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${pessoa!['nome']} embarcado na poltrona $poltrona'),
        ),
      );
      mudar(3);
      pesquisar(busca.text);
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> cancelar(Dados c) async {
    final controle = TextEditingController();
    final texto = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancelar embarque'),
        content: TextField(
          controller: controle,
          maxLength: 300,
          decoration: const InputDecoration(labelText: 'Motivo obrigatório'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Voltar'),
          ),
          TextButton(
            onPressed: () {
              if (controle.text.trim().isNotEmpty) {
                Navigator.pop(ctx, controle.text.trim());
              }
            },
            child: const Text('Confirmar cancelamento'),
          ),
        ],
      ),
    );
    // O controller só é descartado depois da animação do diálogo.
    Future<void>.delayed(const Duration(milliseconds: 300), controle.dispose);
    if (texto == null) return;
    try {
      await ApiService.requisicao(
        'api/checkins/${c['id']}/',
        widget.token,
        delete: true,
        corpo: {'motivo': texto},
      );
      await atualizar();
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final aberto = v['embarque_aberto'] == true;
    final titulo = [
      'Painel fiscal',
      'Embarque da ${sentidoNome(v['sentido']).toLowerCase()}',
      'QR Code do dia',
      'Check-in manual',
      'Registrar embarque',
      'Conferência',
    ][tela];
    final subtitulo = [
      '${v['onibus_nome']} • para ${v['destino']}',
      '${v['onibus_nome']} • próximo ponto: ${v['proximo_ponto'] ?? 'não informado'}',
      '${sentidoNome(v['sentido'])} • ${v['onibus_nome']} • fiscal ${widget.usuario['nome']}',
      'Busque por nome ou RUA',
      'Check-in manual • ${sentidoNome(v['sentido'])} • ${v['onibus_nome']}',
      '${v['onibus_nome']} • partida prevista ${v['horario_ida']}',
    ][tela];
    return PopScope(
      canPop: tela == 0,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) mudar(0);
      },
      child: TelaUnicap(
        titulo: titulo,
        rolar: tela != 4,
        compacto: tela == 4,
        subtitulo: subtitulo,
        acoes: [
          if (tela == 1)
            Botao(
              'Mostrar QR Code do dia',
              icone: Icons.qr_code,
              onPressed: aberto ? mostrarQr : null,
              ocupado: ocupado,
            ),
          if (tela == 2)
            Botao(
              'Check-in manual',
              icone: Icons.search,
              contorno: true,
              onPressed: aberto ? () => mudar(3) : null,
            ),
          if (tela == 4)
            Botao(
              'Registrar embarque',
              icone: Icons.person_add_alt,
              onPressed:
                  poltrona != null &&
                      pontoId != null &&
                      motivo.text.trim().isNotEmpty &&
                      aberto
                  ? registrar
                  : null,
              ocupado: ocupado,
            ),
          Botao(
            'Voltar',
            voltar: true,
            icone: Icons.arrow_back,
            onPressed: ocupado
                ? null
                : () {
                    if (tela == 0) {
                      Navigator.pop(context);
                    } else {
                      mudar(
                        tela == 2
                            ? 1
                            : tela == 4
                            ? 3
                            : 0,
                      );
                    }
                  },
          ),
        ],
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (erro != null) Aviso(erro!),
            ...switch (tela) {
              0 => painel(),
              1 => contador(),
              2 => codigo(),
              3 => buscaManual(),
              4 => registroManual(),
              _ => conferencia(),
            },
          ],
        ),
      ),
    );
  }

  List<Widget> painel() => [
    Row(
      children: [
        SizedBox(width: 114, child: FotoOnibus(v, altura: 100)),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Placa', style: Theme.of(context).textTheme.bodySmall),
              Text(
                '${v['placa']}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text('Motorista', style: Theme.of(context).textTheme.bodySmall),
              Text(
                '${v['motorista_nome']}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ),
      ],
    ),
    GradeDados({
      'Embarque': mapas(v['pontos'])
          .where((p) => p['sentido'] == v['sentido'])
          .map((p) => p['nome'])
          .join(', '),
      'Capacidade': '${v['ocupados']}/${v['capacidade']}',
    }),
    const SizedBox(height: 12),
    Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        Etiqueta(
          v['embarque_aberto'] == true
              ? 'Embarque da ${sentidoNome(v['sentido']).toLowerCase()} aberto'
              : '${v['etapa_nome']}',
        ),
        Etiqueta(
          v['localizacao'] != null ? 'GPS ativo' : 'Aguardando GPS',
          icone: Icons.gps_fixed,
        ),
      ],
    ),
    const SizedBox(height: 14),
    Seletor(
      itens: widget.usuario['estudante'] == true
          ? const ['Fiscal', 'Associado']
          : const ['Fiscal'],
      selecionado: 0,
      onChanged: (i) {
        if (i == 1 && v['embarque_aberto'] == true) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => SelecionarPoltrona(
                viagem: v,
                token: widget.token,
                proprioFiscal: true,
              ),
            ),
          );
        }
      },
    ),
    const SizedBox(height: 12),
    acao(
      Icons.qr_code,
      'Embarque e QR Code',
      'Contador de check-in e QR Code do dia',
      1,
      v['embarque_aberto'] == true,
    ),
    acao(
      Icons.search,
      'Check-in manual',
      'Associado sem celular ou sem câmera',
      3,
      v['embarque_aberto'] == true,
    ),
    acao(
      Icons.checklist,
      'Conferência',
      'Lista nominal da ida e da volta',
      5,
      true,
    ),
    if (v['etapa'] == 'agendada')
      const Aviso('Aguardando o motorista iniciar a rota.'),
  ];
  Widget acao(
    IconData icon,
    String nome,
    String desc,
    int destino,
    bool ativo,
  ) => Opacity(
    opacity: ativo ? 1 : .45,
    child: ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFFFFE8DB),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: azulUnibus, size: 23),
      ),
      title: Text(
        nome,
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
      ),
      subtitle: Text(
        desc,
        style: const TextStyle(fontSize: 10, color: cinzaUnicap),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: ativo ? () => mudar(destino) : null,
    ),
  );
  List<Widget> contador() => [
    Cartao(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Ocupacao(v, grande: true),
          Text(
            'Embarque aberto desde ${hora(v['sentido'] == 'ida' ? v['iniciada_em'] : v['chegada_em'])} • atualizado ${hora(v['atualizado_em'])}',
            style: const TextStyle(color: cinzaUnicap, fontSize: 10),
          ),
        ],
      ),
    ),
    const TituloSecao('Últimos check-ins'),
    ...checkins
        .where((c) => c['cancelado'] != true)
        .take(8)
        .map((c) => linha(c)),
    if (checkins.isEmpty) const Text('Nenhum check-in registrado ainda.'),
  ];
  List<Widget> codigo() => [
    if (qr == null)
      const Aviso('QR indisponível. Volte ao contador e tente novamente.')
    else
      Cartao(
        child: Column(
          children: [
            if (DateTime.tryParse(
                  '${qr!['expira_em']}',
                )?.isAfter(DateTime.now()) ==
                true)
              QrImageView(
                data: '${qr!['codigo']}',
                size: 270,
                padding: const EdgeInsets.all(12),
              )
            else
              const Aviso('QR do dia expirado.'),
            const Text(
              'Válido hoje, só neste ônibus e sentido,\nenquanto o embarque estiver aberto',
              textAlign: TextAlign.center,
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                const Etiqueta('Funciona sem internet', icone: Icons.cloud_off),
                Etiqueta(
                  'Gerado às ${hora(qr!['gerado_em'])}',
                  icone: Icons.access_time,
                ),
              ],
            ),
          ],
        ),
      ),
    const SizedBox(height: 14),
    Cartao(
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Quantidade de check-in',
                  style: TextStyle(fontSize: 11, color: cinzaUnicap),
                ),
                Text(
                  '${v['presentes']}/${v['capacidade']}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 22,
                  ),
                ),
              ],
            ),
          ),
          if (checkins.isNotEmpty)
            Expanded(
              child: Text(
                '✓ ${checkins.first['nome']}\npol. ${checkins.first['poltrona']} • ${hora(checkins.first['registrado_em'])}',
                textAlign: TextAlign.right,
                style: const TextStyle(fontSize: 11),
              ),
            ),
        ],
      ),
    ),
  ];
  List<Widget> buscaManual() => [
    TextField(
      controller: busca,
      onChanged: pesquisar,
      decoration: const InputDecoration(
        prefixIcon: Icon(Icons.search),
        hintText: 'Nome ou RUA',
      ),
    ),
    const SizedBox(height: 8),
    Text(
      '${encontrados.length} associados da rota encontrados',
      style: const TextStyle(color: cinzaUnicap, fontSize: 11),
    ),
    ...encontrados.map(
      (a) => LinhaPessoa(
        a,
        subtitulo: 'RUA ${a['rua']} • ${a['instituicao']}',
        trailing: Etiqueta(
          a['embarque'] == null
              ? 'Pode embarcar'
              : 'Já embarcou • pol. ${a['embarque']['poltrona']}',
        ),
        onTap: () => selecionar(a),
      ),
    ),
    const SizedBox(height: 16),
    const Aviso(
      'Quando usar\nAssociado sem bateria, sem câmera ou sem internet. Todo check-in manual exige motivo e fica no log.',
    ),
  ];
  List<Widget> registroManual() => [
    Text(
      '${pessoa?['nome']} • ${pessoa?['rua']}',
      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
    ),
    const SizedBox(height: 8),
    TextField(
      controller: motivo,
      onChanged: (_) => setState(() {}),
      maxLength: 300,
      decoration: const InputDecoration(
        labelText: 'Motivo do check-in manual',
        hintText: 'Ex.: Celular sem bateria',
        counterText: '',
      ),
    ),
    EscolhaPonto(
      viagem: v,
      selecionado: pontoId,
      onChanged: (id) => setState(() => pontoId = id),
    ),
    Expanded(
      child: MapaPoltronas(
        assentos: assentos,
        selecionada: poltrona,
        onChanged: (n) => setState(() => poltrona = n),
      ),
    ),
  ];
  Widget linha(Dados c, {bool cancelar = false}) => LinhaPessoa(
    c,
    subtitulo:
        'Pol. ${c['poltrona'] ?? '—'} • ${c['ponto_nome']} • ${hora(c['registrado_em'])} • ${c['origem']}${c['cancelado'] == true ? '\nCancelado: ${c['motivo_cancelamento']}' : ''}',
    trailing: cancelar && c['cancelado'] != true && v['embarque_aberto'] == true
        ? IconButton(
            tooltip: 'Cancelar embarque de ${c['nome']}',
            onPressed: () => this.cancelar(c),
            icon: const Icon(Icons.close, size: 18),
          )
        : null,
  );
  List<Widget> conferencia() {
    final ativos = checkins.where((c) => c['cancelado'] != true).toList();
    final grupos = <String, List<Dados>>{};
    for (final c in checkins) {
      grupos.putIfAbsent('${c['ponto_nome']}', () => []).add(c);
    }
    return [
      Seletor(
        itens: ['Ida (${v['total_ida']})', 'Volta (${v['total_retorno']})'],
        selecionado: sentido == 'ida' ? 0 : 1,
        onChanged: (i) {
          setState(() => sentidoConferencia = i == 0 ? 'ida' : 'retorno');
          atualizar();
        },
      ),
      const SizedBox(height: 12),
      Numeros({
        'embarcados': ativos.length,
        'vagas': v['vagas_disponiveis'],
        'capacidade': v['capacidade'],
      }),
      const SizedBox(height: 12),
      Row(
        children: [
          const Expanded(
            child: Text(
              'Lista nominal',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
          TextButton(
            onPressed: () => setState(() => porPonto = !porPonto),
            child: Text(porPonto ? 'Sem agrupar' : 'Por ponto'),
          ),
        ],
      ),
      if (porPonto)
        for (final e in grupos.entries) ...[
          TituloSecao(e.key),
          ...e.value.map((c) => linha(c, cancelar: true)),
        ]
      else
        ...checkins.map((c) => linha(c, cancelar: true)),
      if (checkins.isEmpty) const Text('Nenhum embarque neste sentido.'),
      const SizedBox(height: 12),
      const Text(
        'Toque em × para cancelar um embarque indevido (motivo obrigatório).',
        style: TextStyle(color: cinzaUnicap, fontSize: 11),
      ),
    ];
  }
}
