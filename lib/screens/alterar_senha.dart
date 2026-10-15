import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../login.dart';

class AlterarSenha extends StatefulWidget {
  final String accessToken;
  const AlterarSenha({super.key, required this.accessToken});
  @override
  State<AlterarSenha> createState() => _AlterarSenhaState();
}

class _AlterarSenhaState extends State<AlterarSenha> {
  final atual = TextEditingController(),
      nova = TextEditingController(),
      confirmacao = TextEditingController();
  bool enviando = false;
  String? erro;
  @override
  void dispose() {
    atual.dispose();
    nova.dispose();
    confirmacao.dispose();
    super.dispose();
  }

  Future<void> salvar() async {
    if (nova.text != confirmacao.text) {
      setState(() => erro = 'As senhas não coincidem.');
      return;
    }
    setState(() {
      enviando = true;
      erro = null;
    });
    try {
      await ApiService.alterarSenha(atual.text, nova.text, widget.accessToken);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Senha alterada. Entre novamente.')),
      );
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (_) => const Login()),
        (_) => false,
      );
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Alterar senha')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text('Use ao menos 8 caracteres e evite senhas comuns.'),
        const SizedBox(height: 20),
        TextField(
          controller: atual,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Senha atual'),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: nova,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Nova senha'),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: confirmacao,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Confirmar nova senha'),
        ),
        if (erro != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(erro!, style: const TextStyle(color: Colors.red)),
          ),
        const SizedBox(height: 20),
        ElevatedButton(
          onPressed: enviando ? null : salvar,
          child: Text(enviando ? 'Salvando...' : 'Salvar senha'),
        ),
      ],
    ),
  );
}
