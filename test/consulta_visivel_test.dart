import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aulas_flutter/services/api_service.dart';
import 'package:aulas_flutter/services/consulta_visivel.dart';

class TelaConsulta extends StatefulWidget {
  final Future<void> Function() carregar;
  const TelaConsulta(this.carregar, {super.key});
  @override
  State<TelaConsulta> createState() => _TelaConsultaState();
}

class _TelaConsultaState extends EstadoComConsulta<TelaConsulta> {
  @override
  Duration get intervaloConsulta => const Duration(seconds: 10);
  @override
  Future<void> consultar() async {
    try {
      await widget.carregar();
    } catch (e) {
      falhaConsulta(e);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: TextButton(
      onPressed: () => Navigator.push(
        context,
        MaterialPageRoute(
          builder: (c) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.pop(c),
              child: const Text('Voltar'),
            ),
          ),
        ),
      ),
      child: const Text('Abrir detalhe'),
    ),
  );
}

void main() {
  testWidgets(
    'Consulta pausa em rota oculta e background e retoma imediatamente',
    (t) async {
      var chamadas = 0;
      await t.pumpWidget(
        MaterialApp(
          navigatorObservers: [observadorConsultas],
          home: TelaConsulta(() async {
            chamadas++;
          }),
        ),
      );
      await t.pump();
      expect(chamadas, 1);
      await t.pump(const Duration(seconds: 9));
      expect(chamadas, 1);
      await t.pump(const Duration(seconds: 1));
      expect(chamadas, 2);
      await t.tap(find.text('Abrir detalhe'));
      await t.pumpAndSettle();
      await t.pump(const Duration(seconds: 30));
      expect(chamadas, 2);
      await t.tap(find.text('Voltar'));
      await t.pumpAndSettle();
      expect(chamadas, 3);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await t.pump(const Duration(seconds: 30));
      expect(chamadas, 3);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await t.pump();
      expect(chamadas, 4);
      await t.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('Consulta para definitivamente ao receber403 ou404', (t) async {
    for (final status in [403, 404]) {
      var chamadas = 0;
      await t.pumpWidget(
        MaterialApp(
          navigatorObservers: [observadorConsultas],
          home: TelaConsulta(() async {
            chamadas++;
            throw ApiException('Acesso removido', status: status);
          }),
        ),
      );
      await t.pump();
      await t.pump(const Duration(minutes: 1));
      expect(chamadas, 1);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await t.pump();
      expect(chamadas, 1);
      await t.pumpWidget(const SizedBox.shrink());
    }
  });

  test('Intervalo curto só acompanha janela de escolha ou embarque aberta', () {
    expect(intervaloDaViagem({'escolha_aberta': true}).inSeconds, 3);
    expect(intervaloDaViagem({'embarque_aberto': true}).inSeconds, 3);
    expect(
      intervaloDaViagem({
        'embarque_aberto': false,
        'escolha_aberta': false,
      }).inSeconds,
      15,
    );
  });
}
