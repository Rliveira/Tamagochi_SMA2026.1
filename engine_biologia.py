import time
from PyQt6.QtCore import QThread, pyqtSignal

class MotorBiologico(QThread):
    # ==========================================
    # SINAIS (Comunicação com a Interface)
    # ==========================================
    # Envia os números exatos para a UI caso você queira exibir barras de status depois
    status_atualizado = pyqtSignal(dict) 
    
    # Envia o comando para a UI trocar de pasta de sprites: (estagio_vida, emocao)
    mudar_animacao = pyqtSignal(str, str) 

    def __init__(self):
        super().__init__()
        self.blackboard = {
            "fome": 20,
            "energia": 90,
            "tedio": 30,
            "saude": 100,
            "maturidade": 0,
            "vivo": True
        }

    def run(self):
        """
        Loop assíncrono que roda em segundo plano.
        Substitui o nosso antigo "time.sleep(10)" problemático do Colab.
        """
        ciclos_segundos = 0
        
        while self.blackboard["vivo"]:
            time.sleep(1) # O relógio bate a cada segundo silenciosamente
            ciclos_segundos += 1
            
            # O metabolismo real e pesado acontece a cada 10 segundos
            if ciclos_segundos >= 10:
                self.blackboard["fome"] = min(100, self.blackboard["fome"] + 3)
                self.blackboard["energia"] = max(0, self.blackboard["energia"] - 2)
                self.blackboard["tedio"] = min(100, self.blackboard["tedio"] + 4)
                self.blackboard["maturidade"] += 1
                
                # Penalidades médicas
                if self.blackboard["fome"] >= 85 or self.blackboard["energia"] <= 15:
                    self.blackboard["saude"] = max(0, self.blackboard["saude"] - 8)
                
                if self.blackboard["saude"] <= 0:
                    self.blackboard["vivo"] = False
                    
                # Checa se o corpo precisa mudar a animação por instinto
                self._avaliar_estado_fisico()
                ciclos_segundos = 0
                
            # Dispara o sinal do status atualizado
            self.status_atualizado.emit(self.blackboard)

    def _avaliar_estado_fisico(self):
        """
        Atua como uma Behavior Tree simplificada e reativa.
        Avalia o Blackboard e decide qual é o sprite correto agora.
        """
        idade = self.blackboard["maturidade"]
        
        # 1. Regra de Evolução de Idade
        if idade < 20:
            estagio = "1_togepi"
        elif idade < 50:
            estagio = "2_togetic"
        else:
            estagio = "3_togekiss"

        # 2. Regra de Humor (Prioridade de Necessidades)
        emocao = "movement" # Estado padrão (andando/respirando)
        
        if self.blackboard["saude"] <= 0:
            emocao = "hurt" # Representa nocaute/morte
        elif self.blackboard["energia"] <= 15:
            emocao = "asleep" # Caiu no sono
        elif self.blackboard["saude"] <= 30 or self.blackboard["fome"] >= 80:
            emocao = "hurt" # Sentindo dor ou muita fome
        elif self.blackboard["tedio"] >= 70:
            emocao = "idle_attack" # Agitado/Irritado por falta de atenção
            
        # Avisa a interface para trocar a pasta de imagens!
        self.mudar_animacao.emit(estagio, emocao)

    def interagir_com_mouse(self, tipo_interacao):
        """
        Método instantâneo chamado quando você clica fisicamente no pet na tela.
        Gera uma reação emocional sem atrasos de IA.
        """
        if not self.blackboard["vivo"]:
            return
            
        idade = self.blackboard["maturidade"]
        estagio = "1_togepi" if idade < 20 else ("2_togetic" if idade < 50 else "3_togekiss")
        
        if tipo_interacao == "carinho_rapido":
            self.blackboard["tedio"] = max(0, self.blackboard["tedio"] - 20)
            self.mudar_animacao.emit(estagio, "special_attack") # Animação de felicidade