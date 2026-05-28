class Usuario {
  final int id;
  final String nome;
  final String tipo;
  final String token;

  Usuario({
    required this.id,
    required this.nome,
    required this.tipo,
    required this.token,
  });

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['user']['id'],
      nome: json['user']['nome'],
      tipo: json['user']['tipo'],
      token: json['token'],
    );
  }

  bool get isAdmin => tipo == "admin";
}
