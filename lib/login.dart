import 'dart:async';
import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'services/armazenamento.dart';
import 'services/fila_offline.dart';
import 'services/rastreamento.dart';
import 'screens/viagens.dart';
import 'ui/componentes.dart';
import 'ui/tema.dart';

class Login extends StatefulWidget {
  const Login({super.key});
  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  final emailController = TextEditingController(),
      senhaController = TextEditingController();
  bool carregando = false, visivel = false;
  String? erro;
  @override
  void initState() {
    super.initState();
    FilaOffline.instancia.parar();
    if (Rastreamento.instancia.ativo) Rastreamento.instancia.parar();
    ApiService.encerrarSessao();
    // Remove credenciais de versões anteriores sem apagar a fila por usuário.
    unawaited(Armazenamento.apagar('sessao').catchError((_) {}));
  }

  @override
  void dispose() {
    emailController.dispose();
    senhaController.dispose();
    super.dispose();
  }

  Future<void> abrir(Dados d) async {
    final u = Map<String, dynamic>.from(d['usuario'] as Map),
        token = d['access'] as String;
    await FilaOffline.instancia.iniciar(token, '${u['id']}');
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ViagensHoje(usuario: u, token: token),
      ),
    );
  }

  Future<void> entrar() async {
    if (carregando) return;
    if (emailController.text.trim().isEmpty || senhaController.text.isEmpty) {
      setState(() => erro = 'Informe o e-mail ou RUA e a senha.');
      return;
    }
    setState(() {
      carregando = true;
      erro = null;
    });
    try {
      final d = await ApiService.login(
        emailController.text.trim(),
        senhaController.text,
      );
      if (d == null) throw ApiException('E-mail, RUA ou senha inválidos.');
      await abrir(d);
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: LayoutBuilder(
        builder: (context, c) => SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: c.maxHeight),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 30),
              child: IntrinsicHeight(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    SizedBox(height: c.maxHeight > 650 ? 90 : 28),
                    Center(
                      child: Image.asset(
                        'assets/logo_unicap.png',
                        width: 110,
                        height: 115,
                        fit: BoxFit.contain,
                      ),
                    ),
                    const SizedBox(height: 30),
                    const Text(
                      'Acesse sua conta',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 7),
                    const Text(
                      'Associado, fiscal ou motorista',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: cinzaUnicap, fontSize: 12),
                    ),
                    const SizedBox(height: 30),
                    if (erro != null) Aviso(erro!),
                    const Text(
                      'E-mail ou RUA',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 7),
                    TextField(
                      controller: emailController,
                      enabled: !carregando,
                      autocorrect: false,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [AutofillHints.username],
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.badge_outlined, size: 20),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Senha',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 7),
                    TextField(
                      controller: senhaController,
                      enabled: !carregando,
                      obscureText: !visivel,
                      autofillHints: const [AutofillHints.password],
                      onSubmitted: (_) => entrar(),
                      decoration: InputDecoration(
                        prefixIcon: const Icon(Icons.lock_outline, size: 20),
                        suffixIcon: IconButton(
                          tooltip: visivel ? 'Ocultar senha' : 'Exibir senha',
                          onPressed: () => setState(() => visivel = !visivel),
                          icon: Icon(
                            visivel
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                            size: 20,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Botao('Entrar', onPressed: entrar, ocupado: carregando),
                    const SizedBox(height: 18),
                    const Text(
                      'Esqueceu a senha?',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: cinzaUnicap),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Procure a administração da UNICAP.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    const Padding(
                      padding: EdgeInsets.only(top: 30, bottom: 22),
                      child: Text(
                        'Transporte universitário UNICAP',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 10, color: cinzaUnicap),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
