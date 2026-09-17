import 'package:flutter/material.dart';

import './login.dart';
import './onibus.dart';
import './services/api_service.dart';

class Home extends StatefulWidget {
  final Map<String, dynamic> usuario;
  final String accessToken;

  const Home({super.key, required this.usuario, required this.accessToken});

  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  bool carregando = true;

  String? erro;

  List<Map<String, dynamic>> onibus = [];

  @override
  void initState() {
    super.initState();

    carregarOnibus();
  }

  Future<void> carregarOnibus() async {
    setState(() {
      carregando = true;
      erro = null;
    });

    try {
      final resultado = await ApiService.listarOnibus(widget.accessToken);

      if (!mounted) {
        return;
      }

      setState(() {
        onibus = resultado;
        carregando = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }

      setState(() {
        carregando = false;
        erro = e.toString();
      });
    }
  }

  void sair() {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const Login()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final nome = widget.usuario['nome']?.toString() ?? 'Usuário';

    return Scaffold(
      appBar: AppBar(
        title: Text('Bem-vindo, $nome'),
        backgroundColor: const Color(0xFFFF5E08),
        actions: [
          IconButton(
            onPressed: carregarOnibus,
            tooltip: 'Atualizar',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),

      body: RefreshIndicator(onRefresh: carregarOnibus, child: _conteudo()),

      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            onPressed: sair,
            icon: const Icon(Icons.logout),
            label: const Text('Sair'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1C3B6E),
              foregroundColor: Colors.white,
              minimumSize: const Size(double.infinity, 50),
            ),
          ),
        ),
      ),
    );
  }

  Widget _conteudo() {
    if (carregando) {
      return const Center(child: CircularProgressIndicator());
    }

    if (erro != null) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(30),
        children: [
          const SizedBox(height: 100),

          const Icon(Icons.error_outline, size: 70, color: Colors.red),

          const SizedBox(height: 20),

          const Text(
            'Não foi possível carregar os ônibus.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),

          const SizedBox(height: 10),

          Text(erro!, textAlign: TextAlign.center),

          const SizedBox(height: 25),

          ElevatedButton(
            onPressed: carregarOnibus,
            child: const Text('Tentar novamente'),
          ),
        ],
      );
    }

    if (onibus.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(30),
        children: const [
          SizedBox(height: 120),

          Icon(Icons.directions_bus_outlined, size: 80, color: Colors.grey),

          SizedBox(height: 20),

          Text(
            'Nenhum ônibus disponível.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),

          SizedBox(height: 10),

          Text(
            'Os ônibus ativos cadastrados no sistema administrativo aparecerão aqui.',
            textAlign: TextAlign.center,
          ),
        ],
      );
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Ônibus disponíveis',
          style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
        ),

        const SizedBox(height: 5),

        const Text(
          'Selecione um veículo para visualizar os detalhes.',
          style: TextStyle(color: Colors.grey),
        ),

        const SizedBox(height: 20),

        ...onibus.map((item) => _cardOnibus(item)),
      ],
    );
  }

  Widget _cardOnibus(Map<String, dynamic> item) {
    final foto = ApiService.tratarUrlImagem(item['foto']?.toString());

    final codigo = item['codigo']?.toString() ?? '-';

    final nome = item['nome']?.toString() ?? 'Ônibus';

    final placa = item['placa']?.toString() ?? '-';

    final capacidade = item['capacidade']?.toString() ?? '0';

    final motorista =
        item['motorista_nome']?.toString().trim().isNotEmpty == true
        ? item['motorista_nome'].toString()
        : 'Não informado';

    return Card(
      margin: const EdgeInsets.only(bottom: 20),
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
      child: InkWell(
        borderRadius: BorderRadius.circular(15),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => Onibus(dados: item)),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (foto.isNotEmpty)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    foto,
                    width: double.infinity,
                    height: 190,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) {
                      return _semImagem();
                    },
                  ),
                )
              else
                _semImagem(),

              const SizedBox(height: 15),

              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      nome,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),

                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.green.shade100,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Text(
                      'Ativo',
                      style: TextStyle(
                        color: Colors.green,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 10),

              Text('Código: $codigo'),

              Text('Placa: $placa'),

              Text('Capacidade: $capacidade passageiros'),

              Text('Motorista: $motorista'),

              const SizedBox(height: 15),

              const Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    'Ver detalhes',
                    style: TextStyle(
                      color: Color(0xFF1C3B6E),
                      fontWeight: FontWeight.bold,
                    ),
                  ),

                  SizedBox(width: 5),

                  Icon(
                    Icons.arrow_forward_ios,
                    size: 15,
                    color: Color(0xFF1C3B6E),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _semImagem() {
    return Container(
      width: double.infinity,
      height: 190,
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Icon(Icons.directions_bus, size: 80, color: Colors.grey),
    );
  }
}
