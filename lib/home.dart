import 'package:flutter/material.dart';
import './onibus.dart';

class Home extends StatelessWidget {
  final Map<String, dynamic> usuario;

  const Home({super.key, required this.usuario});

  @override
  Widget build(BuildContext context) {
    if (usuario.isEmpty) {
      return const Scaffold(
        body: Center(child: Text("Usuário não autenticado")),
      );
    }

    final List<Map<String, dynamic>> lista = [
      {"nome": "Rota 1", "capacidade": 48, "id": 1},
      {"nome": "Rota 2", "capacidade": 48, "id": 2},
      {"nome": "Rota 3", "capacidade": 48, "id": 3},
    ];

    final imagens = [
      'assets/onibusPreto.png',
      'assets/onibusAzul.png',
      'assets/onibusLaranja.png',
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text('Bem Vindo, ${usuario["nome"] ?? ""}'),
        backgroundColor: const Color(0xFFFF5E08),
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              const Text(
                'Ônibus Disponíveis',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),

              const SizedBox(height: 20),

              for (int i = 0; i < lista.length; i++)
                _cardOnibus(context, lista[i], imagens[i]),

              const SizedBox(height: 20),

              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1C3B6E),
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 50),
                ),
                onPressed: () => Navigator.pop(context),
                child: const Text('Sair'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cardOnibus(
    BuildContext context,
    Map<String, dynamic> onibus,
    String imagem,
  ) {
    final String nome = onibus["nome"] as String;
    final int capacidade = onibus["capacidade"] as int;
    final int rotaId = onibus["id"] as int;

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => Onibus(
              imagem: imagem,
              rota: nome,
              capacidade: 'Capacidade: $capacidade',
              usuario: usuario,
              rotaId: rotaId,
            ),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 25),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: const [
            BoxShadow(
              blurRadius: 10,
              offset: Offset(0, 5),
              color: Colors.black26,
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(15),
          child: Column(
            children: [
              Image.asset(imagem, width: 220, height: 160, fit: BoxFit.contain),

              const SizedBox(height: 10),

              Text(
                nome,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),

              Text('Capacidade: $capacidade'),

              const SizedBox(height: 5),

              const Text('Clique para embarcar'),
            ],
          ),
        ),
      ),
    );
  }
}
