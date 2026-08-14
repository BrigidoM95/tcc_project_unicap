import 'package:flutter/material.dart';

import './login.dart';
import './onibus.dart';

class Home extends StatelessWidget {
  final Map<String, dynamic> usuario;

  const Home({
    super.key,
    required this.usuario,
  });

  @override
  Widget build(BuildContext context) {
    if (usuario.isEmpty) {
      return const Scaffold(
        body: Center(
          child: Text('Usuário não autenticado'),
        ),
      );
    }

    final String tipo = usuario['tipo']?.toString().toLowerCase() ?? '';

    switch (tipo) {
      case 'associado':
        return _homeAssociado(context);

      case 'fiscal':
        return _homeFiscal(context);

      case 'motorista':
        return _homeMotorista(context);

      default:
        return _homePerfilInvalido(context);
    }
  }

  Widget _homeAssociado(BuildContext context) {
    final List<Map<String, dynamic>> lista = [
      {
        'nome': 'Rota 1',
        'capacidade': 48,
        'id': 1,
      },
      {
        'nome': 'Rota 2',
        'capacidade': 48,
        'id': 2,
      },
      {
        'nome': 'Rota 3',
        'capacidade': 48,
        'id': 3,
      },
    ];

    final List<String> imagens = [
      'assets/onibusPreto.png',
      'assets/onibusAzul.png',
      'assets/onibusLaranja.png',
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Bem-vindo, ${usuario["nome"] ?? ""}',
        ),
        backgroundColor: const Color(0xFFFF5E08),
        automaticallyImplyLeading: false,
      ),

      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),

          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Área do Associado',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 10),

              if (usuario['rua'] != null)
                Text(
                  'RUA: ${usuario["rua"]}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 16,
                  ),
                ),

              const SizedBox(height: 30),

              const Text(
                'Ônibus Disponíveis',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 20),

              for (int i = 0; i < lista.length; i++)
                _cardOnibus(
                  context,
                  lista[i],
                  imagens[i],
                ),

              const SizedBox(height: 20),

              _botaoSair(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _homeFiscal(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Bem-vindo, ${usuario["nome"] ?? ""}',
        ),
        backgroundColor: const Color(0xFFFF5E08),
        automaticallyImplyLeading: false,
      ),

      body: Padding(
        padding: const EdgeInsets.all(20),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Área do Fiscal',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 20),

            Text(
              'Usuário: ${usuario["nome"] ?? ""}',
              textAlign: TextAlign.center,
            ),

            Text(
              'E-mail: ${usuario["email"] ?? ""}',
              textAlign: TextAlign.center,
            ),

            const Spacer(),

            _botaoSair(context),
          ],
        ),
      ),
    );
  }

  Widget _homeMotorista(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Bem-vindo, ${usuario["nome"] ?? ""}',
        ),
        backgroundColor: const Color(0xFFFF5E08),
        automaticallyImplyLeading: false,
      ),

      body: Padding(
        padding: const EdgeInsets.all(20),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Área do Motorista',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 20),

            Text(
              'Usuário: ${usuario["nome"] ?? ""}',
              textAlign: TextAlign.center,
            ),

            Text(
              'E-mail: ${usuario["email"] ?? ""}',
              textAlign: TextAlign.center,
            ),

            const Spacer(),

            _botaoSair(context),
          ],
        ),
      ),
    );
  }


  Widget _homePerfilInvalido(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Acesso'),
        backgroundColor: const Color(0xFFFF5E08),
        automaticallyImplyLeading: false,
      ),

      body: Padding(
        padding: const EdgeInsets.all(20),

        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Perfil de usuário inválido.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 30),

            _botaoSair(context),
          ],
        ),
      ),
    );
  }


  Widget _cardOnibus(
    BuildContext context,
    Map<String, dynamic> onibus,
    String imagem,
  ) {
    final String nome = onibus['nome'] as String;
    final int capacidade = onibus['capacidade'] as int;
    final int rotaId = onibus['id'] as int;

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
              Image.asset(
                imagem,
                width: 220,
                height: 160,
                fit: BoxFit.contain,
              ),

              const SizedBox(height: 10),

              Text(
                nome,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),

              Text(
                'Capacidade: $capacidade',
              ),

              const SizedBox(height: 5),

              const Text(
                'Clique para embarcar',
              ),
            ],
          ),
        ),
      ),
    );
  }


  Widget _botaoSair(BuildContext context) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF1C3B6E),
        foregroundColor: Colors.white,
        minimumSize: const Size(
          double.infinity,
          50,
        ),
      ),

      onPressed: () {
        Navigator.pushAndRemoveUntil(
          context,
          MaterialPageRoute(
            builder: (_) => Login(),
          ),
          (route) => false,
        );
      },

      child: const Text('Sair'),
    );
  }
}