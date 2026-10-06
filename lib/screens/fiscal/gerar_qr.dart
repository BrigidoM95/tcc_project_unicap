import 'package:flutter/services.dart';
import '../../ui/tema.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../services/api_service.dart';

class GerarQr extends StatefulWidget {
  final int viagemId;
  final String accessToken;
  const GerarQr({super.key, required this.viagemId, required this.accessToken});
  @override
  State<GerarQr> createState() => _GerarQrState();
}

class _GerarQrState extends State<GerarQr> {
  Map<String, dynamic>? qr;
  Map<String, dynamic>? presencas;
  String? erro;
  bool ocupado = false;
  bool atualizando = false;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    gerar();
    timer = Timer.periodic(const Duration(seconds: 15), (_) => atualizar());
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> gerar() async {
    if (ocupado) return;
    setState(() {
      ocupado = true;
      erro = null;
      qr = null;
    });
    try {
      final d = await ApiService.embarques(
        'viagens/${widget.viagemId}/qr/',
        widget.accessToken,
        corpo: {},
      );
      if (mounted) setState(() => qr = d);
      await atualizar();
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  Future<void> atualizar() async {
    if (qr == null || atualizando) return;
    atualizando = true;
    try {
      final d = await ApiService.embarques(
        'viagens/${widget.viagemId}/presencas/',
        widget.accessToken,
      );
      if (mounted)
        setState(() {
          presencas = d;
          erro = null;
        });
    } catch (e) {
      if (mounted)
        setState(() {
          erro = ApiService.mensagemErro(e);
          qr = null;
          presencas = null;
        });
    } finally {
      atualizando = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = presencas?['viagem'] ?? qr?['viagem'];
    final expiracao = DateTime.tryParse(qr?['expira_em']?.toString() ?? '');
    final valido =
        expiracao != null &&
        expiracao.isAfter(DateTime.now()) &&
        v?['status'] == 'em_andamento';
    return Scaffold(
      appBar: AppBar(
        title: const Text('QR Code do fiscal'),
        backgroundColor: const Color(0xFF142C4D),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (erro != null) Aviso(erro!),
          if (v != null)
            CartaoSecao(
              titulo: "${v['rota_nome']} — ${v['sentido']}",
              descricao: "${v['onibus_codigo']} / ${v['placa']}",
              child: Wrap(
                spacing: 12,
                runSpacing: 10,
                children: [
                  Chip(
                    avatar: const Icon(Icons.people_outline),
                    label: Text("${v['presentes']} presentes"),
                  ),
                  Chip(
                    avatar: const Icon(Icons.event_seat_outlined),
                    label: Text("${v['vagas_disponiveis']} vagas"),
                  ),
                ],
              ),
            ),
          CartaoSecao(
            titulo: 'Código de embarque',
            descricao:
                'Apresente o QR Code ou informe o código curto ao associado.',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (ocupado) const Center(child: CircularProgressIndicator()),
                if (qr != null && valido) ...[
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 260),
                      child: AspectRatio(
                        aspectRatio: 1,
                        child: QrImageView(
                          data: qr!['codigo'] as String,
                          backgroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  SelectableText(
                    qr!['codigo_manual']?.toString() ?? '',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1,
                      color: azulUnibus,
                    ),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () async {
                      await Clipboard.setData(
                        ClipboardData(
                          text: qr!['codigo_manual']?.toString() ?? '',
                        ),
                      );
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Código copiado.')),
                      );
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copiar código'),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Válido até ${horarioLocal(qr!["expira_em"])}',
                    textAlign: TextAlign.center,
                  ),
                ] else if (!ocupado)
                  const Aviso(
                    'Código indisponível ou expirado. Gere um novo para continuar.',
                  ),
                const SizedBox(height: 20),
                ElevatedButton.icon(
                  onPressed: ocupado ? null : gerar,
                  icon: const Icon(Icons.refresh),
                  label: Text(ocupado ? 'Gerando...' : 'Gerar novo código'),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Ao gerar um novo código, o anterior deixa de funcionar.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Color(0xFF526176)),
                ),
              ],
            ),
          ),
          CartaoSecao(
            titulo: 'Presenças confirmadas',
            descricao: 'Atualização automática a cada 15 segundos.',
            child: Column(
              children: [
                if (((presencas?['checkins'] as List?) ?? []).isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('Nenhum embarque confirmado nesta lista.'),
                  ),
                ...((presencas?['checkins'] as List?) ?? []).map(
                  (c) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(
                      Icons.check_circle,
                      color: Colors.green,
                    ),
                    title: Text('${c['nome']}'),
                    subtitle: Text(
                      "${c['rua']} — ${horarioLocal(c['registrado_em'])}",
                    ),
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
