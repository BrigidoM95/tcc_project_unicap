import '../../ui/tema.dart';
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class HistoricoEmbarques extends StatefulWidget {
  final String accessToken;
  const HistoricoEmbarques({super.key, required this.accessToken});
  @override
  State<HistoricoEmbarques> createState() => _HistoricoEmbarquesState();
}

class _HistoricoEmbarquesState extends State<HistoricoEmbarques> {
  List<dynamic> itens = [];
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
      final d = await ApiService.embarques('historico/', widget.accessToken);
      if (mounted) setState(() => itens = d['checkins'] as List);
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Meus embarques'),
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
              if (itens.isEmpty && erro == null)
                const Text('Nenhum embarque registrado.'),
              ...itens.map(
                (c) => Card(
                  child: ListTile(
                    title: Text("${c['rota_nome']} — ${c['sentido']}"),
                    subtitle: Text(
                      "${c['onibus_codigo']} / ${c['placa']}\n${horarioLocal(c['registrado_em'])}",
                    ),
                  ),
                ),
              ),
            ],
          ),
  );
}
