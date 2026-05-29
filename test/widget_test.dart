// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aulas_flutter/login.dart';
import 'package:aulas_flutter/home.dart';
import 'package:aulas_flutter/services/api_service.dart';

void main() {
  testWidgets('Tela de login', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Login()));

    expect(find.text('Login'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Entrar'), findsOneWidget);
  });

  testWidgets('Digitar email e senha', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Login()));

    await tester.enterText(find.byType(TextField).at(0), 'teste@email.com');
    await tester.enterText(find.byType(TextField).at(1), '123456');

    expect(find.text('teste@email.com'), findsOneWidget);
    expect(find.text('123456'), findsOneWidget);
  });

  test('Login retorna null com dados inválidos', () async {
    final result = await ApiService.login("errado", "123");
    expect(result, null);
  });

  test('Entidade usuário deve conter campos básicos', () {
    final usuario = {"id": 1, "nome": "Teste", "tipo": "associado"};

    expect(usuario.containsKey("id"), true);
    expect(usuario.containsKey("nome"), true);
    expect(usuario.containsKey("tipo"), true);
  });

  testWidgets('Home bloqueia acesso sem login', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Home(usuario: {})));

    expect(find.text("Usuário não autenticado"), findsOneWidget);
  });

  testWidgets('Home mostra 3 ônibus', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: Home(usuario: {"nome": "Teste"})),
    );

    await tester.pump();

    expect(find.text("Rota 1"), findsOneWidget);
    expect(find.text("Rota 2"), findsOneWidget);
    expect(find.text("Rota 3"), findsOneWidget);
  });
}
