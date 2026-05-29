import 'package:flutter/material.dart';

class RotaMotorista extends StatefulWidget {
  final int rotaId;

  const RotaMotorista({super.key, required this.rotaId});

  @override
  State<RotaMotorista> createState() => _RotaMotoristaState();
}

class _RotaMotoristaState extends State<RotaMotorista> {
  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text("Iniciar Rota")));
  }
}
