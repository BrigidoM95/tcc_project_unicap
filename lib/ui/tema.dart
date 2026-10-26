import 'package:flutter/material.dart';

const azulUnibus = Color(0xFF1B396D),
    laranjaUnibus = Color(0xFFFC5C08),
    verdeUnicap = Color(0xFF137547),
    vermelhoUnicap = Color(0xFFB42318),
    cinzaUnicap = Color(0xFF667085),
    bordaUnicap = Color(0xFFDCE2EB),
    fundoSuave = Color(0xFFF3F4F7);
ThemeData temaUnibus() => ThemeData(
  useMaterial3: true,
  fontFamily: 'DejaVuSans',
  scaffoldBackgroundColor: Colors.white,
  colorScheme: ColorScheme.fromSeed(
    seedColor: azulUnibus,
    primary: azulUnibus,
    secondary: laranjaUnibus,
    surface: Colors.white,
  ),
  textTheme: const TextTheme(
    bodyLarge: TextStyle(fontSize: 14, color: azulUnibus, letterSpacing: 0),
    bodyMedium: TextStyle(fontSize: 13, color: azulUnibus, letterSpacing: 0),
    bodySmall: TextStyle(fontSize: 11, color: cinzaUnicap, letterSpacing: 0),
    labelLarge: TextStyle(fontSize: 14, letterSpacing: 0),
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: laranjaUnibus,
    foregroundColor: Color(0xFF101828),
    elevation: 0,
  ),
  elevatedButtonTheme: ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: laranjaUnibus,
      foregroundColor: const Color(0xFF101828),
      elevation: 0,
      minimumSize: const Size(double.infinity, 50),
      textStyle: const TextStyle(
        fontFamily: 'DejaVuSans',
        fontSize: 15,
        fontWeight: FontWeight.bold,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: azulUnibus,
      minimumSize: const Size(double.infinity, 50),
      side: const BorderSide(color: azulUnibus, width: 1.3),
      textStyle: const TextStyle(
        fontFamily: 'DejaVuSans',
        fontSize: 14,
        fontWeight: FontWeight.bold,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: azulUnibus, width: 1.3),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: azulUnibus, width: 1.3),
    ),
  ),
  cardTheme: CardThemeData(
    color: Colors.white,
    elevation: 0,
    margin: const EdgeInsets.only(bottom: 12),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: bordaUnicap, width: 1.3),
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
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            titulo,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          if (descricao != null) ...[
            const SizedBox(height: 8),
            Text(descricao!),
          ],
          const SizedBox(height: 16),
          child,
        ],
      ),
    ),
  );
}

class Aviso extends StatelessWidget {
  final String texto;
  final bool sucesso, informativo;
  const Aviso(
    this.texto, {
    super.key,
    this.sucesso = false,
    this.informativo = false,
  });
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: sucesso
          ? const Color(0xFFE4F2EB)
          : informativo
          ? const Color(0xFFE7EDF8)
          : const Color(0xFFFFF0E6),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          sucesso ? Icons.check_circle_outline : Icons.info_outline,
          size: 20,
          color: sucesso ? verdeUnicap : azulUnibus,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(texto, style: const TextStyle(fontSize: 12, height: 1.5)),
        ),
      ],
    ),
  );
}

String horarioLocal(dynamic valor) {
  final d = DateTime.tryParse(valor?.toString() ?? '')?.toLocal();
  if (d == null) return '—';
  String n(int i) => i.toString().padLeft(2, '0');
  return '${n(d.day)}/${n(d.month)}/${d.year} • ${n(d.hour)}:${n(d.minute)}';
}
