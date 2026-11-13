"""Verificações da entrega de fotografias no Django, inclusive em produção."""
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from embarques.tests import Cenario


class FotoPublicaOnibusTests(Cenario, TestCase):
    def test_foto_cadastrada_tem_url_publica_e_resposta_de_imagem(self):
        with TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            self.onibus.foto.save('fotografia_teste.jpg', ContentFile(b'foto-de-teste'), save=True)
            self.onibus.refresh_from_db()
            self.assertEqual(self.onibus.foto_url, reverse('onibus_foto', args=[self.onibus.pk]))
            resposta = self.client.get(self.onibus.foto_url)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta['Content-Type'], 'image/jpeg')
            self.assertEqual(b''.join(resposta.streaming_content), b'foto-de-teste')
            api = self.cliente(self.associado).get(f'/api/viagens/{self.viagem.pk}/')
            self.assertEqual(api.data['foto'], self.onibus.foto_url)

    def test_arquivo_ausente_nao_divulga_url_e_retorna_404(self):
        self.onibus.foto = 'onibus/fotografia-que-nao-existe.webp'
        self.onibus.save(update_fields=['foto'])
        self.assertEqual(self.onibus.foto_url, '')
        resposta = self.client.get(reverse('onibus_foto', args=[self.onibus.pk]))
        self.assertEqual(resposta.status_code, 404)
