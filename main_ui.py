import os
import random
import re
import sys

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMenu,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from dotenv import load_dotenv

from agente_llm import CerebroTamagotchi
from engine_biologia import MotorBiologico
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl  
from PyQt6.QtMultimedia import QSoundEffect  
load_dotenv()


class ThreadPensamento(QThread):
    resposta_concluida = pyqtSignal(str)

    def __init__(self, cerebro, mensagem, estado_emocional):
        super().__init__()
        self.cerebro = cerebro
        self.mensagem = mensagem
        self.estado_emocional = estado_emocional

    def run(self):
        resposta = self.cerebro.pensar_e_responder(self.mensagem, self.estado_emocional)
        self.resposta_concluida.emit(resposta)


class TamagotchiDesktop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.posicao_mouse_antiga = None
        self.base_sprites_dir = self._resolver_diretorio_sprites()

        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(2)

        self.balao_fala = QLabel("", self)
        self.balao_fala.setWordWrap(True)
        self.balao_fala.setFixedWidth(120)
        self.balao_fala.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.balao_fala.setStyleSheet(
            """
            background-color: white;
            border: 2px solid #333;
            border-radius: 10px;
            padding: 5px;
            font-family: Arial;
            font-size: 10px;
            color: black;
            """
        )
        self.balao_fala.hide()
        self.layout_principal.addWidget(self.balao_fala, alignment=Qt.AlignmentFlag.AlignCenter)

        # Janela de animação do sprite do Togepi
        self.label_imagem = QLabel(self)
        self.label_imagem.setScaledContents(True)
        self.label_imagem.setFixedSize(60,60)
        self.layout_principal.addWidget(self.label_imagem, alignment=Qt.AlignmentFlag.AlignCenter)

        tooltip_texts = [
            "fome", "energia", "tedio", "fase"
        ]

        self.barra_fome = self.criar_barra_progresso("#FF5722", "🍖", tooltip_texts[0])   # F = Fome[cite: 4]
        self.barra_energia = self.criar_barra_progresso("#2196F3", "⚡", tooltip_texts[1]) # E = Energia[cite: 4]
        self.barra_tedio = self.criar_barra_progresso("#FFC107", "🎮", tooltip_texts[2])   # T = Tédio[cite: 4]
        self.barra_fase = self.criar_barra_progresso("#9C27B0", "🌟", tooltip_texts[3])    # V = Vida/Evolução[cite: 4]

        self.barra_fase.setToolTip(tooltip_texts[3])
        self.barra_fome.setToolTip(tooltip_texts[0])
        self.barra_energia.setToolTip(tooltip_texts[1])
        self.barra_tedio.setToolTip(tooltip_texts[2])

        self.input_chat = QLineEdit(self)
        self.input_chat.setPlaceholderText("Fale com ele...")
        self.input_chat.setStyleSheet("background-color: white; color: black; border-radius: 5px; font-size: 10px;")
        self.input_chat.setFixedWidth(100)
        self.input_chat.hide()
        self.input_chat.returnPressed.connect(self.enviar_mensagem_ia)
        self.layout_principal.addWidget(self.input_chat, alignment=Qt.AlignmentFlag.AlignCenter)

        self.frames = []
        self.frame_atual_index = 0
        self.animacao_atual = ""
        self.estado_emocional_atual = "movement"
        self.estado_biologico_atual = ("1_togepi", "movement")
        self.efeito_visual_tool_id = 0
        self.efeito_visual_ativo = False
        self.timer_retorno_animacao = QTimer(self)
        self.timer_retorno_animacao.setSingleShot(True)
        self.timer_retorno_animacao.timeout.connect(self._restaurar_animacao_biologica)

        self.som_cry = QSoundEffect(self)
        self.diretorio_sons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds_of_cry")
        
        # Função interna rápida para carregar o arquivo correto baseado no estágio
        self.atualizar_audio_estagio("1_togepi")

        # Toca o som de nascimento/abertura imediatamente
        self.tocar_som()

        self.timer_animacao = QTimer(self)
        self.timer_animacao.timeout.connect(self.atualizar_frame)
        self.timer_animacao.start(150)

        self.motor = MotorBiologico()
        self.motor.mudar_animacao.connect(self.carregar_animacao_motor)
        self.motor.status_atualizado.connect(self.atualizar_hud)
        self.motor.start()

        self.carregar_animacao_motor("1_togepi", "movement")

        chave_api = os.getenv("GEMINI_API_KEY")
        if not chave_api:
            print("⚠️ AVISO: GEMINI_API_KEY não encontrada no .env!")

        self.cerebro_llm = CerebroTamagotchi(chave_api, self.motor.blackboard)
        self.thread_pensamento = None

    def _resolver_diretorio_sprites(self):
        diretorio_base = os.path.dirname(os.path.abspath(__file__))
        candidatos = [
            os.path.join(diretorio_base, "sprites_organizados"),
            os.path.join(diretorio_base, "extrator_sprites", "sprites_organizados"),
            os.path.join(diretorio_base, "extrator_sprites", "sprites_processados_dersorganizados"),
        ]

        for candidato in candidatos:
            if os.path.exists(candidato):
                return candidato

        print("⚠️ AVISO: Nenhuma pasta de sprites encontrada. Verifique sprites_organizados.")
        return candidatos[0]

    def criar_barra_progresso(self, cor_hex, rotulo_texto, tooltip_texto):
        """Cria uma barra mais larga acompanhada de uma letra identificadora."""
        from PyQt6.QtWidgets import QHBoxLayout

        # Criamos um container horizontal específico para este status
        layout_linha = QHBoxLayout()
        layout_linha.setContentsMargins(0, 0, 0, 0)
        layout_linha.setSpacing(4)
        layout_linha.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Criamos o indicador de texto (Letra ou Emoji)
        label_status = QLabel(rotulo_texto, self)
        label_status.setStyleSheet("""
            color: white; 
            font-family: Arial; 
            font-size: 11px; 
            font-weight: bold;
            background-color: rgba(0, 0, 0, 120);
            border-radius: 2px;
            padding-left: 2px;
            padding-right: 2px;
        """)
        label_status.setFixedWidth(12) # Garante alinhamento vertical perfeito
        label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_status.setToolTip(f"Status: {tooltip_texto}")

        # Criamos a barra de progresso ajustada
        barra = QProgressBar(self)
        barra.setFixedSize(70, 7)
        barra.setTextVisible(False)
        barra.setStyleSheet(
            f"""
            QProgressBar {{ border: 1px solid #333; border-radius: 3px; background-color: rgba(0, 0, 0, 50); }}
            QProgressBar::chunk {{ background-color: {cor_hex}; border-radius: 2px; }}
            """
        )

        # Adicionamos os dois elementos lado a lado na linha
        layout_linha.addWidget(label_status)
        layout_linha.addWidget(barra)

        # Inserimos essa linha no layout principal vertical do Tamagotchi
        self.layout_principal.addLayout(layout_linha)
        return barra

    def atualizar_hud(self, blackboard):
        self.barra_fome.setValue(100 - blackboard["fome"])
        self.barra_energia.setValue(blackboard["energia"])
        self.barra_tedio.setValue(100 - blackboard["tedio"])
        self._atualizar_barra_fase(blackboard["maturidade"])
        self._verificar_efeito_visual_tool(blackboard)

        if not self.balao_fala.isVisible() and random.random() < 0.15:
            self.gerar_pensamento_autonomo(blackboard)

    def _atualizar_barra_fase(self, maturidade):
        if maturidade < 20:
            fase_atual = 1
            inicio = 0
            fim = 20
        elif maturidade < 50:
            fase_atual = 2
            inicio = 20
            fim = 50
        else:
            fase_atual = 3
            inicio = 50
            fim = 50

        if fase_atual == 3:
            progresso = 100
        else:
            progresso = int(((maturidade - inicio) / (fim - inicio)) * 100)
            progresso = max(0, min(100, progresso))

        self.barra_fase.setValue(progresso)

    def gerar_pensamento_autonomo(self, blackboard):
        if blackboard["fome"] > 75:
            pensamento = "Toge... ronnc... (fome)"
        elif blackboard["energia"] < 25:
            pensamento = "*bocejo* ...zzZ"
        elif blackboard["tedio"] > 75:
            pensamento = "Toge toge! (brinca comigo!)"
        elif blackboard["saude"] < 50:
            pensamento = "Toge... *cof cof*"
        else:
            pensamento = "*Cantarolando feliz*"
            self.tocar_som()  # Toca o som de grito feliz ocasionalmente

        self.exibir_balao(pensamento, tempo_ms=4000)

    def exibir_balao(self, texto, tempo_ms=5000):
        self.balao_fala.setText(texto)
        self.balao_fala.show()
        QTimer.singleShot(tempo_ms, self.balao_fala.hide)

    def enviar_mensagem_ia(self):
        mensagem = self.input_chat.text()
        if not mensagem.strip():
            return

        self.input_chat.clear()
        self.input_chat.hide()
        self.exibir_balao("Pensando...", tempo_ms=20000)

        self.thread_pensamento = ThreadPensamento(self.cerebro_llm, mensagem, self.estado_emocional_atual)
        self.thread_pensamento.resposta_concluida.connect(self.receber_resposta_ia)
        self.thread_pensamento.start()

    def receber_resposta_ia(self, resposta):
        self.exibir_balao(resposta, tempo_ms=7000)

    def _chave_ordenacao_frame(self, nome_arquivo):
        correspondencia = re.search(r"(\d+)", nome_arquivo)
        return int(correspondencia.group(1)) if correspondencia else nome_arquivo

    def _carregar_animacao(self, estagio_vida, emocao):
        if emocao == "movement":
            caminho_pasta = os.path.join(self.base_sprites_dir, estagio_vida, "movement")
            if not os.path.exists(caminho_pasta):
                caminho_pasta = os.path.join(self.base_sprites_dir, estagio_vida, "idle_movement")
        else:
            caminho_pasta = os.path.join(self.base_sprites_dir, estagio_vida, emocao)

        self.estado_emocional_atual = emocao

        if self.animacao_atual == caminho_pasta:
            return

        self.animacao_atual = caminho_pasta
        self.frames.clear()

        if os.path.exists(caminho_pasta):
            arquivos = sorted(
                [f for f in os.listdir(caminho_pasta) if f.endswith('.png')],
                key=self._chave_ordenacao_frame,
            )
            for arquivo in arquivos:
                pixmap = QPixmap(os.path.join(caminho_pasta, arquivo))
                if not pixmap.isNull():
                    self.frames.append(pixmap)
            self.frame_atual_index = 0
        else:
            print(f"⚠️ AVISO: pasta de animação não encontrada: {caminho_pasta}")

        if not self.frames:
            print(f"⚠️ AVISO: nenhum frame carregado para {estagio_vida}/{emocao} em {caminho_pasta}")

    def carregar_animacao_motor(self, estagio_vida, emocao):
        # Se mudou de estágio (Evolução!), atualiza o áudio e toca
        if self.estado_biologico_atual[0] != estagio_vida:
            self.atualizar_audio_estagio(estagio_vida)
            self.tocar_som()
            
        self.estado_biologico_atual = (estagio_vida, emocao)
        if self.efeito_visual_ativo:
            return
        self._carregar_animacao(estagio_vida, emocao)

    def carregar_animacao_visual(self, estagio_vida, emocao, duracao_ms=1200):
        self.efeito_visual_ativo = True
        self._carregar_animacao(estagio_vida, emocao)
        self.timer_retorno_animacao.start(max(250, int(duracao_ms)))

    def _restaurar_animacao_biologica(self):
        self.efeito_visual_ativo = False
        estagio_vida, emocao = self.estado_biologico_atual
        self._carregar_animacao(estagio_vida, emocao)

    def atualizar_audio_estagio(self, estagio_vida):
        """Muda o arquivo de áudio carregado conforme o Pokémon evolui."""
        nome_arquivo = f"{estagio_vida.split('_')[1]}_cry.wav" # Transforma '1_togepi' em 'togepi_cry.wav'
        caminho_som = os.path.join(self.diretorio_sons, nome_arquivo)
        
        if os.path.exists(caminho_som):
            self.som_cry.setSource(QUrl.fromLocalFile(caminho_som))
            self.som_cry.setVolume(0.5) # Volume em 50%
        else:
            print(f"⚠️ AVISO: Arquivo de áudio não encontrado: {caminho_som}")

    def tocar_som(self):
        """Gatilhador para reproduzir o grito se ele estiver carregado."""
        if self.som_cry.status() != QSoundEffect.Status.Error:
            self.som_cry.play()

    def _verificar_efeito_visual_tool(self, blackboard):
        evento_visual = blackboard.get("visual_tool_event")
        if not isinstance(evento_visual, dict):
            return

        evento_id = evento_visual.get("id")
        if evento_id is None or evento_id == self.efeito_visual_tool_id:
            return

        self.efeito_visual_tool_id = evento_id
        estagio = evento_visual.get("estagio", self.estado_biologico_atual[0])
        emocao = evento_visual.get("emocao", "movement")
        duracao_ms = evento_visual.get("duracao_ms", 1200)
        self.carregar_animacao_visual(estagio, emocao, duracao_ms)

    def atualizar_frame(self):
        if self.frames:
            self.label_imagem.setPixmap(self.frames[self.frame_atual_index])
            self.frame_atual_index = (self.frame_atual_index + 1) % len(self.frames)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.posicao_mouse_antiga = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.posicao_mouse_antiga is not None:
            delta = event.globalPosition().toPoint() - self.posicao_mouse_antiga
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.posicao_mouse_antiga = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.posicao_mouse_antiga = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.motor.interagir_com_mouse("carinho_rapido")

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        acao_definir_nomes = QAction("✏️ Definir nomes", self)
        acao_definir_nomes.triggered.connect(self.definir_nomes)
        menu.addAction(acao_definir_nomes)

        acao_alimentar = QAction("🍎 Alimentar", self)
        acao_alimentar.triggered.connect(self.alimentar_pet)
        menu.addAction(acao_alimentar)

        acao_brincar = QAction("🎾 Brincar", self)
        acao_brincar.triggered.connect(self.brincar_com_pet)
        menu.addAction(acao_brincar)

        acao_descansar = QAction("💤 Descansar", self)
        acao_descansar.triggered.connect(self.descansar_pet)
        menu.addAction(acao_descansar)

        acao_conversar = QAction("💬 Conversar", self)
        acao_conversar.triggered.connect(lambda: (self.input_chat.show(), self.input_chat.setFocus()))
        menu.addAction(acao_conversar)

        acao_fechar = QAction("❌ Fechar janela", self)
        acao_fechar.triggered.connect(self.fechar_aplicacao)
        menu.addAction(acao_fechar)

        menu.exec(event.globalPos())

    def definir_nomes(self):
        nome_dono_atual = self.motor.blackboard.get("nome_dono", "dono")
        nome_pet_atual = self.motor.blackboard.get("nome_pet", "Togepi")

        nome_dono, ok_dono = QInputDialog.getText(
            self,
            "Definir nome do dono",
            "Digite o nome do dono:",
            text=nome_dono_atual,
        )
        if not ok_dono:
            return

        nome_pet, ok_pet = QInputDialog.getText(
            self,
            "Definir nome do pet",
            "Digite o nome do pet:",
            text=nome_pet_atual,
        )
        if not ok_pet:
            return

        nome_dono = nome_dono.strip() or nome_dono_atual
        nome_pet = nome_pet.strip() or nome_pet_atual

        self.motor.blackboard["nome_dono"] = nome_dono
        self.motor.blackboard["nome_pet"] = nome_pet
        self.exibir_balao(f"Agora eu sou {nome_pet} e meu dono é {nome_dono}.", tempo_ms=5000)

    def alimentar_pet(self):
        mensagem = self.motor.alimentar()
        self.exibir_balao(mensagem, tempo_ms=3500)

    def brincar_com_pet(self):
        mensagem = self.motor.brincar()
        self.exibir_balao(mensagem, tempo_ms=3500)

    def descansar_pet(self):
        mensagem = self.motor.descansar()
        self.exibir_balao(mensagem, tempo_ms=3500)

    def fechar_aplicacao(self):
        self.motor.blackboard["vivo"] = False
        self.motor.wait()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = TamagotchiDesktop()
    pet.show()
    sys.exit(app.exec())