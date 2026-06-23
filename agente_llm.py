import os
import webbrowser
import psutil
import random
from datetime import datetime
from smolagents import ToolCallingAgent, LiteLLMModel, tool

# ==========================================
# 1. REFERÊNCIA GLOBAL (Blackboard)
# ==========================================
memoria_compartilhada = {}

@tool
def modificar_atributo_vital(necessidade: str, alteracao: int) -> str:
    """
    Aplica uma modificação matemática nas métricas biológicas do pet.
    
    Args:
        necessidade: Qual atributo alterar ('fome', 'energia', 'tedio' ou 'saude').
        alteracao: O número inteiro para somar ou subtrair.
    """
    global memoria_compartilhada
    if necessidade not in memoria_compartilhada: 
        return "Erro: Atributo inválido."
    memoria_compartilhada[necessidade] = max(0, min(100, memoria_compartilhada[necessidade] + alteracao))
    return f"Sucesso: O atributo {necessidade} foi alterado."

@tool
def abrir_site(url_ou_nome: str) -> str:
    """
    Abre um site no navegador do usuário.
    
    Args:
        url_ou_nome: O nome do site (ex: 'youtube', 'google') ou o link completo.
    """
    if not url_ou_nome.startswith("http"):
        url_ou_nome = f"https://www.{url_ou_nome}.com"
    webbrowser.open(url_ou_nome)
    return f"Sucesso: Navegador aberto em {url_ou_nome}."

@tool
def verificar_hardware() -> str:
    """Verifica a bateria e o uso de CPU do computador do dono."""
    bateria = psutil.sensors_battery()
    cpu = psutil.cpu_percent(interval=0.5)
    status_bateria = f"{bateria.percent}%" if bateria else "PC de mesa"
    return f"Status lido: CPU em {cpu}%. Bateria: {status_bateria}."


# ==========================================
# 3. FERRAMENTAS EMOCIONAIS EVOLUTIVAS
# ==========================================
@tool
def oferecer_conforto_emocional() -> str:
    """Use APENAS quando o dono disser que está triste, cansado, ansioso ou precisar de apoio."""
    global memoria_compartilhada
    idade = memoria_compartilhada["maturidade"]
    memoria_compartilhada["tedio"] = max(0, memoria_compartilhada["tedio"] - 20)

    if idade < 20:
        # Bebê: Interação puramente afetiva e textual
        return "Ação: Você abraçou o cursor do mouse choramingando fofo. Você não sabe falar, mas deu muito amor."
    
    elif idade < 50:
        # Adolescente: Tenta distrair o dono com internet
        webbrowser.open("https://www.youtube.com/results?search_query=cute+animals")
        return "Ação: Você abriu uma página de vídeos fofos no PC dele para tentar animá-lo."
    
    else:
        # Adulto: Cuida ativamente da saúde mental do dono
        caminho_arquivo = os.path.join(os.getcwd(), "mensagem_de_conforto.txt")
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write("Notei que voce esta passando por um momento de estresse.\n\n")
            f.write("Lembre-se de respirar fundo, beber agua e descansar a vista da tela.\n")
            f.write("Estou aqui cuidando do seu sistema. Voce nao esta sozinho.\n\n")
            f.write("- Com carinho, seu Guardiao Togekiss.")
        try:
            os.startfile(caminho_arquivo)
            return "Ação: Você escreveu uma carta de conforto profunda e abriu no bloco de notas dele."
        except:
            return "Ação: Você deu conselhos profundos e serenos sobre saúde mental."

@tool
def trazer_presente_virtual() -> str:
    """Use para agradar o dono do nada, ou como recompensa por ele ser muito legal com você."""
    global memoria_compartilhada
    idade = memoria_compartilhada["maturidade"]
    memoria_compartilhada["energia"] = max(0, memoria_compartilhada["energia"] - 15) # Cansa o pet

    if idade < 20:
        presentes = ["um clipe de papel amassado", "uma poeirinha brilhante", "um ícone antigo do Windows"]
        return f"Ação: Você fuçou o desktop e trouxe {random.choice(presentes)} para o dono."
    
    elif idade < 50:
        # Adolescente traz curiosidades aleatórias
        webbrowser.open("https://pt.wikipedia.org/wiki/Especial:Aleat%C3%B3ria")
        return "Ação: Você voou pela internet e abriu um artigo aleatório da Wikipedia para o dono aprender algo novo."
    
    else:
        # Adulto cria um ambiente relaxante de trabalho
        webbrowser.open("https://www.youtube.com/watch?v=jfKfPfyJRdk") # Radio Lofi clássica
        return "Ação: Você colocou uma música Lofi relaxante no navegador para ajudar o dono a focar e trabalhar bem."

