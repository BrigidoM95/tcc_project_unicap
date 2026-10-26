import 'package:flutter/material.dart';
import 'screens/viagens.dart';

class PainelMotorista extends StatelessWidget {
  final Map<String, dynamic> usuario;
  final String accessToken;
  const PainelMotorista({
    super.key,
    required this.usuario,
    required this.accessToken,
  });
  @override
  Widget build(BuildContext context) =>
      ViagensHoje(usuario: usuario, token: accessToken);
}
