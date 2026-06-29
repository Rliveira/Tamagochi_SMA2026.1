import time
from PyQt6.QtCore import QThread, pyqtSignal

from behavior_tree import BehaviorContext, build_biological_behavior_tree

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
            "maturidade": 26,
            "vivo": True,
            "nome_dono": "dono",
            "nome_pet": "bebê"
        }
        self.arvore_comportamental = build_biological_behavior_tree()
        
    def _obter_multiplicadores(self):
        """Retorna (fome, energia, tedio) com base na maturidade."""
        idade = self.blackboard["maturidade"]
        
        if idade < 20:   # 1_togepi (Bebê)
            return {"fome": 6, "energia": -3, "tedio": 0} # Tédio 0 para simplificar
        elif idade < 50: # 2_togetic (Adolescente)
            return {"fome": 3, "energia": -2, "tedio": 4}
        else:            # 3_togekiss (Adulto)
            return {"fome": 1, "energia": -1, "tedio": 2}

    def run(self):
        """
        Loop assíncrono que roda em segundo plano.
        Substitui o nosso antigo "time.sleep(10)"
        """
        ciclos_segundos = 0
        
        while self.blackboard["vivo"]:
            time.sleep(1) # O relógio bate a cada segundo silenciosamente
            ciclos_segundos += 1
            
            # O metabolismo real e pesado acontece a cada 300 segundos (5 minutos)
            if ciclos_segundos >= 5:
                mult = self._obter_multiplicadores()
        
                self.blackboard["fome"] = min(100, self.blackboard["fome"] + mult["fome"])
                self.blackboard["energia"] = max(0, self.blackboard["energia"] + mult["energia"])
                self.blackboard["tedio"] = min(100, self.blackboard["tedio"] + mult["tedio"])
                self.blackboard["maturidade"] += 1
                
                # Penalidades médicas caso o pet esteja em estado crítico
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
        Avalia o Blackboard por uma Behavior Tree explícita e decide qual é o sprite correto agora.
        """
        contexto = BehaviorContext(blackboard=self.blackboard)
        decisao = self.arvore_comportamental.run(contexto)

        if decisao.estagio:
            self.mudar_animacao.emit(decisao.estagio, decisao.emocao)

    def _estagio_atual(self):
        idade = self.blackboard["maturidade"]
        if idade < 20:
            return "1_togepi"
        if idade < 50:
            return "2_togetic"
        return "3_togekiss"

    def alimentar(self) -> str:
        """Alimenta o pet sem depender da LLM."""
        if not self.blackboard["vivo"]:
            return "O pet não pode ser alimentado agora."

        self.blackboard["fome"] = max(0, self.blackboard["fome"] - 35)
        self.blackboard["saude"] = min(100, self.blackboard["saude"] + 4)

        estagio = self._estagio_atual()
        self.mudar_animacao.emit(estagio, "special_attack")
        return "Toge! *come feliz e fica mais confortável*"

    def brincar(self) -> str:
        """Brinca com o pet sem depender da LLM."""
        if not self.blackboard["vivo"]:
            return "O pet não pode brincar agora."

        self.blackboard["tedio"] = max(0, self.blackboard["tedio"] - 30)
        self.blackboard["saude"] = min(100, self.blackboard["saude"] + 2)

        estagio = self._estagio_atual()
        emocao = "special_attack" if estagio == "1_togepi" else "attack"
        self.mudar_animacao.emit(estagio, emocao)
        return "Toge toge! *brinca animado com o dono*"

    def descansar(self) -> str:
        """Permite que o pet descanse sem chamar a LLM."""
        if not self.blackboard["vivo"]:
            return "O pet não pode descansar agora."

        self.blackboard["energia"] = min(100, self.blackboard["energia"] + 25)
        estagio = self._estagio_atual()
        self.mudar_animacao.emit(estagio, "asleep")
        return "Toge... *descansa em paz por um instante*"

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