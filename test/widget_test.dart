import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:aulas_flutter/home.dart';
import 'package:aulas_flutter/login.dart';

void main() {
  testWidgets('Login mostra campos e botão de entrada', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Login()));

    expect(find.text('Login'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Entrar'), findsOneWidget);
  });

  testWidgets('Login permite digitar e-mail e senha', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Login()));

    await tester.enterText(find.byType(TextField).at(0), 'teste@email.com');

    await tester.enterText(find.byType(TextField).at(1), '12345678');

    final email = tester.widget<TextField>(find.byType(TextField).at(0));

    final senha = tester.widget<TextField>(find.byType(TextField).at(1));

    expect(email.controller!.text, 'teste@email.com');
    expect(senha.controller!.text, '12345678');
    expect(senha.obscureText, isTrue);
  });

  testWidgets('Login exige preenchimento dos campos', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Login()));

    await tester.ensureVisible(find.text('Entrar'));
    await tester.tap(find.text('Entrar'));
    await tester.pump();

    expect(find.text('Informe o e-mail e a senha.'), findsOneWidget);

    expect(find.byType(Login), findsOneWidget);
    expect(find.byType(Home), findsNothing);
  });

  testWidgets('Home mostra nome e erro ao carregar ônibus', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Home(
          usuario: {'id': 1, 'nome': 'Teste', 'tipo': 'associado'},
          accessToken: 'token-apenas-para-teste',
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Bem-vindo, Teste'), findsOneWidget);

    expect(find.text('Não foi possível carregar os ônibus.'), findsOneWidget);

    expect(find.text('Tentar novamente'), findsOneWidget);
    expect(find.text('Sair'), findsOneWidget);
  });

  testWidgets('Sair da Home retorna ao login', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Home(
          usuario: {'id': 1, 'nome': 'Teste', 'tipo': 'associado'},
          accessToken: 'token-apenas-para-teste',
        ),
      ),
    );

    await tester.pumpAndSettle();

    await tester.tap(find.text('Sair'));
    await tester.pumpAndSettle();

    expect(find.byType(Login), findsOneWidget);
    expect(find.byType(Home), findsNothing);
    expect(find.text('Entrar'), findsOneWidget);
  });
}
