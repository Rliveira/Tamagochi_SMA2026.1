import sys
import os
import random
from PyQt6.QtWidgets import (QApplication, QLabel, QWidget, QVBoxLayout, 
                             QProgressBar, QLineEdit, QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QAction
from dotenv import load_dotenv

from engine_biologia import MotorBiologico
from agente_llm import CerebroTamagotchi

load_dotenv()

class ThreadPensamento(QThread):
    resposta_concluida = pyqtSignal(str)

    def __init__(self, cerebro, mensagem, estado_emocional):
        super().__init__()
        self.cerebro = cerebro
        self.mensagem = mensagem
        self.estado_emocional = estado_emocional

    def run(self):
        # Chama a API do Gemini no fundo
        resposta = self.cerebro.pensar_e_responder(self.mensagem, self.estado_emocional)
        self.resposta_concluida.emit(resposta)


class TamagotchiDesktop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.posicao_mouse_antiga = None

        # ==========================================
        # 1. LAYOUT PRINCIPAL
        # ==========================================
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(2)

        # ==========================================
        # 2. BALÃO DE PENSAMENTO / FALA
        # ==========================================
        self.balao_fala = QLabel("", self)
        self.balao_fala.setWordWrap(True)
        self.balao_fala.setFixedWidth(120)
        self.balao_fala.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.balao_fala.setStyleSheet("""
            background-color: white; 
            border: 2px solid #333; 
            border-radius: 10px; 
            padding: 5px; 
            font-family: Arial; 
            font-size: 10px; 
            color: black;
        """)
        self.balao_fala.hide() # Escondido por padrão
        self.layout_principal.addWidget(self.balao_fala, alignment=Qt.AlignmentFlag.AlignCenter)

        # ==========================================
        # 3. O SPRITE DO POKÉMON
        # ==========================================
        self.label_imagem = QLabel(self)
        self.label_imagem.setScaledContents(True)
        self.label_imagem.setFixedSize(50, 50) # Tamanho reduzido
        self.layout_principal.addWidget(self.label_imagem, alignment=Qt.AlignmentFlag.AlignCenter)

        # ==========================================
        # 4. HUD: BARRAS DE METABOLISMO
        # ==========================================
        self.barra_fome = self.criar_barra_progresso("#FF5722")  # Vermelho
        self.barra_energia = self.criar_barra_progresso("#2196F3") # Azul
        self.barra_tedio = self.criar_barra_progresso("#FFC107")   # Amarelo
        self.barra_saude = self.criar_barra_progresso("#4CAF50")   # Verde

        # ==========================================
        # 5. CAIXA DE CHAT (Entrada do Usuário)
        # ==========================================
        self.input_chat = QLineEdit(self)
        self.input_chat.setPlaceholderText("Fale com ele...")
        self.input_chat.setStyleSheet("background-color: white; color: black; border-radius: 5px; font-size: 10px;")
        self.input_chat.setFixedWidth(100)
        self.input_chat.hide()
        self.input_chat.returnPressed.connect(self.enviar_mensagem_ia)
        self.layout_principal.addWidget(self.input_chat, alignment=Qt.AlignmentFlag.AlignCenter)

        # ==========================================
        # 6. CONFIGURAÇÃO DE ANIMAÇÃO E MOTORES
        # ==========================================
        self.frames = []
        self.frame_atual_index = 0
        self.animacao_atual = ""
        self.estado_emocional_atual = "movement"

        self.timer_animacao = QTimer(self)
        self.timer_animacao.timeout.connect(self.atualizar_frame)
        self.timer_animacao.start(150)

        # Inicia a Biologia
        self.motor = MotorBiologico()
        self.motor.mudar_animacao.connect(self.carregar_animacao)
        self.motor.status_atualizado.connect(self.atualizar_hud)
        self.motor.start()

        # Inicia o Cérebro (IA) passando a referência do Blackboard
        chave_api = os.getenv("GEMINI_API_KEY")
        if not chave_api:
            print("⚠️ AVISO: GEMINI_API_KEY não encontrada no .env!")
            
        self.cerebro_llm = CerebroTamagotchi(chave_api, self.motor.blackboard)
        self.thread_pensamento = None

    def criar_barra_progresso(self, cor_hex):
        """Cria barras finas e minimalistas para o layout."""
        barra = QProgressBar(self)
        barra.setFixedSize(50, 4) # Altura de apenas 4 pixels
        barra.setTextVisible(False)
        barra.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid #ccc; border-radius: 2px; background-color: transparent; }}
            QProgressBar::chunk {{ background-color: {cor_hex}; border-radius: 2px; }}
        """)
        self.layout_principal.addWidget(barra, alignment=Qt.AlignmentFlag.AlignCenter)
        return barra

    # ==========================================
    # LÓGICA DE INTERFACE E EVENTOS
    # ==========================================
    def atualizar_hud(self, blackboard):
        """Atualiza as barras com base no Motor Biológico e avalia pensamentos instintivos."""
        self.barra_fome.setValue(100 - blackboard["fome"]) # Invertido para secar conforme sente fome
        self.barra_energia.setValue(blackboard["energia"])
        self.barra_tedio.setValue(100 - blackboard["tedio"]) # Invertido para secar conforme o tédio sobe
        self.barra_saude.setValue(blackboard["saude"])

        # Sorteio offline para balões de pensamento autônomos (15% de chance a cada tick de metabolismo)
        if not self.balao_fala.isVisible() and random.random() < 0.15:
            self.gerar_pensamento_autonomo(blackboard)

    def gerar_pensamento_autonomo(self, blackboard):
        """Gera falas instintivas baseadas nas métricas reais, sem gastar API."""
        pensamento = ""
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

        self.exibir_balao(pensamento, tempo_ms=4000)

    def exibir_balao(self, texto, tempo_ms=5000):
        """Exibe o balão e cria um timer para escondê-lo depois."""
        self.balao_fala.setText(texto)
        self.balao_fala.show()
        QTimer.singleShot(tempo_ms, self.balao_fala.hide)

    def enviar_mensagem_ia(self):
        """Captura o texto digitado e aciona o Gemini em segundo plano."""
        mensagem = self.input_chat.text()
        if not mensagem.strip():
            return

        self.input_chat.clear()
        self.input_chat.hide()
        self.exibir_balao("Pensando...", tempo_ms=20000) # Mantém aberto até a IA responder

        # Dispara a Thread da LLM
        self.thread_pensamento = ThreadPensamento(self.cerebro_llm, mensagem, self.estado_emocional_atual)
        self.thread_pensamento.resposta_concluida.connect(self.receber_resposta_ia)
        self.thread_pensamento.start()

    def receber_resposta_ia(self, resposta):
        """Callback acionado quando o Gemini termina de formular a frase."""
        self.exibir_balao(resposta, tempo_ms=7000) # Exibe a resposta final por 7 segundos

    # ==========================================
    # ANIMAÇÃO DE SPRITES
    # ==========================================
    def carregar_animacao(self, estagio_vida, emocao):
        caminho_pasta = os.path.join("sprites_organizados", estagio_vida, emocao)
        self.estado_emocional_atual = emocao
        
        if self.animacao_atual == caminho_pasta:
            return
        
        self.animacao_atual = caminho_pasta
        self.frames.clear()
        
        if os.path.exists(caminho_pasta):
            arquivos = sorted([f for f in os.listdir(caminho_pasta) if f.endswith('.png')])
            for arquivo in arquivos:
                self.frames.append(QPixmap(os.path.join(caminho_pasta, arquivo)))
            self.frame_atual_index = 0

    def atualizar_frame(self):
        if self.frames:
            self.label_imagem.setPixmap(self.frames[self.frame_atual_index])
            self.frame_atual_index = (self.frame_atual_index + 1) % len(self.frames)

    # ==========================================
    # CONTROLES DO MOUSE (Mover, Carinho e Menu)
    # ==========================================
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
        """Botão direito agora abre um menu com opções."""
        menu = QMenu(self)
        
        acao_conversar = QAction("💬 Conversar", self)
        acao_conversar.triggered.connect(lambda: (self.input_chat.show(), self.input_chat.setFocus()))
        menu.addAction(acao_conversar)

        acao_fechar = QAction("❌ Fechar Tamagotchi", self)
        acao_fechar.triggered.connect(self.fechar_aplicacao)
        menu.addAction(acao_fechar)
        
        menu.exec(event.globalPos())

    def fechar_aplicacao(self):
        self.motor.blackboard["vivo"] = False
        self.motor.wait()
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    pet = TamagotchiDesktop()
    pet.show()
    sys.exit(app.exec())