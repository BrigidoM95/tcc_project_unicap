import 'package:flutter/material.dart';

class SelecionarAssento extends StatefulWidget {
  final int associadoId;
  final int rotaId;

  const SelecionarAssento({
    super.key,
    required this.associadoId,
    required this.rotaId,
  });

  @override
  State<SelecionarAssento> createState() => _SelecionarAssentoState();
}

class _SelecionarAssentoState extends State<SelecionarAssento> {
  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text("Selecionar Assento")));
  }
}
