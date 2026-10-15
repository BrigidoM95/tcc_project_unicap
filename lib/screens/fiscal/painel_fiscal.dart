import '../../ui/tema.dart';
import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import 'gerar_qr.dart';

class PainelFiscal extends StatefulWidget {
  final String accessToken;
  const PainelFiscal({super.key, required this.accessToken});
  @override
  State<PainelFiscal> createState() => _PainelFiscalState();
}

class _PainelFiscalState extends State<PainelFiscal> {
  List<dynamic> viagens = [];
  bool carregando = true;
  String? erro;
  @override
  void initState() {
    super.initState();
    carregar();
  }

  Future<void> carregar() async {
    setState(() {
      carregando = true;
      erro = null;
    });
    try {
      final d = await ApiService.embarques('viagens/', widget.accessToken);
      if (mounted) setState(() => viagens = d['viagens'] as List);
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Embarque — Fiscal'),
      backgroundColor: const Color(0xFF142C4D),
      actions: [
        IconButton(
          onPressed: carregando ? null : carregar,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: carregando
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (erro != null) Aviso(erro!),
              const Text(
                'Selecione a viagem para apresentar o QR Code. O motorista precisa iniciá-la primeiro.',
              ),
              if (viagens.isEmpty && erro == null)
                const Padding(
                  padding: EdgeInsets.all(20),
                  child: Text('Nenhuma viagem em andamento.'),
                ),
              ...viagens.map(
                (v) => Card(
                  child: ListTile(
                    title: Text('${v['rota_nome']} — ${v['sentido']}'),
                    subtitle: Text(
                      "${v['onibus_codigo']} / ${v['placa']} — ${v['vagas_disponiveis']} vagas",
                    ),
                    trailing: const Icon(Icons.qr_code),
                    onTap: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => GerarQr(
                            viagemId: v['id'] as int,
                            accessToken: widget.accessToken,
                          ),
                        ),
                      );
                      if (mounted) carregar();
                    },
                  ),
                ),
              ),
            ],
          ),
  );
}
