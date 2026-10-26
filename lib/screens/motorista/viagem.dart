import 'dart:async';
import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../services/fila_offline.dart';
import '../../services/rastreamento.dart';
import '../../ui/componentes.dart';
import '../../ui/mapa_viagem.dart';
import '../../ui/tema.dart';

class ViagemMotorista extends StatefulWidget {
  final Dados viagem, usuario;
  final String token;
  const ViagemMotorista({
    super.key,
    required this.viagem,
    required this.usuario,
    required this.token,
  });
  @override
  State<ViagemMotorista> createState() => _ViagemMotoristaState();
}

class _ViagemMotoristaState extends State<ViagemMotorista> {
  late Dados v;
  String? erro, erroPermissao;
  bool ocupado = false, buscando = false, permitido = false;
  Timer? timer;
  final gps = Rastreamento.instancia;
  static const transicoes = {
    'agendada': ['iniciar_rota', 'embarque_ida', 'iniciada_em'],
    'embarque_ida': ['iniciar_ida', 'transito_ida', 'partida_ida_em'],
    'transito_ida': ['finalizar_ida', 'no_destino', 'chegada_em'],
    'no_destino': ['iniciar_volta', 'transito_volta', 'partida_volta_em'],
    'transito_volta': ['finalizar', 'encerrada', 'finalizada_em'],
  };
  @override
  void initState() {
    super.initState();
    v = widget.viagem;
    gps.addListener(mudou);
    FilaOffline.instancia.addListener(mudou);
    if (!['encerrada', 'cancelada'].contains(v['etapa'])) verificarPermissao();
    atualizar();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => atualizar());
  }

  void mudou() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    timer?.cancel();
    gps.removeListener(mudou);
    FilaOffline.instancia.removeListener(mudou);
    super.dispose();
  }

  Future<void> verificarPermissao() async {
    try {
      final ok = await Rastreamento.permitir();
      if (mounted) {
        setState(() {
          permitido = ok;
          erroPermissao = ok
              ? null
              : 'Permita o acesso à localização do aparelho.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          permitido = false;
          erroPermissao = ApiService.mensagemErro(e);
        });
      }
    }
  }

  Future<void> atualizar() async {
    if (buscando || ocupado) return;
    buscando = true;
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/',
        widget.token,
        cache: true,
      );
      if (!mounted) return;
      final pendentes = FilaOffline.instancia.itens.where(
        (e) =>
            e['tipo'] == 'transicao' &&
            e['caminho'] == 'api/viagens/${v['id']}/transicao/' &&
            e['estado'] == 'pendente',
      );
      if (pendentes.isEmpty) {
        setState(() {
          v = d;
          erro = null;
        });
        if (ApiService.avisosCache['api/viagens/${v['id']}/'] == null) {
          gps.atualizar(v, widget.token);
        }
      }
    } catch (e) {
      if (e is ApiException && [403, 404].contains(e.status)) gps.parar();
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      buscando = false;
    }
  }

  Future<void> executar() async {
    final t = transicoes[v['etapa']];
    if (t == null || ocupado || gps.emMovimento) return;
    if (v['etapa'] == 'agendada' && !permitido) {
      await verificarPermissao();
      if (!permitido) return;
    }
    if (['transito_ida', 'no_destino', 'transito_volta'].contains(v['etapa'])) {
      final ok = await confirmar();
      if (!ok) return;
    }
    setState(() => ocupado = true);
    final quando = DateTime.now().toUtc().toIso8601String();
    try {
      final d = await ApiService.requisicao(
        'api/viagens/${v['id']}/transicao/',
        widget.token,
        corpo: {'acao': t[0], 'ocorrida_em': quando},
      );
      if (mounted) setState(() => v = d);
    } catch (e) {
      if (ApiService.falhaTemporaria(e)) {
        await FilaOffline.instancia.adicionar(
          'transicao',
          'api/viagens/${v['id']}/transicao/',
          {'acao': t[0], 'ocorrida_em': quando},
          resumo: v,
        );
        if (mounted) {
          setState(() {
            v = {
              ...v,
              'etapa': t[1],
              t[2]: quando,
              'status': t[1] == 'encerrada' ? 'finalizada' : 'em_andamento',
              'sentido':
                  ['no_destino', 'transito_volta', 'encerrada'].contains(t[1])
                  ? 'retorno'
                  : 'ida',
            };
            erro = 'Etapa guardada. Aguardando confirmação do servidor.';
          });
        }
      } else if (mounted) {
        setState(() => erro = ApiService.mensagemErro(e));
      }
    } finally {
      gps.atualizar(v, widget.token);
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<bool> confirmar() async {
    final volta = v['etapa'] == 'no_destino',
        fim = v['etapa'] == 'transito_volta';
    return await showModalBottomSheet<bool>(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.white,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
          ),
          builder: (c) => SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 42,
                      height: 4,
                      decoration: BoxDecoration(
                        color: bordaUnicap,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Center(
                    child: CircleAvatar(
                      radius: 29,
                      backgroundColor: Color(0xFFFFE8DB),
                      child: Icon(Icons.flag_outlined, color: laranjaUnibus),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    volta
                        ? 'Deseja iniciar o caminho de volta?'
                        : 'Deseja finalizar a viagem?',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    volta
                        ? 'Ao iniciar, o embarque da volta fecha.'
                        : fim
                        ? 'Confirme só ao chegar. A viagem será encerrada e o GPS desligado.'
                        : 'Confirme só ao chegar ao destino. O embarque da volta é liberado e o GPS passa ao modo econômico.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: cinzaUnicap,
                      fontSize: 12,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                  GradeDados({
                    'Saída': hora(
                      v[fim ? 'partida_volta_em' : 'partida_ida_em'],
                    ),
                    'Agora': hora(DateTime.now().toIso8601String()),
                    'Último ponto': mapas(v['pontos']).isEmpty
                        ? 'Não informado'
                        : '${mapas(v['pontos']).last['nome']}',
                    'A bordo ${fim ? 'na volta' : 'na ida'}':
                        '${fim ? v['total_retorno'] : v['total_ida']}',
                  }, suave: true),
                  const SizedBox(height: 16),
                  Botao(
                    volta ? 'Iniciar caminho de volta' : 'Finalizar viagem',
                    onPressed: () => Navigator.pop(c, true),
                  ),
                  const SizedBox(height: 10),
                  Botao(
                    'Cancelar',
                    contorno: true,
                    onPressed: () => Navigator.pop(c, false),
                  ),
                ],
              ),
            ),
          ),
        ) ??
        false;
  }

  @override
  Widget build(BuildContext context) {
    final etapa = '${v['etapa']}',
        agendada = etapa == 'agendada',
        encerrada = etapa == 'encerrada' || etapa == 'cancelada';
    final titulo = switch (etapa) {
      'agendada' => 'Ônibus selecionado',
      'embarque_ida' => 'Rota iniciada',
      'transito_ida' => 'Em viagem',
      'no_destino' => 'No destino',
      'transito_volta' => 'Boa viagem!',
      _ => 'Viagem encerrada',
    };
    final sub = switch (etapa) {
      'agendada' => '${v['onibus_nome']} • para ${v['destino']}',
      'embarque_ida' => 'Embarque da ida • ${v['onibus_nome']}',
      'no_destino' => '${v['destino']} • retorno às ${v['horario_retorno']}',
      'transito_ida' => 'Ida • para ${v['destino']}',
      'transito_volta' => 'Volta • saindo de ${v['destino']}',
      _ => '${v['onibus_nome']} • ${dataCompleta(v['data'])}',
    };
    final botao = switch (etapa) {
      'agendada' => 'Iniciar rota',
      'embarque_ida' => 'Iniciar viagem',
      'no_destino' => 'Iniciar caminho de volta',
      _ => 'Finalizar viagem',
    };
    final pendentes = FilaOffline.instancia.itens.where(
      (e) =>
          e['tipo'] == 'transicao' &&
          e['caminho'] == 'api/viagens/${v['id']}/transicao/' &&
          e['estado'] != 'confirmado',
    );
    return TelaUnicap(
      titulo: titulo,
      subtitulo: sub,
      acoes: [
        if (!encerrada)
          Botao(
            botao,
            icone: agendada || etapa == 'embarque_ida'
                ? Icons.play_arrow_outlined
                : Icons.flag_outlined,
            ocupado: ocupado,
            onPressed:
                gps.emMovimento ||
                    (agendada && (!permitido || v['pode_iniciar'] != true))
                ? null
                : executar,
          ),
        Botao(
          encerrada ? 'Voltar ao início' : 'Voltar',
          voltar: true,
          icone: Icons.arrow_back,
          onPressed: ocupado ? null : () => Navigator.pop(context),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (erro != null) Aviso(erro!),
          if (erroPermissao != null) ...[
            Aviso(erroPermissao!),
            TextButton(
              onPressed: verificarPermissao,
              child: const Text('Verificar localização novamente'),
            ),
          ],
          for (final p in pendentes)
            Aviso(
              p['estado'] == 'recusado'
                  ? 'Etapa recusada: ${p['erro']}'
                  : 'Etapa pendente de envio: ${p['corpo']['acao']}',
            ),
          ...switch (etapa) {
            'agendada' => antes(),
            'embarque_ida' => embarque(),
            'no_destino' => destino(),
            'encerrada' || 'cancelada' => resumo(),
            _ => emViagem(),
          },
        ],
      ),
    );
  }

  List<Widget> antes() {
    final pontos = mapas(v['pontos']);
    return [
      FotoOnibus(v, altura: 150),
      const SizedBox(height: 16),
      GradeDados({
        'Placa': '${v['placa']}',
        'Capacidade': '${v['capacidade']} lugares',
        'Saída': '${v['horario_ida']}',
        'Retorno': '${v['horario_retorno']}',
        'Embarque': pontos
            .where((p) => p['sentido'] == 'ida')
            .map((p) => p['nome'])
            .join(', '),
        'Desembarque': pontos
            .where((p) => p['sentido'] == 'retorno')
            .map((p) => p['nome'])
            .join(', '),
      }),
      const TituloSecao('Antes de iniciar'),
      InkWell(
        onTap: verificarPermissao,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            permitido
                ? '✓  Localização do celular permitida'
                : '!  Permita a localização',
            style: TextStyle(
              color: permitido ? azulUnibus : vermelhoUnicap,
              fontSize: 12,
            ),
          ),
        ),
      ),
      Text(
        '${v['pode_iniciar'] == true ? '✓' : '◷'}  Liberado a partir de ${hora(v['liberada_em'])} (60 min antes)',
        style: const TextStyle(fontSize: 12),
      ),
      const SizedBox(height: 14),
      Text(
        '♧  Fiscal da viagem: ${v['fiscal_nome'] ?? 'Sem fiscal'}',
        style: const TextStyle(fontSize: 12),
      ),
    ];
  }

  Widget statusGps() => Wrap(
    spacing: 7,
    runSpacing: 7,
    children: [
      Etiqueta(
        gps.erro != null
            ? 'Aguardando GPS'
            : gps.ultimoEnvio == null
            ? 'Obtendo localização'
            : v['etapa'] == 'no_destino'
            ? 'GPS econômico • a cada 60 s'
            : 'GPS ativo • a cada ${gps.intervalo} s',
        icone: Icons.gps_fixed,
      ),
      Etiqueta(
        v['etapa'] == 'no_destino'
            ? 'No destino'
            : 'Iniciada ${hora(v['iniciada_em'])}',
        icone: Icons.access_time,
      ),
    ],
  );
  List<Widget> embarque() => [
    statusGps(),
    const TituloSecao('Pontos de embarque'),
    ...mapas(v['pontos'])
        .where((p) => p['sentido'] == 'ida')
        .map(
          (p) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(
              children: [
                Icon(
                  p['passou_em'] != null
                      ? Icons.check_circle
                      : Icons.radio_button_unchecked,
                  color: p['passou_em'] != null ? azulUnibus : bordaUnicap,
                  size: 22,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '${p['nome']}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Text(hora(p['passou_em'])),
              ],
            ),
          ),
        ),
    const TituloSecao('Desembarque'),
    ...mapas(v['pontos'])
        .where((p) => p['sentido'] == 'retorno')
        .map(
          (p) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('○  ${p['nome']}'),
          ),
        ),
    const SizedBox(height: 18),
    Cartao(
      child: Column(
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Quantidade de check-in',
                  style: TextStyle(fontSize: 12, color: cinzaUnicap),
                ),
              ),
              Text(
                '${v['presentes']}/${v['capacidade']}',
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value:
                  ((v['presentes'] as num? ?? 0) /
                          (v['capacidade'] as num? ?? 1))
                      .clamp(0, 1),
              minHeight: 6,
              color: azulUnibus,
              backgroundColor: const Color(0xFFE6EAF0),
            ),
          ),
        ],
      ),
    ),
    const SizedBox(height: 12),
    const Aviso(
      'Embarque da ida aberto\nQuando terminar o último ponto de embarque, toque em “Iniciar viagem”. O embarque da ida fecha nesse momento.',
      informativo: true,
    ),
    if (gps.erro != null) Aviso(gps.erro!),
  ];
  List<Widget> emViagem() => [
    MapaDaViagem(v, altura: 300),
    const SizedBox(height: 12),
    Cartao(
      cor: const Color(0xFFFFF8F2),
      borda: const Color(0xFFFFD9C2),
      child: Row(
        children: [
          const Icon(Icons.location_on, color: Color(0xFF101828)),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Próxima parada',
                  style: TextStyle(color: cinzaUnicap, fontSize: 10),
                ),
                Text(
                  '${v['proximo_ponto'] ?? 'Aguardando posição'}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
          Tooltip(
            message:
                '${v['previsao_metodo'] ?? 'Previsão disponível com GPS recente e ônibus em movimento.'}',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                const Text(
                  'Previsão',
                  style: TextStyle(color: cinzaUnicap, fontSize: 10),
                ),
                Text(
                  hora(v['previsao_chegada']),
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
    const SizedBox(height: 12),
    Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        Etiqueta(
          gps.erro != null
              ? 'Aguardando GPS'
              : gps.ultimoEnvio == null
              ? 'Obtendo localização'
              : 'GPS ativo',
          icone: Icons.gps_fixed,
        ),
        Etiqueta(
          '${v['presentes']} a bordo',
          fundo: const Color(0xFFFFE8DB),
          icone: Icons.people_outline,
        ),
      ],
    ),
    if (gps.erro != null) ...[const SizedBox(height: 12), Aviso(gps.erro!)],
  ];
  List<Widget> destino() => [
    statusGps(),
    const SizedBox(height: 14),
    Cartao(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('✓  Ida finalizada às ${hora(v['chegada_em'])}'),
          const SizedBox(height: 16),
          Text('✓  Embarque da volta aberto às ${hora(v['chegada_em'])}'),
        ],
      ),
    ),
    const TituloSecao('Embarque da volta'),
    Numeros({
      'embarcados': v['total_retorno'],
      'vagas': v['vagas_disponiveis'],
      'capacidade': v['capacidade'],
    }),
    const SizedBox(height: 14),
    const Cartao(
      child: Column(
        children: [
          CircleAvatar(
            radius: 28,
            backgroundColor: Color(0xFFFFE8DB),
            child: Icon(Icons.swap_horiz, color: laranjaUnibus),
          ),
          SizedBox(height: 12),
          Text(
            'Deseja iniciar o caminho de volta?',
            textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          SizedBox(height: 8),
          Text(
            'Ao iniciar, o embarque da volta fecha.',
            textAlign: TextAlign.center,
            style: TextStyle(color: cinzaUnicap, fontSize: 11),
          ),
        ],
      ),
    ),
  ];
  List<Widget> resumo() => [
    const Center(
      child: CircleAvatar(
        radius: 30,
        backgroundColor: Color(0xFFE4F2EB),
        child: Icon(Icons.check, color: verdeUnicap, size: 32),
      ),
    ),
    const SizedBox(height: 14),
    const Text(
      'Tudo registrado',
      textAlign: TextAlign.center,
      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
    ),
    const SizedBox(height: 6),
    Text(
      'GPS desligado. Obrigado pela viagem, ${nomeCurto(widget.usuario)}.',
      textAlign: TextAlign.center,
      style: const TextStyle(color: cinzaUnicap, fontSize: 11),
    ),
    const SizedBox(height: 16),
    Cartao(
      child: Column(
        children: [
          for (final e in {
            'iniciada_em': 'Rota iniciada',
            'partida_ida_em': 'Viagem iniciada (ida)',
            'chegada_em': 'Viagem finalizada (ida)',
            'partida_volta_em': 'Caminho de volta iniciado',
            'finalizada_em': 'Viagem de retorno finalizada',
          }.entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 7),
              child: Row(
                children: [
                  Text(
                    hora(v[e.key]),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12),
                    child: Icon(Icons.circle, color: laranjaUnibus, size: 9),
                  ),
                  Expanded(
                    child: Text(e.value, style: const TextStyle(fontSize: 12)),
                  ),
                ],
              ),
            ),
        ],
      ),
    ),
    const SizedBox(height: 14),
    Numeros({
      'na ida': v['total_ida'],
      'na volta': v['total_retorno'],
      'pontos da rota': mapas(v['pontos']).length,
    }),
    const SizedBox(height: 14),
    Aviso(
      v['encerrada_pelo_sistema'] == true
          ? 'Encerrada pelo sistema. A administração deve revisar esta viagem.'
          : 'Viagem não finalizada até 03:00 é encerrada pelo sistema e marcada para revisão do administrador.',
      informativo: true,
    ),
  ];
}
