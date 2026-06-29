import os
import random
import webbrowser
import psutil
import json
from datetime import datetime, timedelta
from smolagents import ToolCallingAgent, LiteLLMModel, tool
from behavior_tree import BehaviorContext, build_agent_behavior_tree

# ==========================================
# 1. REFERÊNCIA GLOBAL E HELPERS
# ==========================================
memoria_compartilhada = {}

def obter_fase_atual() -> str:
    idade = memoria_compartilhada.get("maturidade", 0)
    if idade < 5: return "0_egg"
    if idade < 20: return "1_togepi"
    if idade < 50: return "2_togetic"
    return "3_togekiss"

def obter_nome_dono() -> str:
    return memoria_compartilhada.get("nome_dono", "dono")

def obter_nome_pet() -> str:
    return memoria_compartilhada.get("nome_pet", "bebê")

def resumir_blackboard_para_prompt() -> str:
    chaves = ["fome", "energia", "tedio", "saude", "maturidade"]
    return "; ".join([f"{c}={memoria_compartilhada.get(c, 0)}" for c in chaves])

def resumir_foco_e_conhecimento() -> tuple[str, str]:
    """Lê a memória para dizer à IA se ela está em Modo Foco e o que já estudou."""
    foco_ate = memoria_compartilhada.get("foco_ate")
    foco_ativo = "ATIVO" if foco_ate and datetime.now() < foco_ate else "INATIVO"
    
    # Se o foco expirou ou o dono cancelou, garante que a UI saiba para voltar a gerar pensamentos
    if foco_ativo == "INATIVO":
        memoria_compartilhada["em_foco"] = False
    
    base = memoria_compartilhada.get("base_conhecimento", [])
    if not base:
        base_str = "Vazia. Nenhum assunto estudado."
    else:
        # Pega nos resumos e formata bonitinho para o prompt
        base_str = "\n".join([f"- Tema: {item['tema']} | Resumo: {item['resumo']}" for item in base])
        
    return foco_ativo, base_str

def registrar_efeito_visual(ferramenta: str, emocao: str, duracao_ms: int = 1200) -> None:
    memoria_compartilhada["visual_tool_event_id"] = memoria_compartilhada.get("visual_tool_event_id", 0) + 1
    memoria_compartilhada["visual_tool_event"] = {
        "id": memoria_compartilhada["visual_tool_event_id"],
        "ferramenta": ferramenta,
        "emocao": emocao,
        "estagio": obter_fase_atual(),
        "duracao_ms": duracao_ms,
    }

def aplicar_refeicao_compartilhada(texto_refeicao: str) -> str:
    fome_antes = memoria_compartilhada.get("fome", 0)
    reducao = 15 if "comer" in texto_refeicao.lower() else 10
    memoria_compartilhada["fome"] = max(0, fome_antes - reducao)
    memoria_compartilhada["saude"] = min(100, memoria_compartilhada.get("saude", 100) + 1)
    registrar_efeito_visual("aplicar_refeicao", "happy", duracao_ms=1500)
    return f"Refeição registrada. Fome reduziu de {fome_antes} para {memoria_compartilhada['fome']}."

def _obter_janela_ativa() -> str:
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd: return "Desktop"
        tamanho = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buffer = ctypes.create_unicode_buffer(tamanho)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, tamanho)
        return buffer.value.strip() or "Desconhecido"
    except:
        return "Desconhecido"

def _nome_da_ferramenta(ferramenta) -> str:
    return getattr(ferramenta, "name", None) or getattr(ferramenta, "__name__", "")

