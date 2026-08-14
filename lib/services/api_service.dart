import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = "http://127.0.0.1:8000/";

  static Future<Map<String, dynamic>> login(String email, String senha) async {
    try {
      final response = await http.post(
        Uri.parse("${baseUrl}api/login/"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"email": email, "senha": senha}),
      );

      final Map<String, dynamic> dados = jsonDecode(response.body);

      if (response.statusCode == 200) {
        return {"sucesso": true, ...dados};
      }

      return {
        "sucesso": false,
        "erro": dados["erro"] ?? "Não foi possível realizar o login.",
      };
    } catch (e) {
      return {
        "sucesso": false,
        "erro": "Não foi possível conectar ao servidor.",
      };
    }
  }
}
