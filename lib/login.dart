import 'package:flutter/material.dart';
import './home.dart';
import './services/api_service.dart';

class Login extends StatelessWidget {
  Login({super.key});

  final TextEditingController emailController = TextEditingController();
  final TextEditingController senhaController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: SizedBox(
            width: 400,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Image.asset(
                  'assets/logo.jpeg',
                  width: 200,
                  height: 200,
                  fit: BoxFit.contain,
                ),

                const SizedBox(height: 20),

                const Text(
                  'Login',
                  textAlign: TextAlign.left,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                const SizedBox(height: 15),

                TextField(
                  controller: emailController,
                  keyboardType: TextInputType.emailAddress,
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: const Color(0xFFFF5E08),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    labelText: 'E-mail',
                    labelStyle: const TextStyle(
                      color: Colors.black,
                    ),
                  ),
                ),

                const SizedBox(height: 10),

                TextField(
                  controller: senhaController,
                  obscureText: true,
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: const Color(0xFFFF5E08),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    labelText: 'Senha',
                    labelStyle: const TextStyle(
                      color: Colors.black,
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1C3B6E),
                    foregroundColor: Colors.white,
                    minimumSize: const Size(
                      double.infinity,
                      50,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),

                  onPressed: () async {
                    final email = emailController.text.trim();
                    final senha = senhaController.text;

                    if (email.isEmpty || senha.isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Informe o e-mail e a senha.',
                          ),
                        ),
                      );

                      return;
                    }

                    final response = await ApiService.login(
                      email,
                      senha,
                    );

                    if (!context.mounted) {
                      return;
                    }

                    if (response["sucesso"] == true) {
                      final usuario = response["usuario"];

                      Navigator.pushReplacement(
                        context,
                        MaterialPageRoute(
                          builder: (context) => Home(
                            usuario: usuario,
                          ),
                        ),
                      );
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            response["erro"] ??
                                "Não foi possível realizar o login.",
                          ),
                        ),
                      );
                    }
                  },

                  child: const Text(
                    'Entrar',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}