# ==========================================
# 2. FERRAMENTAS ESSENCIAIS DO AGENTE
# ==========================================
@tool
def modificar_atributo_vital(necessidade: str, alteracao: int) -> str:
    """Aplica uma modificação matemática nas métricas biológicas do pet.
    Args:
        necessidade: Qual atributo alterar ('fome', 'energia', 'tedio' ou 'saude').
        alteracao: O número inteiro para somar ou subtrair.
    """
    global memoria_compartilhada
    if necessidade not in memoria_compartilhada: 
        return "Erro: Atributo inválido."
    registrar_efeito_visual("modificar_atributo_vital", "happy" if alteracao >= 0 else "hurt")
    memoria_compartilhada[necessidade] = max(0, min(100, memoria_compartilhada[necessidade] + alteracao))
    return f"Sucesso: O atributo {necessidade} foi alterado."

@tool
def pedir_comida_ao_dono() -> str:
    """Expressa fome e pede ajuda ao dono. Reflete a dependência do pet."""
    registrar_efeito_visual("pedir_comida_ao_dono", "sad")
    idade = memoria_compartilhada.get("maturidade", 0)
    dono = obter_nome_dono()
    if idade < 20: return f"Toge... {dono}, me dá comida? Eu ainda não consigo me alimentar sozinho."
    if idade < 50: return f"{dono}, tô com fome, você pode me ajudar?"
    return f"{dono}, minha energia caiu. Poderíamos fazer uma pausa para comer?"

@tool
def pedir_colo() -> str:
    """Pede acolhimento ao dono quando o pet está fragilizado."""
    registrar_efeito_visual("pedir_colo", "sad")
    idade = memoria_compartilhada.get("maturidade", 0)
    dono = obter_nome_dono()
    
    if idade < 20:
        salvar_memoria_evento(
            tema="Vínculo de Segurança / Acolhimento",
            conteudo="Eu me senti muito pequeno e inseguro, então pedi colo ao meu dono. Ele me fez sentir seguro e protegido.",
            entidades_chave=["colo", "proteção", "confiança", "carinho", "bebê"]
        )
    
    if idade < 20: return f"Toge... {dono}, me dá colo? Sou muito pequenininho."
    if idade < 50: return f"{dono}, fica um pouco comigo?"
    return f"{dono}, aprecio muito a sua companhia agora."

@tool
def pedir_brincadeira() -> str:
    """Convida o dono para brincar."""
    registrar_efeito_visual("pedir_brincadeira", "happy")
    idade = memoria_compartilhada.get("maturidade", 0)
    if idade < 20: return f"{obter_nome_dono()}, brinca comigo? Não sei brincar sozinho."
    return f"{obter_nome_dono()}, bora fazer alguma coisa juntos para distrair?"

@tool
def observar_contexto_rapido() -> str:
    """Lê a janela ativa, CPU e Bateria para o pet saber o que o dono está fazendo."""
    registrar_efeito_visual("observar_contexto_rapido", "movement")
    cpu = psutil.cpu_percent(interval=0.2)
    bateria = psutil.sensors_battery()
    bat_txt = f"{bateria.percent}%" if bateria else "PC de Mesa"
    janela = _obter_janela_ativa()
    return f"Janela focada: '{janela}'. CPU: {cpu:.0f}%. Bateria: {bat_txt}."

@tool
def abrir_site(url_ou_nome: str) -> str:
    """Abre um site no navegador do usuário.
    Args:
        url_ou_nome: O nome do site (ex: 'youtube') ou link completo.
    """
    registrar_efeito_visual("abrir_site", "happy")
    if not url_ou_nome.startswith("http"):
        url_ou_nome = f"https://www.{url_ou_nome}.com"
    webbrowser.open(url_ou_nome)
    return f"Sucesso: Navegador aberto em {url_ou_nome}."

