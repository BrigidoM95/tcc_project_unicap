(() => {
  const instituicao = document.getElementById('id_instituicao');
  const curso = document.getElementById('id_curso');
  const dados = document.getElementById('cursos-disponiveis');
  const aviso = document.getElementById('curso-aviso');
  if (!instituicao || !curso || !dados || !aviso) return;

  const cursos = JSON.parse(dados.textContent);
  function atualizarCursos() {
    const selecionado = curso.value;
    const opcoes = cursos.filter(item => String(item.instituicao_id) === instituicao.value);
    const texto = !instituicao.value ? 'Selecione primeiro a instituição'
      : opcoes.length ? 'Selecione o curso' : 'Nenhum curso ativo nesta instituição';
    curso.replaceChildren(new Option(texto, ''));
    for (const item of opcoes) {
      curso.add(new Option(item.nome, String(item.id)));
    }
    if (opcoes.some(item => String(item.id) === selecionado)) curso.value = selecionado;
    curso.disabled = !instituicao.value || opcoes.length === 0;
    aviso.hidden = !instituicao.value || opcoes.length > 0;
  }

  instituicao.addEventListener('change', atualizarCursos);
  atualizarCursos();
})();