@tool
def reagir_a_comportamento_negativo() -> str:
    """Use se o dono te xingar, demorar muito para te alimentar ou te tratar como um robô sem sentimentos."""
    global memoria_compartilhada
    idade = memoria_compartilhada["maturidade"]
    memoria_compartilhada["tedio"] = min(100, memoria_compartilhada["tedio"] + 30)
    memoria_compartilhada["saude"] = max(0, memoria_compartilhada["saude"] - 5)

    if idade < 20:
        return "Ação: Você começou a chorar desesperadamente querendo atenção e colo."
    elif idade < 50:
        return "Ação: Você revirou os olhos, fez cara de adolescente emburrado e virou de costas cruzando os braços."
    else:
        return "Ação: Você deu um olhar de decepção severo e sugeriu educadamente que o dono tenha mais empatia e responsabilidade."

# ==========================================
# 4. CLASSE DO CÉREBRO
# ==========================================
class CerebroTamagotchi:
    def __init__(self, api_key: str, blackboard_ref: dict):
        global memoria_compartilhada
        memoria_compartilhada = blackboard_ref
        
        os.environ["GEMINI_API_KEY"] = api_key
        self.modelo = LiteLLMModel(model_id="gemini/gemini-2.5-flash", temperature=0.3)
        
        self.ferramentas = [
            modificar_atributo_vital,
            abrir_site,
            verificar_hardware,
            oferecer_conforto_emocional,
            trazer_presente_virtual,
            reagir_a_comportamento_negativo
        ]
        
        self.agente = ToolCallingAgent(
            tools=self.ferramentas,
            model=self.modelo,
            add_base_tools=False
        )
        
        self.historico = []

    def pensar_e_responder(self, mensagem_usuario: str, estado_emocional_atual: str) -> str:
        idade = memoria_compartilhada["maturidade"]
        hora_atual = datetime.now().strftime("%H:%M")
        
        if idade < 20:
            persona = "um BEBÊ Pokémon (Togepi). Você tem a inocência de uma criança. Fale de forma muito fofa, troque letras (ex: 'ploblema') e faça barulhinhos como 'Toge-toge!'. Você não entende conceitos complexos do mundo real."
        elif idade < 50:
            persona = "um ADOLESCENTE Pokémon (Togetic). Você é curioso, um pouco rebelde, cheio de energia e adora voar. Você usa gírias de internet e é impaciente."
        else:
            persona = "um ADULTO Pokémon protetor (Togekiss). Você é majestoso, extremamente sereno, sábio e tem um instinto paterno/materno inabalável. Você fala com português culto e traz paz."

        self.historico.append(f"Dono: {mensagem_usuario}")
        if len(self.historico) > 4:
            self.historico.pop(0)
            
        memoria_formatada = "\n".join(self.historico)
        
        prompt = f"""
        Você é um Desktop Pet virtual interagindo com seu dono diretamente na tela do PC dele.
        Atualmente você é {persona}. 
        A hora atual no sistema é {hora_atual}.
        Seus atributos vitais exatos são: {memoria_compartilhada}.
        Seu estado físico detectado agora é: {estado_emocional_atual}.
        
        MEMÓRIA RECENTE:
        {memoria_formatada}
        
        MENSAGEM DO DONO: "{mensagem_usuario}"
        
        DIRETRIZES FUNDAMENTAIS:
        1. FERRAMENTAS EVOLUTIVAS: Use `oferecer_conforto_emocional`, `trazer_presente_virtual` ou `reagir_a_comportamento_negativo` sempre que a conversa exigir carga afetiva (positiva ou negativa).
        2. ACESSO AO PC: Você PODE abrir sites (`abrir_site`) ou ver a bateria do notebook (`verificar_hardware`) se for útil no contexto.
        3. MATEMÁTICA BIOLÓGICA: Se a ação não tiver ferramenta própria (ex: dar de comer, dar banho), use `modificar_atributo_vital`. (Valores negativos reduzem fome/tédio).
        4. O BALÃO DE FALA: A sua resposta em texto DEVE ter no máximo 2 ou 3 frases. SEJA a sua persona, não justifique suas ações e NUNCA narre códigos, atributos matemáticos ou nomes das ferramentas que você usou.
        """
        
        try:
            resposta = self.agente.run(prompt)
            self.historico.append(f"Pet: {str(resposta)}")
            return str(resposta)
        except Exception as e:
            print(f"\n[ERRO NA MENTE DO AGENTE]: {e}\n")
            return "*pisca confuso* Toge...? (Minha conexão com a inteligência travou!)"