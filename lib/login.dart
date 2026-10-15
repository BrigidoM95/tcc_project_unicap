import 'package:flutter/material.dart';

import './home.dart';
import './services/api_service.dart';
import './painel_motorista.dart';

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
    if (carregando) return;

    if (emailController.text.trim().isEmpty || senhaController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Informe o e-mail e a senha.')),
      );
      return;
    }

    setState(() => carregando = true);

    try {
      final response = await ApiService.login(
        emailController.text.trim(),
        senhaController.text,
      );

      if (response == null) {
        throw Exception(
          'Não foi possível entrar. Confira as credenciais '
          'e a conexão com o servidor.',
        );
      }

      final access = response['access'];
      final usuario = response['usuario'];

      if (access is! String || access.isEmpty || usuario is! Map) {
        throw Exception('Resposta inválida recebida do servidor.');
      }

      final dadosUsuario = Map<String, dynamic>.from(usuario);

      // Consulta o perfil no servidor, sem depender
      // do formato do campo "tipo" no retorno do login.
      final painel = await ApiService.painelMotorista(access);

      if (!mounted) return;

      final Widget destino = painel['motorista'] == true
          ? PainelMotorista(usuario: dadosUsuario, accessToken: access)
          : Home(usuario: dadosUsuario, accessToken: access);

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => destino),
      );
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(ApiService.mensagemErro(e))));
    } finally {
      if (mounted) {
        setState(() => carregando = false);
      }
    }
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
                      fillColor: Colors.white,
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
                      fillColor: Colors.white,
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
