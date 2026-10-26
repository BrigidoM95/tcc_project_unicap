import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/api_service.dart';
import 'tema.dart';

typedef Dados = Map<String, dynamic>;

class EscolhaPonto extends StatelessWidget {
  final Dados viagem;
  final int? selecionado;
  final String? sentido;
  final String rotulo;
  final ValueChanged<int?> onChanged;
  const EscolhaPonto({
    super.key,
    required this.viagem,
    this.selecionado,
    this.sentido,
    this.rotulo = 'Ponto de embarque',
    required this.onChanged,
  });
  @override
  Widget build(BuildContext context) {
    final pontos = mapas(
      viagem['pontos'],
    ).where((p) => p['sentido'] == (sentido ?? viagem['sentido'])).toList();
    final valor = pontos.any((p) => p['id'] == selecionado)
        ? selecionado
        : pontos.length == 1
        ? pontos.first['id'] as int
        : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: DropdownButtonFormField<int>(
        key: ValueKey(
          '$sentido:$valor:${pontos.map((p) => p['id']).join(',')}',
        ),
        initialValue: valor,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: rotulo,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 14,
          ),
        ),
        items: pontos
            .map(
              (p) => DropdownMenuItem(
                value: p['id'] as int,
                child: Text(
                  '${p['nome']}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            )
            .toList(),
        onChanged: pontos.length == 1 ? null : onChanged,
      ),
    );
  }
}

String trajetoNome(dynamic t) => t == 'ida_volta'
    ? 'Ida e volta'
    : t == 'volta'
    ? 'Só volta'
    : 'Só ida';
String direcaoDestino(Dados v) => v['sentido'] == 'retorno'
    ? 'Volta • saindo de ${v['destino']}'
    : 'Ida • para ${v['destino']}';

List<Dados> mapas(dynamic valor) => (valor as List? ?? [])
    .map((e) => Map<String, dynamic>.from(e as Map))
    .toList();
String sentidoNome(dynamic s) => s == 'retorno' ? 'Volta' : 'Ida';
// O servidor envia este horário no fuso da operação, independente do aparelho.
String horaOperacao(dynamic valor) =>
    RegExp(r'T(\d{2}:\d{2})').firstMatch('$valor')?.group(1) ?? '08:00';
String hora(dynamic valor) {
  final d = DateTime.tryParse('$valor')?.toLocal();
  return d == null
      ? '—'
      : '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
}

String nomeCurto(Dados u) => (u['nome']?.toString() ?? '').split(' ').first;
String dataCompleta(dynamic valor) {
  final d = DateTime.tryParse('$valor');
  if (d == null) return 'Data não informada';
  const dias = [
    'segunda',
    'terça',
    'quarta',
    'quinta',
    'sexta',
    'sábado',
    'domingo',
  ];
  return '${dias[d.weekday - 1]}, ${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';
}

String dataHoje() {
  final d = DateTime.now();
  const dias = [
    'Segunda',
    'Terça',
    'Quarta',
    'Quinta',
    'Sexta',
    'Sábado',
    'Domingo',
  ];
  return '${dias[d.weekday - 1]}, ${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}';
}

String iniciais(String nome) => nome
    .trim()
    .split(RegExp(r'\s+'))
    .take(2)
    .map((e) => e.isEmpty ? '' : e[0])
    .join()
    .toUpperCase();

class TelaUnicap extends StatelessWidget {
  final String titulo, subtitulo;
  final String? saudacao;
  final Widget child;
  final List<Widget> acoes;
  final Widget? rodape, topoAcao;
  final bool rolar, compacto;
  const TelaUnicap({
    super.key,
    required this.titulo,
    this.subtitulo = '',
    this.saudacao,
    required this.child,
    this.acoes = const [],
    this.rodape,
    this.topoAcao,
    this.rolar = true,
    this.compacto = false,
  });
  @override
  Widget build(BuildContext context) => AnnotatedRegion<SystemUiOverlayStyle>(
    value: const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.white,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
    child: Scaffold(
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: EdgeInsets.fromLTRB(
              24,
              MediaQuery.paddingOf(context).top + (compacto ? 20 : 48),
              24,
              compacto ? 16 : 24,
            ),
            decoration: const BoxDecoration(
              color: laranjaUnibus,
              borderRadius: BorderRadius.vertical(bottom: Radius.circular(40)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (saudacao != null)
                        Text(
                          saudacao!,
                          style: const TextStyle(
                            fontSize: 15,
                            color: Color(0xFF101828),
                          ),
                        ),
                      Text(
                        titulo,
                        style: const TextStyle(
                          fontSize: 23,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF101828),
                          height: 1.3,
                        ),
                      ),
                      if (subtitulo.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(
                          subtitulo,
                          style: const TextStyle(
                            fontSize: 11,
                            color: Color(0xFF101828),
                            height: 1.4,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (topoAcao != null) topoAcao!,
              ],
            ),
          ),
          Expanded(
            child: rolar
                ? SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 16, 24, 12),
                    child: child,
                  )
                : Padding(
                    padding: const EdgeInsets.fromLTRB(24, 16, 24, 12),
                    child: child,
                  ),
          ),
          if (acoes.isNotEmpty)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (var i = 0; i < acoes.length; i++) ...[
                      if (i > 0) const SizedBox(height: 10),
                      acoes[i],
                    ],
                  ],
                ),
              ),
            ),
          if (rodape != null) rodape!,
        ],
      ),
    ),
  );
}

