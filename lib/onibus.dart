import 'package:flutter/material.dart';

class Onibus extends StatelessWidget {
  final String imagem;
  final String rota;
  final String capacidade;
  final Map<String, dynamic> usuario;
  final int rotaId;

  const Onibus({
    super.key,
    required this.imagem,
    required this.rota,
    required this.capacidade,
    required this.usuario,
    required this.rotaId,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ônibus'),
        backgroundColor: const Color(0xFFFF5E08),
      ),
      body: Center(
        child: ElevatedButton(
          onPressed: () => Navigator.pop(context),
          child: const Text("Voltar"),
        ),
      ),
    );
  }
}
