import 'package:flutter/material.dart';
import './login.dart';
import 'ui/tema.dart';

void main() {
  runApp(const Main());
}

class Main extends StatelessWidget {
  const Main({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: temaUnibus(),
      home: const Login(),
      builder: (context, child) => ColoredBox(
        color: const Color(0xFFE4EAF2),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: child ?? const SizedBox.shrink(),
          ),
        ),
      ),
    );
  }
}
