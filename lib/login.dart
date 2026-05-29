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
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset(
              'assets/logo.jpeg',
              width: 200,
              height: 200,
              fit: BoxFit.contain,
            ),

            Text(
              textAlign: TextAlign.left,
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              'Login',
            ),

            TextField(
              controller: emailController,
              decoration: InputDecoration(
                filled: true,
                fillColor: Color(0xFFFF5E08),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                labelText: 'Email',
                labelStyle: TextStyle(color: Colors.black),
              ),
            ),

            const SizedBox(height: 5),

            TextField(
              controller: senhaController,
              decoration: InputDecoration(
                filled: true,
                fillColor: Color(0xFFFF5E08),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),

                labelText: 'Senha',
                labelStyle: TextStyle(color: Colors.black),
              ),

              obscureText: true,
            ),

            const SizedBox(height: 10),

            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1C3B6E),
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 50),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),

              onPressed: () async {
                final response = await ApiService.login(
                  emailController.text.trim(),
                  senhaController.text.trim(),
                );
                if (response != null) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => Home(usuario: response),
                    ),
                  );
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Login inválido')),
                  );
                }
              },
              child: const Text('Entrar'),
            ),
          ],
        ),
      ),
    );
  }
}