class Botao extends StatelessWidget {
  final String texto;
  final VoidCallback? onPressed;
  final IconData? icone;
  final bool voltar, contorno, ocupado;
  const Botao(
    this.texto, {
    super.key,
    this.onPressed,
    this.icone,
    this.voltar = false,
    this.contorno = false,
    this.ocupado = false,
  });
  @override
  Widget build(BuildContext context) {
    final conteudo = Row(
      children: [
        if (icone != null) Icon(icone, size: 20),
        Expanded(
          child: ocupado
              ? const Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : Text(
                  texto,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontFamily: 'DejaVuSans',
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0,
                  ),
                ),
        ),
        if (icone != null) const SizedBox(width: 20),
      ],
    );
    if (contorno) {
      return OutlinedButton(
        onPressed: ocupado ? null : onPressed,
        child: conteudo,
      );
    }
    return ElevatedButton(
      onPressed: ocupado ? null : onPressed,
      style: voltar
          ? ElevatedButton.styleFrom(
              backgroundColor: azulUnibus,
              foregroundColor: Colors.white,
            )
          : null,
      child: conteudo,
    );
  }
}

class Cartao extends StatelessWidget {
  final Widget child;
  final Color? cor, borda;
  final double padding;
  const Cartao({
    super.key,
    required this.child,
    this.cor,
    this.borda,
    this.padding = 14,
  });
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: EdgeInsets.all(padding),
    decoration: BoxDecoration(
      color: cor ?? Colors.white,
      border: Border.all(color: borda ?? bordaUnicap, width: 1.2),
      borderRadius: BorderRadius.circular(16),
    ),
    child: child,
  );
}

class Etiqueta extends StatelessWidget {
  final String texto;
  final Color cor, fundo;
  final IconData? icone;
  const Etiqueta(
    this.texto, {
    super.key,
    this.cor = azulUnibus,
    this.fundo = const Color(0xFFE9EFF8),
    this.icone,
  });
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: fundo,
      borderRadius: BorderRadius.circular(7),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icone != null) ...[
          Icon(icone, size: 12, color: cor),
          const SizedBox(width: 4),
        ],
        Flexible(
          child: Text(
            texto,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 10,
              color: cor,
            ),
          ),
        ),
      ],
    ),
  );
}

class FotoOnibus extends StatelessWidget {
  final Dados viagem;
  final double altura;
  const FotoOnibus(this.viagem, {super.key, this.altura = 138});
  @override
  Widget build(BuildContext context) {
    final url = ApiService.tratarUrlImagem(viagem['foto']?.toString());
    Widget fallback() => Image.asset(
      'assets/onibus_referencia.png',
      height: altura,
      fit: BoxFit.contain,
    );
    return url.isEmpty
        ? fallback()
        : Image.network(
            url,
            height: altura,
            fit: BoxFit.contain,
            errorBuilder: (_, e, s) => fallback(),
          );
  }
}

class GradeDados extends StatelessWidget {
  final Map<String, String> campos;
  final bool suave;
  const GradeDados(this.campos, {super.key, this.suave = false});
  @override
  Widget build(BuildContext context) => Cartao(
    cor: suave ? const Color(0xFFF7F8FA) : null,
    child: LayoutBuilder(
      builder: (context, c) => Wrap(
        spacing: 14,
        runSpacing: 12,
        children: campos.entries
            .map(
              (e) => SizedBox(
                width: (c.maxWidth - 14) / 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      e.key,
                      style: const TextStyle(color: cinzaUnicap, fontSize: 10),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      e.value,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        height: 1.25,
                      ),
                    ),
                  ],
                ),
              ),
            )
            .toList(),
      ),
    ),
  );
}

