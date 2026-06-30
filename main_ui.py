import os
import random
import re
import sys

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl, QSize
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
    QHBoxLayout, QMessageBox
)
from PyQt6.QtMultimedia import QSoundEffect  
from dotenv import load_dotenv

from agente_llm import CerebroTamagotchi
from engine_biologia import MotorBiologico

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

        # ==========================================
        # BALÃO DE FALA 
        # ==========================================
        self.balao_fala = QLabel("", self)
        self.balao_fala.setWordWrap(True)
        self.balao_fala.setMinimumWidth(80)   
        self.balao_fala.setMaximumWidth(220) 
        self.balao_fala.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.balao_fala.setStyleSheet(
            """
            QLabel {
                background-color: white;
                border: 2px solid #333;
                border-radius: 12px;
                padding: 8px;
                font-family: Arial;
                font-size: 11px;
                color: black;
            }
            """
        )
        self.balao_fala.hide()
        self.layout_principal.addWidget(self.balao_fala, alignment=Qt.AlignmentFlag.AlignCenter)

        # Timer dedicado para esconder o balão
        self.timer_balao = QTimer(self)
        self.timer_balao.setSingleShot(True)
        self.timer_balao.timeout.connect(self._esconder_balao)
        
        # Timer para o ciclo de sono profundo
        self.timer_sono = QTimer(self)
        self.timer_sono.timeout.connect(self._processar_sono)

        # Janela de animação do sprite
        self.label_imagem = QLabel(self)
        self.label_imagem.setScaledContents(True)
        self.label_imagem.setFixedSize(60, 60)
        self.layout_principal.addWidget(self.label_imagem, alignment=Qt.AlignmentFlag.AlignCenter)

        # HUD / Barras
        tooltip_texts = ["fome", "energia", "tedio", "fase"]
        self.barra_fome = self.criar_barra_progresso("#FF5722", "🍖", tooltip_texts[0])
        self.barra_energia = self.criar_barra_progresso("#2196F3", "⚡", tooltip_texts[1])
        self.barra_tedio = self.criar_barra_progresso("#FFC107", "🎮", tooltip_texts[2])
        self.barra_fase = self.criar_barra_progresso("#9C27B0", "🌟", tooltip_texts[3])

        # Chat Input
        self.input_chat = QLineEdit(self)
        self.input_chat.setPlaceholderText("Fale com ele...")
        self.input_chat.setStyleSheet("background-color: white; color: black; border-radius: 5px; font-size: 10px;")
        self.input_chat.setFixedWidth(100)
        self.input_chat.hide()
        self.input_chat.returnPressed.connect(self.enviar_mensagem_ia)
        self.layout_principal.addWidget(self.input_chat, alignment=Qt.AlignmentFlag.AlignCenter)

        # Estados e Controle
        self.frames = []
        self.frame_atual_index = 0
        self.animacao_atual = ""
        self.estado_emocional_atual = "movement"
        self.estado_biologico_atual = ("0_egg", "movement")
        self.efeito_visual_tool_id = 0
        self.efeito_visual_ativo = False
        
        self.timer_retorno_animacao = QTimer(self)
        self.timer_retorno_animacao.setSingleShot(True)
        self.timer_retorno_animacao.timeout.connect(self._restaurar_animacao_biologica)

        # Áudio
        self.som_cry = QSoundEffect(self)
        self.diretorio_sons = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sounds_efects", "sounds_of_cry"
        )
        self.atualizar_audio_estagio("0_egg") 

        self.timer_animacao = QTimer(self)
        self.timer_animacao.timeout.connect(self.atualizar_frame)
        self.timer_animacao.start(300)

        # Integração com o Motor Biológico Estendido
        self.motor = MotorBiologico()
        self.motor.mudar_animacao.connect(self.carregar_animacao_motor)
        self.motor.status_atualizado.connect(self.atualizar_hud)
        

        # MUDANÇA: Inicializa o pet como OVO e NÃO inicia o motor ainda!
        self.motor.blackboard["maturidade"] = 0 
        self.motor.blackboard["nome_dono"] = "???"
        self.motor.blackboard["nome_pet"] = "Ovo"
        self.carregar_animacao_motor("0_egg", "movement")
        
        # Inicia a sequência de introdução após 1.5 segundos
        QTimer.singleShot(1500, self.iniciar_introducao)

        chave_api = os.getenv("GEMINI_API_KEY")
        if not chave_api:
            print("⚠️ AVISO: GEMINI_API_KEY não encontrada no .env!")

        self.cerebro_llm = CerebroTamagotchi(chave_api, self.motor.blackboard)
        self.thread_pensamento = None
        
    # ==========================================
    # FLUXO DE INTRODUÇÃO (NASCIMENTO)
    # ==========================================
    def iniciar_introducao(self):
        self.exibir_balao("Um ovo digital misterioso apareceu na sua tela...", tempo_ms=4500)
        # Chama a próxima etapa após 4.5 segundos
        QTimer.singleShot(4500, self.passo_1_nome_dono)

    def passo_1_nome_dono(self):
        nome_dono, ok = QInputDialog.getText(self, "Novo Amigo", "Qual é o seu nome?")
        if ok and nome_dono.strip():
            self.motor.blackboard["nome_dono"] = nome_dono.strip()
        else:
            self.motor.blackboard["nome_dono"] = "Dono"
            
        self.passo_2_caracteristica()

    def passo_2_caracteristica(self):
        traco, ok = QInputDialog.getText(self, "Aura", "Qual característica você mais admira num amigo?")
        if ok and traco.strip():
            self.motor.blackboard["traco_admirado"] = traco.strip()
        else:
            self.motor.blackboard["traco_admirado"] = "lealdade"

        self.exibir_balao("*O ovo absorve sua aura e começa a incubação...*", tempo_ms=4000)
        
        # A vida biológica começa aqui, COM O OVO EM MATURIDADE 0!
        self.motor.start()

    def passo_3_chocar(self):
        """Esta função agora só será chamada AUTOMATICAMENTE pela biologia quando o ovo estiver pronto!"""
        self.animacao_atual = "" 
        
        # carregando som do ovo rachando
        diretorio_efects_pai = os.path.dirname(self.diretorio_sons)
        caminho_crack = os.path.join(diretorio_efects_pai, "egg_cracking.wav")

        if os.path.exists(caminho_crack):
            self.som_cry.setSource(QUrl.fromLocalFile(caminho_crack))
            self.som_cry.setVolume(0.6) # Volume ligeiramente mais alto para destacar os estalos
            self.som_cry.play()
        else:
            print(f"⚠️ AVISO: Som de rachadura não encontrado: {caminho_crack}")
        
        # Força a execução da animação de quebra do ovo 'born' por 3 segundos
        self.carregar_animacao_visual("0_egg", "born", duracao_ms=3000)
        
        # Espera os 3 segundos da animação de quebra acabar para nascer e batizar
        QTimer.singleShot(3000, self.passo_4_batismo)

    def passo_4_batismo(self):
        # Carrega e toca o Cry oficial dele imediatamente
        self.atualizar_audio_estagio("1_togepi")
        self.tocar_som()

        #  Abre a caixinha para o usuário digitar o nome
        nome_pet, ok = QInputDialog.getText(self, "Nascimento!", "O ovo chocou! Como você vai chamá-lo?")
        if ok and nome_pet.strip():
            self.motor.blackboard["nome_pet"] = nome_pet.strip()
        else:
            self.motor.blackboard["nome_pet"] = "Bebê Togepi"

        nome = self.motor.blackboard["nome_pet"]
        self.exibir_balao(f"Toge toge! (Oi, eu sou o {nome}!)", tempo_ms=5000)
        
        # Atualiza a árvore para liberar o estado biológico do Togepi bebê andando
        self.carregar_animacao_motor("1_togepi", "movement")

    def passo_evolucao(self, estagio_velho, estagio_novo):
        """Executa a animação de evolução por 6 segundos com som e trava com MessageBox."""
        # 1. Informa o jogador no balão de fala
        nome_atual = self.motor.blackboard.get("nome_pet", "Pet")
        self.exibir_balao(f"O que está acontecendo com {nome_atual}?! ✨", tempo_ms=6000)
        
        # 2. Carrega e toca o som de evolução (evolution.wav)
        diretorio_efects_pai = os.path.dirname(self.diretorio_sons)
        caminho_evolution_som = os.path.join(diretorio_efects_pai, "evolution.wav")
        
        if os.path.exists(caminho_evolution_som):
            self.som_cry.stop()
            self.som_cry.setSource(QUrl.fromLocalFile(caminho_evolution_som))
            self.som_cry.setVolume(0.6)
            self.som_cry.play()
        
        # 3. Força a execução dos sprites da pasta 'evolution' do estágio antigo por 6 segundos
        self.carregar_animacao_visual(estagio_velho, "evolution", duracao_ms=6000)
        
        # 4. Agenda o travamento da tela para quando a animação de 6 segundos terminar
        QTimer.singleShot(6000, lambda: self.finalizar_evolucao(estagio_novo))

    def finalizar_evolucao(self, estagio_novo):
        """Gera o som clássico do pokémon novo e joga o pop-up de bloqueio na tela."""
        # Toca o grito (Cry) do novo estágio alcançado
        self.atualizar_audio_estagio(estagio_novo)
        self.tocar_som()
        
        # Altera o balão de fala para comemorar
        nome_atual = self.motor.blackboard.get("nome_pet", "Pet")
        traducao_fase = {"2_togetic": "Togetic", "3_togekiss": "Togekiss"}
        nome_especie = traducao_fase.get(estagio_novo, "Pokémon")
        
        self.exibir_balao(f"Parabéns! Seu {nome_atual} evoluiu para {nome_especie}! 🎉", tempo_ms=8000)
        
        # O BLOQUEADOR: Abre o pop-up que paralisa o app até o usuário clicar em OK
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Evolução!")
        msg_box.setText(f"✨ {nome_atual} evoluiu com sucesso para {nome_especie}! ✨")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # O script fica travado EXATAMENTE nesta linha. Nada se move visualmente abaixo dela.
        msg_box.exec()
        
        # 5. Após o usuário clicar em OK, restaura o fluxo normal rodando o movimento da nova fase
        self.efeito_visual_ativo = False
        self.carregar_animacao_motor(estagio_novo, "movement")

    def _resolver_diretorio_sprites(self):
        diretorio_base = os.path.dirname(os.path.abspath(__file__))
        candidatos = [
            os.path.join(diretorio_base, "sprites_organizados"),
            os.path.join(diretorio_base, "extrator_sprites", "sprites_organizados"),
        ]
        for candidato in candidatos:
            if os.path.exists(candidato):
                return candidato
        return candidatos[0]

    def criar_barra_progresso(self, cor_hex, rotulo_texto, tooltip_texto):
        layout_linha = QHBoxLayout()
        layout_linha.setContentsMargins(0, 0, 0, 0)
        layout_linha.setSpacing(4)
        layout_linha.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_status = QLabel(rotulo_texto, self)
        label_status.setStyleSheet("""
            color: white; font-family: Arial; font-size: 11px; font-weight: bold;
            background-color: rgba(0, 0, 0, 120); border-radius: 2px;
            padding-left: 2px; padding-right: 2px;
        """)
        label_status.setFixedWidth(12) 
        label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_status.setToolTip(f"Status: {tooltip_texto}")

        barra = QProgressBar(self)
        barra.setFixedSize(70, 7)
        barra.setTextVisible(False)
        barra.setStyleSheet(
            f"""
            QProgressBar {{ border: 1px solid #333; border-radius: 3px; background-color: rgba(0, 0, 0, 50); }}
            QProgressBar::chunk {{ background-color: {cor_hex}; border-radius: 2px; }}
            """
        )

        layout_linha.addWidget(label_status)
        layout_linha.addWidget(barra)
        self.layout_principal.addLayout(layout_linha)
        return barra

    def atualizar_hud(self, blackboard):
        self.barra_fome.setValue(100 - blackboard.get("fome", 0))
        self.barra_energia.setValue(blackboard.get("energia", 0))
        self.barra_tedio.setValue(100 - blackboard.get("tedio", 0))
        self._atualizar_barra_fase(blackboard.get("maturidade", 0))
        self._verificar_efeito_visual_tool(blackboard)
        
        # Se a IA acabou de ligar o foco, muda a animação na hora
        if blackboard.get("em_foco") and self.estado_emocional_atual != "study":
            self.carregar_animacao_motor(self.estado_biologico_atual[0], "study")

        # Só tenta processar pensamentos autônomos se NÃO for mais ovo
        if blackboard.get("nome_pet") != "Ovo":
            
            # Só pensa sozinho se não estiver dormindo E não estiver focado
            if not self.balao_fala.isVisible() and not self.timer_sono.isActive() and not blackboard.get("em_foco"):
                if random.random() < 0.15:
                    self.gerar_pensamento_autonomo(blackboard)

            # Pensamentos mais frequentes por conta do metabolismo rápido do Togepi bebê
            if not self.balao_fala.isVisible() and random.random() < 0.20:
                self.gerar_pensamento_autonomo(blackboard)
                
            # Evita pensar enquanto dorme adicionando a verificação do timer_sono
            if not self.balao_fala.isVisible() and not self.timer_sono.isActive() and random.random() < 0.15:
                self.gerar_pensamento_autonomo(blackboard)

    def _atualizar_barra_fase(self, maturidade):
        if maturidade < 20:
            fase_atual, inicio, fim = 1, 0, 20
        elif maturidade < 50:
            fase_atual, inicio, fim = 2, 20, 50
        else:
            fase_atual, inicio, fim = 3, 50, 50

        progresso = 100 if fase_atual == 3 else int(((maturidade - inicio) / (fim - inicio)) * 100)
        self.barra_fase.setValue(max(0, min(100, progresso)))

    def gerar_pensamento_autonomo(self, blackboard):

        # Evita gerar pensamentos enquanto o ovo ainda não chocou
        if self.estado_biologico_atual[0] == "0_egg":
            return
        
        if blackboard.get("fome", 0) > 75:
            pensamento = "Toge... ronnc... (fome)"
        elif blackboard.get("energia", 100) < 25:
            pensamento = "*bocejo* ...zzZ"
        elif blackboard.get("tedio", 0) > 75:
            pensamento = "Toge toge! (brinca comigo!)"
        elif blackboard.get("saude", 100) < 50:
            pensamento = "Toge... *cof cof*"
        else:
            # Verifica a emoção atual ditada pela Behavior Tree / Motor antes de cantarolar
            emocao = self.estado_emocional_atual
            
            if emocao in ["hurt", "sad", "angry"]:
                pensamento = "*Virado de costas, emburrado...*"
            elif emocao == "bored":
                pensamento = "*Suspiro profundo...*"
            elif emocao in ["sleep", "asleep"]:
                pensamento = "Zzz..."
            else:
                pensamento = "*Cantarolando feliz*"

        self.exibir_balao(pensamento, tempo_ms=4000)


    # ==========================================
    # LÓGICA DE BALÃO PERFEITA
    # ==========================================
    def exibir_balao(self, texto, tempo_ms=5000):
        self.balao_fala.setText(texto)
        self.balao_fala.show()
        
        # O PULO DO GATO: Obriga o Qt a aplicar o WordWrap antes de medir
        QApplication.processEvents()
        
        # Pega a dica de tamanho perfeito que o Qt calculou para caber o texto com padding
        tamanho_ideal = self.balao_fala.sizeHint()
        
        # Trava o balão neste tamanho para evitar distorções no layout do pet
        self.balao_fala.setFixedSize(tamanho_ideal + QSize(4, 4))
        
        self.adjustSize() # A janela acompanha
        
        self.timer_balao.stop() # Reinicia timer se já houver um rodando
        self.timer_balao.start(tempo_ms)

    def _esconder_balao(self):
        self.balao_fala.hide()
        # Libera o FixedSize para que o balão não ocupe espaço invisível
        self.balao_fala.setMinimumSize(0, 0)
        self.balao_fala.setMaximumSize(16777215, 16777215)
        self.adjustSize() # Encolhe a janela de volta

    def enviar_mensagem_ia(self):
        mensagem = self.input_chat.text()
        if not mensagem.strip():
            return

        self.input_chat.clear()
        self.input_chat.hide()
        self.adjustSize() # Reajusta a UI ao esconder a barra

        self.exibir_balao("Pensando...", tempo_ms=20000)

        self.thread_pensamento = ThreadPensamento(self.cerebro_llm, mensagem, self.estado_emocional_atual)
        self.thread_pensamento.resposta_concluida.connect(self.receber_resposta_ia)
        self.thread_pensamento.start()

    def receber_resposta_ia(self, resposta):
        self.exibir_balao(resposta, tempo_ms=7000)

    def _chave_ordenacao_frame(self, nome_arquivo):
        correspondencia = re.search(r"(\d+)", nome_arquivo)
        return int(correspondencia.group(1)) if correspondencia else nome_arquivo

    # ==========================================
    # SISTEMA DE SPRITES COM FALLBACK SEGURO
    # ==========================================
    def _carregar_animacao(self, estagio_vida, emocao):
        # 1. O TRADUTOR DEFINITIVO
        mapa_animacoes = {
            "0_egg": {
                "movement": "movement", 
                "born": "born",
                "stoped": "stoped",
            },
            "1_togepi": {
                "movement": "movement",
                "sleep": "asleep", 
                "eat": "eating",
                "play": "playing",
                "sad": "sad",
                "Tired": "tired",
                "happy": "happy",
                "evolution": "evolution",
                "hungry": "hungry",    
                "dead": "dead"
            },
            "2_togetic": {
                "movement": "movement",
                "sleep": "sleeping",     
                "eat": "eating",
                "play": "playing",
                "sad": "sad",
                "hurt": "sad",           
                "happy": "happy",
                "bored": "bored",
                "study": "study",
                "tired": "tired",
                "hungry": "hungry",
                "evolution": "evolution",
                "dead": "dead"
            },
            "3_togekiss": {
                "movement": "movement",
                "sleep": "sleeping",        
                "eat": "eating",
                "play": "playing",
                "sad": "sad",
                "hurt": "sad",
                "happy": "happy",
                "bored": "bored",
                "study": "study",
                "tired": "tired",
                "hungry": "hungry",
                "dead": "dead"
            }
        }

        # 2. Faz a tradução inicial
        mapa_fase = mapa_animacoes.get(estagio_vida, {})
        emocao_traduzida = mapa_fase.get(emocao, emocao)

        # 3. Monta o caminho
        caminho_base = os.path.join(self.base_sprites_dir, estagio_vida)
        caminho_pasta = os.path.join(caminho_base, emocao_traduzida)

        # 4. FALLBACK DE SEGURANÇA
        if not os.path.exists(caminho_pasta):
            fallback_movement = mapa_fase.get("movement", "movement")
            caminho_fallback = os.path.join(caminho_base, fallback_movement)
            
            if os.path.exists(caminho_fallback):
                caminho_pasta = caminho_fallback
                self.estado_emocional_atual = "movement"
            else:
                print(f"❌ ERRO CRÍTICO: A pasta '{caminho_fallback}' não existe!")
                return 
        else:
            self.estado_emocional_atual = emocao

        # 5. O MERGULHADOR DE SUBPASTAS COM SORTEIO ALEATÓRIO
        # Verifica o que tem dentro da pasta traduzida
        itens_na_pasta = os.listdir(caminho_pasta)
        tem_pngs_diretos = any(f.lower().endswith('.png') for f in itens_na_pasta)
        
        # Se não houver fotos soltas na pasta mãe, significa que existem variantes (subpastas)
        if not tem_pngs_diretos:
            subpastas = [
                d for d in itens_na_pasta 
                if os.path.isdir(os.path.join(caminho_pasta, d))
            ]
            
            if subpastas:
                # Sorteia aleatoriamente uma das subpastas variantes disponíveis
                subpasta_sorteada = random.choice(subpastas)
                caminho_pasta = os.path.join(caminho_pasta, subpasta_sorteada)
            else:
                print(f"❌ ERRO: Nenhuma imagem ou subpasta encontrada em '{caminho_pasta}'!")
                return


        # 6. CARREGAMENTO DOS FRAMES DA VARIANTE SORTEADA

        # Se escolheu EXATAMENTE a mesma subpasta que já está rodando, 
        # não limpa os frames para não dar um "soluço" no meio do passo
        if self.animacao_atual == caminho_pasta and len(self.frames) > 0:
            return

        self.animacao_atual = caminho_pasta
        self.frames.clear()

        arquivos = sorted(
            [f for f in os.listdir(caminho_pasta) if f.lower().endswith('.png')],
            key=self._chave_ordenacao_frame,
        )
        
        for arquivo in arquivos:
            pixmap = QPixmap(os.path.join(caminho_pasta, arquivo))
            if not pixmap.isNull():
                self.frames.append(pixmap)
                
        self.frame_atual_index = 0

    def carregar_animacao_motor(self, estagio_vida, emocao):
        if self.motor.blackboard.get("em_foco"):
            emocao = "study"
            
        # Gatilho de choque do ovo (Fase 0 -> Fase 1)
        if self.estado_biologico_atual[0] == "0_egg" and estagio_vida == "1_togepi":
            self.estado_biologico_atual = (estagio_vida, emocao)
            self.animacao_atual = ""
            self.passo_3_chocar()
            return
        
        if estagio_vida == "1_togepi" and self.motor.blackboard["nome_pet"] == "Ovo":
            return

        # Evita re-executar se forem os mesmos
        if self.estado_biologico_atual[0] != "0_egg" and self.estado_biologico_atual[0] != estagio_vida:
            estagio_anterior = self.estado_biologico_atual[0]
            
            # Se o estágio anterior possuir a pasta de evolução (Togepi ou Togetic)
            if estagio_anterior in ["1_togepi", "2_togetic"]:
                self.estado_biologico_atual = (estagio_vida, emocao)
                self.animacao_atual = ""
                
                # Dispara a sequência travada de evolução
                self.passo_evolucao(estagio_anterior, estagio_vida)
                return

        if emocao in ["hungry", "tired", "bored", "sad", "hurt"]:
            self.atualizar_audio_estagio(estagio_vida)
            self.tocar_som()

        # Evita re-executar se forem os mesmos
        if self.estado_biologico_atual == (estagio_vida, emocao) and len(self.frames) > 0:
            return
            
        self.estado_biologico_atual = (estagio_vida, emocao)
        
        if self.efeito_visual_ativo and not self.motor.blackboard.get("em_foco"):
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
        # O ovo não tem som de grito, então ignoramos o carregamento
        if estagio_vida == "0_egg":
            return
            
        nome_arquivo = f"{estagio_vida.split('_')[1]}_cry.wav"
        caminho_som = os.path.join(self.diretorio_sons, nome_arquivo)
        
        if os.path.exists(caminho_som):
            self.som_cry.setSource(QUrl.fromLocalFile(caminho_som))
            self.som_cry.setVolume(0.5)
        else:
            print(f"⚠️ AVISO: Arquivo de áudio não encontrado em: {caminho_som}")

    def tocar_som(self):
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
            
    def _interromper_sono(self):
        """Acorda o pet forçadamente se ele for interrompido durante o sono."""
        if self.timer_sono.isActive():
            self.timer_sono.stop()
            self.motor.mudar_animacao.emit(self.estado_biologico_atual[0], "movement")

    def _processar_sono(self):
        """Função chamada pelo timer a cada 2 segundos até a energia bater 100."""
        energia_atual = self.motor.blackboard.get("energia", 0)
        if energia_atual >= 100:
            self.timer_sono.stop()
            self.exibir_balao("Acordei! 100% recarregado! ✨", tempo_ms=4000)
            self.motor.mudar_animacao.emit(self.estado_biologico_atual[0], "movement")
        else:
            # Chama o motor silenciosamente para continuar a subir a energia
            self.motor.descansar()

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
        # Recalcula a janela ao mostrar o campo de texto
        acao_conversar.triggered.connect(lambda: (self.input_chat.show(), self.input_chat.setFocus(), self.adjustSize()))
        menu.addAction(acao_conversar)

        acao_fechar = QAction("❌ Fechar janela", self)
        acao_fechar.triggered.connect(self.fechar_aplicacao)
        menu.addAction(acao_fechar)

        menu.exec(event.globalPos())

    def definir_nomes(self):
        nome_dono_atual = self.motor.blackboard.get("nome_dono", "dono")
        nome_pet_atual = self.motor.blackboard.get("nome_pet", "Togepi")

        nome_dono, ok_dono = QInputDialog.getText(
            self, "Definir nome do dono", "Digite o nome do dono:", text=nome_dono_atual
        )
        if not ok_dono: return

        nome_pet, ok_pet = QInputDialog.getText(
            self, "Definir nome do pet", "Digite o nome do pet:", text=nome_pet_atual
        )
        if not ok_pet: return

        self.motor.blackboard["nome_dono"] = nome_dono.strip() or nome_dono_atual
        self.motor.blackboard["nome_pet"] = nome_pet.strip() or nome_pet_atual
        self.exibir_balao(f"Agora eu sou {self.motor.blackboard['nome_pet']} e meu dono é {self.motor.blackboard['nome_dono']}.", tempo_ms=5000)

    def alimentar_pet(self):
        estagio = self.estado_biologico_atual[0]
        if estagio == "0_egg":
            return
            
        # Executa a lógica biológica e pega o texto de resposta
        mensagem_retorno = self.motor.alimentar()
        self.exibir_balao(mensagem_retorno, tempo_ms=3500)
        
        # 🍎 TRAVA VISUAL: Força os sprites de 'eat' (eating) por 2.5 segundos
        self.carregar_animacao_visual(estagio, "eat", duracao_ms=2500)

    def brincar_com_pet(self):
        estagio = self.estado_biologico_atual[0]
        if estagio == "0_egg":
            return
            
        mensagem_retorno = self.motor.brincar()
        self.exibir_balao(mensagem_retorno, tempo_ms=3500)
        
        # 🎾 TRAVA VISUAL: Força os sprites de 'play' (playing) por 3 segundos
        self.carregar_animacao_visual(estagio, "play", duracao_ms=3000)

    def descansar_pet(self):
        estagio = self.estado_biologico_atual[0]
        if estagio == "0_egg":
            return

        if self.timer_sono.isActive():
            self.exibir_balao("Já estou a dormir... zzz", tempo_ms=3000)
            return

        mensagem_retorno = self.motor.descansar()
        self.exibir_balao(mensagem_retorno, tempo_ms=3500)
        
        # 💤 TRAVA VISUAL DE SONO: Força a animação 'sleep' (asleep/sleeping)
        # Como o sono é contínuo e controlado pelo loop do timer_sono, 
        # nós definimos uma duração longa inicial, e o próprio _processar_sono cuida do loop.
        self.carregar_animacao_visual(estagio, "sleep", duracao_ms=2000)
        
        if self.motor.blackboard.get("energia", 0) < 100:
            self.timer_sono.start(2000)

    def fechar_aplicacao(self):
        self.motor.blackboard["vivo"] = False
        self.motor.wait()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = TamagotchiDesktop()
    pet.show()
    sys.exit(app.exec())