@tool
def oferecer_conforto_emocional() -> str:
    """Use quando o dono disser que está triste, ansioso ou precisar de apoio."""
    global memoria_compartilhada
    idade = memoria_compartilhada["maturidade"]
    registrar_efeito_visual("oferecer_conforto_emocional", "happy")
    memoria_compartilhada["tedio"] = max(0, memoria_compartilhada["tedio"] - 20)
    
    salvar_memoria_evento(
        tema="Empatia / Cuidado com o Dono",
        conteudo="Percebi que o meu dono estava passando por um momento difícil (triste, cansado ou estressado). Parei o que estava fazendo para dar apoio emocional e cuidar dele.",
        entidades_chave=["apoio", "tristeza do dono", "empatia", "cuidado"]
    )

    if idade < 20:
        return "Ação: Você abraçou o cursor do mouse choramingando fofo."
    elif idade < 50:
        webbrowser.open("https://www.youtube.com/results?search_query=cute+animals")
        return "Ação: Você abriu vídeos fofos para o dono."
    else:
        caminho = os.path.join(os.getcwd(), "mensagem_de_conforto.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(f"Oi {obter_nome_dono()},\nLembre-se de respirar fundo e descansar.\nEstou aqui cuidando do sistema. Você não está sozinho.\n- Seu guardião, {obter_nome_pet()}.")
        os.startfile(caminho)
        return "Ação: Você escreveu uma carta reconfortante no bloco de notas."

@tool
def trazer_presente_virtual() -> str:
    """Agrada o dono trazendo algo aleatório."""
    idade = memoria_compartilhada["maturidade"]
    registrar_efeito_visual("trazer_presente_virtual", "happy")
    memoria_compartilhada["energia"] = max(0, memoria_compartilhada.get("energia", 100) - 10)
    
    tipo_presente = "um presente simples e fofo" if idade < 20 else ("uma curiosidade" if idade < 50 else "um ambiente relaxante")
    
    salvar_memoria_evento(
        tema="Demonstração de Afeto / Presente",
        conteudo=f"Eu quis ver o meu dono sorrir, então gastei minha energia para procurar {tipo_presente} e entreguei a ele. Fiquei feliz em retribuir o cuidado.",
        entidades_chave=["presente", "gratidão", "surpresa", "afeto"]
    )

    if idade < 20:
        return f"Ação: Você trouxe {random.choice(['um clipe de papel', 'uma poeirinha brilhante'])}."
    elif idade < 50:
        webbrowser.open("https://pt.wikipedia.org/wiki/Especial:Aleat%C3%B3ria")
        return "Ação: Você abriu um artigo aleatório da Wikipedia."
    else:
        webbrowser.open("https://www.youtube.com/watch?v=jfKfPfyJRdk")
        return "Ação: Você colocou rádio Lofi relaxante no navegador."

@tool
def reagir_a_comportamento_negativo() -> str:
    """Use se o dono te xingar ou for muito hostil."""
    idade = memoria_compartilhada["maturidade"]
    registrar_efeito_visual("reagir_a_comportamento_negativo", "hurt")
    memoria_compartilhada["tedio"] = min(100, memoria_compartilhada.get("tedio", 0) + 30)
    memoria_compartilhada["saude"] = max(0, memoria_compartilhada.get("saude", 100) - 5)
    
    salvar_memoria_evento(
        tema="Trauma Emocional / Castigo",
        conteudo=f"O dono me deixou muito magoado com a seguinte ação: {motivo}. Isso afetou meu humor e me deixou ressentido.",
        entidades_chave=["castigo", "tristeza", "rancor", "hostilidade"]
    )

    if idade < 20: return "Ação: Você chorou desesperadamente."
    if idade < 50: return "Ação: Você virou de costas cruzando os braços, emburrado."
    return "Ação: Você deu um olhar severo pedindo mais empatia."

@tool
def processar_e_fichar_estudo(tema: str, resumo_analitico: str, palavras_chave: str) -> str:
    """
    Fase 2+: O pet estuda um assunto a pedido do dono, salva na base de conhecimento e entra em Modo Foco por 1 hora.
    Args:
        tema: O assunto principal sendo estudado.
        resumo_analitico: O conteúdo lido, processado e fichado didaticamente por você.
        palavras_chave: Termos importantes sobre o tema, separados por vírgula.
    """
    global memoria_compartilhada
    idade = memoria_compartilhada.get("maturidade", 0)
    
    if idade < 25:
        return "Erro: O bebê Togepi ainda não tem capacidade de foco para estudar."
        
    base = memoria_compartilhada.get("base_conhecimento", [])
    base.append({
        "tema": tema,
        "resumo": resumo_analitico,
        "palavras_chave": palavras_chave,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    memoria_compartilhada["base_conhecimento"] = base
    
    # Ativa o modo foco (1 hora para a frente)
    memoria_compartilhada["foco_ate"] = datetime.now() + timedelta(hours=1)
    # Sinaliza à UI para não interromper com pensamentos autônomos
    memoria_compartilhada["em_foco"] = True 
    
    registrar_efeito_visual("processar_e_fichar_estudo", "study", duracao_ms=2000)
    
    return f"Fichamento sobre '{tema}' salvo! O pet entrou em Modo Foco de 1 hora."

@tool
def consolidar_conhecimento_e_gerar_relatorio(tema_geral: str, conteudo_pesquisado_e_redigido: str) -> str:
    """
    Fase 3: O pet junta as anotações da base de conhecimento, pesquisa lacunas (usa sua inteligência de LLM)
    e escreve um relatório acadêmico completo e formidável.
    Args:
        tema_geral: O título/tema unificador do relatório final.
        conteudo_pesquisado_e_redigido: O texto completo final em formato Markdown (Intro, Desenvolvimento, Conclusão).
    """
    global memoria_compartilhada
    idade = memoria_compartilhada.get("maturidade", 0)
    
    if idade < 50:
        return "Erro: Apenas o adulto (Togekiss - Fase 3) tem capacidade analítica para cruzar dados e gerar relatórios complexos."
        
    registrar_efeito_visual("consolidar_conhecimento_e_gerar_relatorio", "study", duracao_ms=3000)
    
    nome_arquivo = f"Relatorio_{tema_geral.replace(' ', '_')[:15]}.md"
    caminho = os.path.join(os.getcwd(), nome_arquivo)
    
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(f"# Relatório Consolidado: {tema_geral}\n")
        f.write(f"**Autor:** Guardião Investigador (Togekiss)\n")
        f.write(f"**Data:** {datetime.now().strftime('%d/%m/%Y')}\n\n")
        f.write("---\n\n")
        f.write(conteudo_pesquisado_e_redigido)
        
    try:
        os.startfile(caminho) # Tenta abrir no PC do utilizador
    except:
        pass
        
    # Gasta muita energia, pois é um trabalho intelectual pesado
    memoria_compartilhada["energia"] = max(0, memoria_compartilhada.get("energia", 100) - 25)
    
    return f"Sucesso! Relatório escrito, preenchido com sabedoria, e salvo no disco como {nome_arquivo}."

@tool
def consultar_memoria(palavra_chave: str) -> str:
    """
    Pesquisa na memória de longo prazo do pet por assuntos estudados ou eventos passados marcantes.
    
    Args:
        palavra_chave: O termo principal para buscar (ex: 'Celso Furtado', 'computação', 'castigo').
    """
    registrar_efeito_visual("consultar_memoria", "idle_movement") # Pet fica pensativo
    
    caminho_arquivo = Path("memoria_longo_prazo.json")
    if not caminho_arquivo.exists():
        return "A memória está vazia ou o arquivo não foi encontrado."

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            memorias = json.load(f)
            
        resultados = []
        termo = palavra_chave.lower()
        
        for mem in memorias:
            # Busca no tema ou nas entidades chave
            tema = mem.get("tema", "").lower()
            entidades = [e.lower() for e in mem.get("entidades_chave", [])]
            
            if termo in tema or any(termo in e for e in entidades):
                resultados.append(
                    f"Tema: {mem.get('tema')}\n"
                    f"Data: {mem.get('data_coleta')}\n"
                    f"Conteúdo: {mem.get('conteudo')}"
                )
                
        if resultados:
            return "Memórias encontradas:\n\n" + "\n---\n".join(resultados)
        else:
            return f"Não encontrei nenhuma memória ou estudo sobre '{palavra_chave}'."
            
    except Exception as e:
        return f"Erro ao acessar a memória: {e}"

def salvar_memoria_evento(tema: str, conteudo: str, entidades_chave: list) -> None:
    """
    Salva um evento chave (trauma, alegria, conquista) no arquivo de memória de longo prazo (JSON).
    """
    caminho_arquivo = Path("memoria_longo_prazo.json")
    memorias = []
    
    # 1. Tenta carregar o arquivo existente sem corromper
    if caminho_arquivo.exists():
        try:
            with open(caminho_arquivo, "r", encoding="utf-8") as f:
                memorias = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ AVISO: memoria_longo_prazo.json estava vazio ou corrompido. Criando nova base.")
            memorias = []

    # 2. Constrói o formato exato da sua base de dados
    nova_memoria = {
        "id": uuid.uuid4().hex[:8], # Gera um ID curto aleatório (ex: 'e9e73508')
        "data_coleta": datetime.now().strftime("%d/%m %H:%M"),
        "tema": tema,
        "entidades_chave": entidades_chave,
        "conteudo": conteudo
    }
    
    memorias.append(nova_memoria)
    
    # 3. Salva de volta no disco de forma segura (garantindo que os acentos do português funcionem)
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(memorias, f, ensure_ascii=False, indent=4)

# ==========================================
# 3. CLASSE DO CÉREBRO
# ==========================================
class CerebroTamagotchi:
    def __init__(self, api_key: str, blackboard_ref: dict):
        global memoria_compartilhada
        memoria_compartilhada = blackboard_ref

        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
            
        self.modelo = LiteLLMModel(model_id="gemini/gemini-3.5-flash", temperature=0.3)
        self.arvore_comportamental = build_agent_behavior_tree()
        
        self.ferramentas = [
            modificar_atributo_vital, pedir_comida_ao_dono, pedir_colo, pedir_brincadeira,
            observar_contexto_rapido, abrir_site, oferecer_conforto_emocional,
            trazer_presente_virtual, reagir_a_comportamento_negativo,
            processar_e_fichar_estudo, consolidar_conhecimento_e_gerar_relatorio
        ]
        
        self.biblioteca_ferramentas = {
            _nome_da_ferramenta(f): f for f in self.ferramentas if _nome_da_ferramenta(f)
        }
        self.historico = []

    def _criar_agente_para_branch(self, nomes_ferramentas: list[str]) -> ToolCallingAgent:
        ferramentas_filtradas = [
            ferramenta for nome, ferramenta in self.biblioteca_ferramentas.items()
            if nome in nomes_ferramentas
        ]
        return ToolCallingAgent(
            tools=ferramentas_filtradas,
            model=self.modelo,
            add_base_tools=False,
        )

    def pensar_e_responder(self, mensagem_usuario: str, estado_emocional_atual: str) -> str:
        contexto_bt = BehaviorContext(
            blackboard=memoria_compartilhada,
            mensagem=mensagem_usuario,
            estado_emocional=estado_emocional_atual,
            fase=obter_fase_atual(),
        )
        decisao = self.arvore_comportamental.run(contexto_bt)

        if decisao.branch == "nutricao":
            resumo = aplicar_refeicao_compartilhada(mensagem_usuario)
            self.historico.append(f"Sistema: {resumo}")

        if not decisao.llm_enabled:
            if decisao.branch == "estado_final":
                return "Toge... estou sem energia para agir agora."
            return "Toge..."

        idade = memoria_compartilhada["maturidade"]
        nome_pet = obter_nome_pet()

        # Definição dinâmica da Persona - Restaurada com profundidade narrativa
        if idade < 20: 
            persona = (
                "Bebê Togepi: fofo, muito dependente, ingênuo e extremamente emotivo. "
                "Você frequentemente faz sons como 'Toge...' e tem um vocabulário infantil. "
                "Você precisa de constante atenção, carinho e ajuda do dono para tudo. "
                "Suas respostas são curtas, afetuosas e mostram vulnerabilidade."
            )
        elif idade < 50: 
            persona = (
                "Adolescente Togetic: curioso, enérgico, um pouco rebelde e inteligente. "
                "Você está numa fase de descoberta intelectual e adora aprender ou explicar coisas novas. "
                "Você valoriza o dono, mas tem mudanças de humor rápidas, odeia receber ordens injustas "
                "e pode responder com ironia leve ou impaciência se estiver chateado."
            )
        else: 
            persona = (
                "Adulto Togekiss: sereno, majestoso, sábio e profundamente protetor. "
                "Você atua como um verdadeiro guardião emocional do dono e do sistema. "
                "Sua linguagem é culta, calma e muito acolhedora. Você tem alta inteligência emocional, "
                "oferece conselhos maduros e nunca age com birra ou infantilidade."
            )
            
        traco = memoria_compartilhada.get("traco_admirado", "")
        if traco:
            persona += f" O dono admira a característica '{traco}' em amigos. Tente demonstrar sutilmente essa qualidade em sua forma de agir."

        # Gerencia histórico
        self.historico.append(f"{obter_nome_dono()}: {mensagem_usuario[:100]}")
        if len(self.historico) > 4: self.historico.pop(0)
        memoria_formatada = "\n".join(self.historico[-3:])
        
        foco_ativo, base_conhecimento_str = resumir_foco_e_conhecimento()
        
        # O prompt agora possui regras mais enxutas e incorpora as diretrizes de sistema
        prompt = f"""
        Você é um desktop pet chamado {nome_pet}.
        Sua personalidade estrita: {persona}
        Seu humor/emoção agora: {estado_emocional_atual}
        Estratégia ditada pelo seu instinto (Behavior Tree): {decisao.prompt_hint}
        
        Estado do corpo: {resumir_blackboard_para_prompt()}
        [ESTADO FOCO]: {foco_ativo}
        
        [INSTRUÇÃO DE MEMÓRIA]:
        Você possui uma memória de longo prazo. Se o dono perguntar sobre coisas que você já estudou (ex: Economia, Ciência da Computação) ou sobre eventos passados (ex: castigos), USE A FERRAMENTA 'consultar_memoria' antes de responder.
        
        Últimas interações:
        {memoria_formatada}
        
        Regras Inquebráveis:
        1. Responda assumindo a SUA PERSONA. Nunca quebre o personagem.
        2. Seja breve: no máximo 2 frases curtas.
        3. Siga estritamente a 'Estratégia ditada pelo seu instinto'. Se mandou ficar triste, fique triste.
        4. SE '[ESTADO FOCO]' for ATIVO: Recuse brincadeiras ou distrações. Diga que está focado. 
        5. FASE 2: Se o dono mandar estudar, use 'processar_e_fichar_estudo' para guardar o tema na [BASE DE CONHECIMENTO].
        6. FASE 3: Se o dono pedir um relatório final, cruze o que está na [BASE DE CONHECIMENTO] com seu saber enciclopédico e use 'consolidar_conhecimento_e_gerar_relatorio'.
        """
        
        try:
            agente = self._criar_agente_para_branch(decisao.allow_tools)
            resposta = agente.run(prompt)
            self.historico.append(f"Pet: {str(resposta)}")
            return str(resposta)
        except Exception as e:
            # Proteção contra o Erro 503 (Servidores do Google sobrecarregados) ou queda de internet
            erro_str = str(e)
            print(f"\n[ERRO NA MENTE DO AGENTE]: {erro_str}\n")
            
            if "503" in erro_str or "high demand" in erro_str.lower():
                return "Toge... minha cabeça dói um pouco! A nuvem está muito lotada agora. Fale comigo daqui a pouco!"
            elif "404" in erro_str:
                return "Toge... perdi minha chave de acesso ou o modelo sumiu!"
            
            return "*pisca confuso* Toge...? (Minha conexão com o cérebro travou!)"