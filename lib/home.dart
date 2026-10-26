import 'package:flutter/material.dart';
import 'screens/viagens.dart';

class Home extends StatelessWidget {
  final Map<String, dynamic> usuario;
  final String accessToken;
  const Home({super.key, required this.usuario, required this.accessToken});
  @override
  Widget build(BuildContext context) =>
      ViagensHoje(usuario: usuario, token: accessToken);
}
