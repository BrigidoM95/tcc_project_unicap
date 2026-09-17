import 'package:flutter/material.dart';

import './home.dart';
import './services/api_service.dart';

class Login extends StatefulWidget {
  const Login({super.key});

  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  final TextEditingController emailController = TextEditingController();

  final TextEditingController senhaController = TextEditingController();

  bool carregando = false;

  @override
  void dispose() {
    emailController.dispose();
    senhaController.dispose();

    super.dispose();
  }

  Future<void> realizarLogin() async {
    if (emailController.text.trim().isEmpty || senhaController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Informe o e-mail e a senha.')),
      );

      return;
    }

    setState(() {
      carregando = true;
    });

    final response = await ApiService.login(
      emailController.text.trim(),
      senhaController.text,
    );

    if (!mounted) {
      return;
    }

    setState(() {
      carregando = false;
    });

    if (response == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('E-mail ou senha inválidos.')),
      );

      return;
    }

    final access = response['access'];

    final usuario = response['usuario'];

    if (access == null || usuario == null || usuario is! Map) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Resposta inválida recebida do servidor.'),
        ),
      );

      return;
    }

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => Home(
          usuario: Map<String, dynamic>.from(usuario),
          accessToken: access.toString(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 450),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Image.asset(
                    'assets/logo.jpeg',
                    width: 180,
                    height: 180,
                    fit: BoxFit.contain,
                  ),

                  const SizedBox(height: 25),

                  const Text(
                    'Login',
                    style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
                  ),

                  const SizedBox(height: 20),

                  TextField(
                    controller: emailController,
                    keyboardType: TextInputType.emailAddress,
                    decoration: InputDecoration(
                      labelText: 'E-mail',
                      filled: true,
                      fillColor: const Color(0xFFFF5E08),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),

                  const SizedBox(height: 12),

                  TextField(
                    controller: senhaController,
                    obscureText: true,
                    onSubmitted: (_) {
                      if (!carregando) {
                        realizarLogin();
                      }
                    },
                    decoration: InputDecoration(
                      labelText: 'Senha',
                      filled: true,
                      fillColor: const Color(0xFFFF5E08),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  ElevatedButton(
                    onPressed: carregando ? null : realizarLogin,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF1C3B6E),
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 52),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: carregando
                        ? const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Entrar'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
