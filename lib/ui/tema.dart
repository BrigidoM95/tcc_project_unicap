import 'package:flutter/material.dart';

const azulUnibus = Color(0xFF142C4D);
const laranjaUnibus = Color(0xFFAD4700);

ThemeData temaUnibus() => ThemeData(
  useMaterial3: true,
  fontFamily: 'Roboto',
  colorScheme: ColorScheme.fromSeed(
    seedColor: azulUnibus,
    primary: azulUnibus,
    secondary: laranjaUnibus,
  ),
  scaffoldBackgroundColor: const Color(0xFFF3F5F9),
  appBarTheme: const AppBarTheme(
    backgroundColor: azulUnibus,
    foregroundColor: Colors.white,
    centerTitle: false,
    elevation: 0,
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: laranjaUnibus,
      foregroundColor: Colors.white,
      minimumSize: const Size(0, 50),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: azulUnibus,
      minimumSize: const Size(0, 48),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xFFBCCADB)),
    ),
  ),
  cardTheme: CardThemeData(
    color: Colors.white,
    elevation: 0,
    margin: const EdgeInsets.only(bottom: 16),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Color(0xFFDCE3ED)),
    ),
  ),
);

class CartaoSecao extends StatelessWidget {
  final String titulo;
  final String? descricao;
  final Widget child;
  const CartaoSecao({
    super.key,
    required this.titulo,
    this.descricao,
    required this.child,
  });
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            titulo,
            style: const TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w700,
              color: azulUnibus,
            ),
          ),
          if (descricao != null) ...[
            const SizedBox(height: 8),
            Text(descricao!, style: const TextStyle(color: Color(0xFF526176))),
          ],
          const SizedBox(height: 18),
          child,
        ],
      ),
    ),
  );
}

class Aviso extends StatelessWidget {
  final String texto;
  final bool sucesso;
  const Aviso(this.texto, {super.key, this.sucesso = false});
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: sucesso ? const Color(0xFFE3F3E9) : const Color(0xFFFFEBE8),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          sucesso ? Icons.check_circle_outline : Icons.info_outline,
          color: sucesso ? Colors.green.shade800 : Colors.red.shade800,
        ),
        const SizedBox(width: 12),
        Expanded(child: Text(texto)),
      ],
    ),
  );
}

String horarioLocal(dynamic valor) {
  final d = DateTime.tryParse(valor?.toString() ?? '')?.toLocal();
  if (d == null) return '—';
  String n(int i) => i.toString().padLeft(2, '0');
  return '${n(d.day)}/${n(d.month)}/${d.year} às ${n(d.hour)}:${n(d.minute)}';
}