class Seletor extends StatelessWidget {
  final List<String> itens;
  final int selecionado;
  final ValueChanged<int> onChanged;
  const Seletor({
    super.key,
    required this.itens,
    required this.selecionado,
    required this.onChanged,
  });
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(3),
    decoration: BoxDecoration(
      color: const Color(0xFFEEF1F5),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Row(
      children: List.generate(
        itens.length,
        (i) => Expanded(
          child: Semantics(
            selected: i == selecionado,
            button: true,
            child: InkWell(
              onTap: () => onChanged(i),
              borderRadius: BorderRadius.circular(8),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  vertical: 10,
                  horizontal: 4,
                ),
                decoration: BoxDecoration(
                  color: i == selecionado ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  itens[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: i == selecionado ? azulUnibus : cinzaUnicap,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class BarraAbas extends StatelessWidget {
  final int indice;
  final ValueChanged<int> onChanged;
  const BarraAbas({super.key, required this.indice, required this.onChanged});
  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      border: Border(top: BorderSide(color: bordaUnicap)),
    ),
    child: SafeArea(
      top: false,
      child: Row(
        children: List.generate(
          2,
          (i) => Expanded(
            child: InkWell(
              onTap: () => onChanged(i),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      i == 0 ? Icons.directions_bus_outlined : Icons.history,
                      size: 23,
                      color: indice == i ? azulUnibus : const Color(0xFF98A2B3),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      i == 0 ? 'Viagens' : 'Histórico',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: indice == i
                            ? azulUnibus
                            : const Color(0xFF98A2B3),
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

class Ocupacao extends StatelessWidget {
  final Dados viagem;
  final bool grande;
  const Ocupacao(this.viagem, {super.key, this.grande = false});
  @override
  Widget build(BuildContext context) {
    final ocupados = (viagem['ocupados'] as num? ?? 0).toInt(),
        cap = (viagem['capacidade'] as num? ?? 1).toInt();
    final lotado = ocupados >= cap;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (grande) ...[
          const Text(
            'Quantidade de check-in',
            style: TextStyle(color: cinzaUnicap, fontSize: 12),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Text(
                '${viagem['presentes'] ?? 0}',
                style: const TextStyle(
                  fontSize: 34,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                '/$cap',
                style: const TextStyle(
                  fontSize: 23,
                  color: cinzaUnicap,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              Etiqueta(
                '${viagem['vagas_disponiveis']} vagas',
                fundo: const Color(0xFFFFE8DB),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: (ocupados / cap).clamp(0, 1),
            minHeight: 6,
            color: lotado ? vermelhoUnicap : azulUnibus,
            backgroundColor: const Color(0xFFE6EAF0),
          ),
        ),
        const SizedBox(height: 8),
        if (!grande)
          Row(
            children: [
              Expanded(
                child: Text(
                  '$ocupados/$cap ocupados',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: lotado ? vermelhoUnicap : azulUnibus,
                  ),
                ),
              ),
              Etiqueta(
                lotado
                    ? 'ÔNIBUS LOTADO'
                    : '${viagem['vagas_disponiveis']} vagas livres',
                cor: lotado ? vermelhoUnicap : azulUnibus,
                fundo: lotado
                    ? const Color(0xFFFDEDEB)
                    : const Color(0xFFFFE8DB),
              ),
            ],
          ),
      ],
    );
  }
}

class Numeros extends StatelessWidget {
  final Map<String, dynamic> valores;
  const Numeros(this.valores, {super.key});
  @override
  Widget build(BuildContext context) => Cartao(
    cor: const Color(0xFFF7F8FA),
    child: Row(
      children: valores.entries
          .map(
            (e) => Expanded(
              child: Column(
                children: [
                  Text(
                    '${e.value}',
                    style: const TextStyle(
                      fontSize: 23,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    e.key,
                    style: const TextStyle(fontSize: 11, color: cinzaUnicap),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    ),
  );
}

class LinhaPessoa extends StatelessWidget {
  final Dados pessoa;
  final String subtitulo;
  final Widget? trailing;
  final VoidCallback? onTap;
  const LinhaPessoa(
    this.pessoa, {
    super.key,
    required this.subtitulo,
    this.trailing,
    this.onTap,
  });
  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: bordaUnicap)),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 21,
            backgroundColor: const Color(0xFFE7EDF6),
            child: Text(
              iniciais('${pessoa['nome']}'),
              style: const TextStyle(
                color: azulUnibus,
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${pessoa['nome']}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    decoration: pessoa['cancelado'] == true
                        ? TextDecoration.lineThrough
                        : null,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitulo,
                  style: const TextStyle(
                    fontSize: 10,
                    color: cinzaUnicap,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    ),
  );
}

class TituloSecao extends StatelessWidget {
  final String texto;
  const TituloSecao(this.texto, {super.key});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 16, bottom: 10),
    child: Text(
      texto,
      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
    ),
  );
}
