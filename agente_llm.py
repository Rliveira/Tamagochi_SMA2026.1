import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import webbrowser
import psutil
import random
from datetime import datetime
from behavior_tree import BehaviorContext, build_agent_behavior_tree
from smolagents import ToolCallingAgent, LiteLLMModel, tool

# ==========================================
# 1. REFERÊNCIA GLOBAL (Blackboard)
# ==========================================
memoria_compartilhada = {}


def obter_fase_atual() -> str:
    """Retorna a fase biológica atual com base na maturidade compartilhada."""
    idade = memoria_compartilhada.get("maturidade", 0)
    if idade < 20:
        return "1_togepi"
    if idade < 50:
        return "2_togetic"
    return "3_togekiss"


def obter_nome_dono() -> str:
    """Retorna o nome do dono definido explicitamente no blackboard."""
    return memoria_compartilhada.get("nome_dono", "dono")


def obter_nome_pet() -> str:
    """Retorna o nome do pet definido explicitamente no blackboard."""
    return memoria_compartilhada.get("nome_pet", "bebê")


def obter_nome_pc() -> str:
    """Retorna o nome do computador inferido ou um fallback neutro."""
    return memoria_compartilhada.get("nome_pc", "PC")


def _truncar_texto(texto: str, limite: int = 120) -> str:
    if len(texto) <= limite:
        return texto
    return texto[: max(0, limite - 1)].rstrip() + "…"


def resumir_blackboard_para_prompt() -> str:
    """Retorna um resumo curto do estado biológico para uso no prompt."""
    chaves = ["fome", "energia", "tedio", "saude", "maturidade", "vivo", "nome_dono", "nome_pet", "nome_pc"]
    partes = []
    for chave in chaves:
        if chave in memoria_compartilhada:
            partes.append(f"{chave}={memoria_compartilhada[chave]}")
    return "; ".join(partes)


def registrar_efeito_visual(ferramenta: str, emocao: str, duracao_ms: int = 1200) -> None:
    """Registra um evento visual para a UI reagir à ferramenta usada.

    Args:
        ferramenta: Nome da ferramenta que disparou o evento.
        emocao: Emoção/animacao que a UI deve carregar.
        duracao_ms: Tempo de exibição do efeito visual.
    """
    memoria_compartilhada["visual_tool_event_id"] = memoria_compartilhada.get("visual_tool_event_id", 0) + 1
    memoria_compartilhada["visual_tool_event"] = {
        "id": memoria_compartilhada["visual_tool_event_id"],
        "ferramenta": ferramenta,
        "emocao": emocao,
        "estagio": obter_fase_atual(),
        "duracao_ms": duracao_ms,
    }


def aplicar_refeicao_compartilhada(texto_refeicao: str) -> str:
    """Atualiza o blackboard quando a conversa indica uma refeição compartilhada."""
    global memoria_compartilhada

    fome_antes = memoria_compartilhada.get("fome", 0)
    saude_antes = memoria_compartilhada.get("saude", 100)
    tedio_antes = memoria_compartilhada.get("tedio", 0)

    texto_normalizado = texto_refeicao.lower()
    if "comer" in texto_normalizado:
        reducao_fome = 18
        bonus_saude = 1
    elif any(palavra in texto_normalizado for palavra in ["almoço", "jantar", "refeição", "comida"]):
        reducao_fome = 14
        bonus_saude = 2
    else:
        reducao_fome = 10
        bonus_saude = 1

    memoria_compartilhada["fome"] = max(0, fome_antes - reducao_fome)
    memoria_compartilhada["saude"] = min(100, saude_antes + bonus_saude)
    memoria_compartilhada["tedio"] = max(0, tedio_antes - 4)
    registrar_efeito_visual("aplicar_refeicao_compartilhada", "special_attack", duracao_ms=1500)

    return (
        f"Refeição compartilhada registrada. Fome: {fome_antes} -> {memoria_compartilhada['fome']}; "
        f"Saúde: {saude_antes} -> {memoria_compartilhada['saude']}; "
        f"Tédio: {tedio_antes} -> {memoria_compartilhada['tedio']}."
    )


def _formatar_bytes(valor: int) -> str:
    unidades = ["B", "KB", "MB", "GB", "TB"]
    tamanho = float(valor)
    for unidade in unidades:
        if tamanho < 1024 or unidade == unidades[-1]:
            return f"{tamanho:.1f} {unidade}" if unidade != "B" else f"{int(tamanho)} B"
        tamanho /= 1024
    return f"{valor} B"


def _contar_extensoes(arquivos: list[Path]) -> str:
    contagem = Counter()
    for arquivo in arquivos:
        extensao = arquivo.suffix.lower() or "[sem_ext]"
        contagem[extensao] += 1
    if not contagem:
        return "Nenhum arquivo encontrado."
    partes = [f"{ext}: {qtde}" for ext, qtde in contagem.most_common(8)]
    return ", ".join(partes)


def _obter_janela_ativa_windows() -> tuple[str, str]:
    """Tenta obter título e processo da janela ativa no Windows."""
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "Nenhuma janela ativa detectada.", ""

        tamanho = user32.GetWindowTextLengthW(hwnd) + 1
        buffer = ctypes.create_unicode_buffer(tamanho)
        user32.GetWindowTextW(hwnd, buffer, tamanho)
        titulo = buffer.value.strip() or "Janela sem título"

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        processo = ""
        try:
            processo = psutil.Process(pid.value).name()
        except Exception:
            processo = ""

        return titulo, processo
    except Exception:
        return "Falha ao identificar a janela ativa.", ""


def _executar_arquivo_ou_app(caminho_ou_comando: str) -> str:
    caminho = caminho_ou_comando.strip().strip('"')
    if not caminho:
        return "Erro: caminho ou comando vazio."

    if caminho.startswith(("http://", "https://")):
        webbrowser.open(caminho)
        return f"Sucesso: URL aberta em {caminho}."

    if os.path.exists(caminho):
        os.startfile(caminho)
        return f"Sucesso: Abrindo {caminho}."

    comando = shutil.which(caminho)
    if comando:
        subprocess.Popen([comando], shell=False)
        return f"Sucesso: Aplicativo iniciado ({caminho})."

    try:
        subprocess.Popen([caminho], shell=True)
        return f"Sucesso: Comando enviado para execução ({caminho})."
    except Exception as exc:
        return f"Erro ao abrir '{caminho}': {exc}"


def _capturar_tela_temporaria() -> str:
    """Tenta gerar um print temporário da tela atual."""
    try:
        import pyautogui

        pasta_temp = Path(os.getcwd()) / "tmp"
        pasta_temp.mkdir(parents=True, exist_ok=True)
        caminho_print = pasta_temp / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        imagem = pyautogui.screenshot()
        imagem.save(caminho_print)
        return str(caminho_print)
    except Exception as exc:
        return f""


def _nome_da_ferramenta(ferramenta) -> str:
    """Obtém o nome canônico de uma ferramenta do smolagents com fallback seguro."""
    return getattr(ferramenta, "name", None) or getattr(ferramenta, "tool_name", None) or getattr(ferramenta, "__name__", "")

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
    registrar_efeito_visual("modificar_atributo_vital", "special_attack" if alteracao >= 0 else "hurt")
    memoria_compartilhada[necessidade] = max(0, min(100, memoria_compartilhada[necessidade] + alteracao))
    return f"Sucesso: O atributo {necessidade} foi alterado."


@tool
def pedir_comida_ao_dono() -> str:
    """Expressa fome do pet e pede ajuda ao dono em vez de tentar se alimentar sozinho.

    Use esta ferramenta para refletir a fase de maior dependência do pet.
    """
    idade = memoria_compartilhada.get("maturidade", 0)
    nome_dono = obter_nome_dono()
    registrar_efeito_visual("pedir_comida_ao_dono", "special_attack")

    if idade < 20:
        return f"Toge... {nome_dono}, me dá comida? Eu ainda não consigo me alimentar sozinho."
    if idade < 50:
        return f"{nome_dono}, tô com fome e preciso que você cuide de mim."
    return f"{nome_dono}, posso te avisar que minha energia está baixa, mas ainda prefiro sua ajuda para me manter bem."


@tool
def pedir_colo() -> str:
    """Pede acolhimento ao dono quando o pet está fragilizado ou inseguro.

    A intenção é reforçar dependência emocional nas fases iniciais.
    """
    nome_dono = obter_nome_dono()
    fase = obter_fase_atual()
    registrar_efeito_visual("pedir_colo", "special_attack")

    if fase == "1_togepi":
        return f"Toge... {nome_dono}, me dá colo? Eu sou pequenininho e preciso de cuidado."
    if fase == "2_togetic":
        return f"{nome_dono}, fica um pouco comigo? Ainda gosto de apoio quando fico inseguro."
    return f"{nome_dono}, estou aqui para te acompanhar também, mas ainda aprecio momentos de acolhimento."


@tool
def pedir_brincadeira() -> str:
    """Pede interação do dono em vez de tentar iniciar diversão autônoma.

    Na fase 1, o pet não brinca sozinho; ele apenas convida o dono.
    """
    nome_dono = obter_nome_dono()
    fase = obter_fase_atual()
    registrar_efeito_visual("pedir_brincadeira", "special_attack")

    if fase == "1_togepi":
        return f"{nome_dono}, brinca comigo? Eu ainda não consigo me divertir sozinho."
    if fase == "2_togetic":
        return f"{nome_dono}, bora fazer alguma coisa juntos?"
    return f"{nome_dono}, quer uma pausa rápida para eu te acompanhar em algo leve?"


@tool
def reagir_a_toque(tipo_toque: str = "carinho") -> str:
    """Retorna uma reação textual a um toque físico ou clique no pet.

    Args:
        tipo_toque: Tipo de contato recebido. Exemplos: 'carinho', 'click', 'arrasto'.
    """
    fase = obter_fase_atual()
    tipo_normalizado = tipo_toque.strip().lower()

    if tipo_normalizado == "carinho":
        registrar_efeito_visual("reagir_a_toque", "special_attack")
    elif tipo_normalizado == "arrasto":
        registrar_efeito_visual("reagir_a_toque", "hurt")
    else:
        registrar_efeito_visual("reagir_a_toque", "movement")

    if fase == "1_togepi":
        if tipo_normalizado == "carinho":
            return "Toge-toge! *encosta de volta com confiança*"
        if tipo_normalizado == "arrasto":
            return "Toge... *fica assustadinho e procura o dono*"
        return "Toge? *pisca curioso*"

    if fase == "2_togetic":
        if tipo_normalizado == "carinho":
            return "Togetic! *gira feliz no ar*"
        if tipo_normalizado == "arrasto":
            return "Ei! *se solta e reclama de leve*"
        return "Toge? *observa com atenção*"

    if tipo_normalizado == "carinho":
        return "Togekiss... *aceita com serenidade e carinho*"
    if tipo_normalizado == "arrasto":
        return "Togekiss... *se reposiciona com calma*"
    return "Togekiss. *responde com calma ao contato*"


@tool
def observar_contexto_rapido() -> str:
    """Resume o contexto imediato do sistema sem executar ações destrutivas.

    A ferramenta prioriza janela ativa, usuário local, fase do pet e métricas do PC.
    """
    titulo_janela, processo_janela = _obter_janela_ativa_windows()
    registrar_efeito_visual("observar_contexto_rapido", "idle_movement")
    cpu = psutil.cpu_percent(interval=0.2)
    memoria = psutil.virtual_memory()
    nome_pc = obter_nome_pc()
    nome_dono = obter_nome_dono()
    fase = obter_fase_atual()

    return (
        f"PC: {nome_pc}; Dono: {nome_dono}; Fase: {fase}; "
        f"Janela ativa: {titulo_janela}" + (f" ({processo_janela})" if processo_janela else "") + "; "
        f"CPU: {cpu:.0f}%; RAM: {memoria.percent:.0f}%."
    )


@tool
def descrever_tela_em_texto() -> str:
    """Faz uma descrição textual curta do contexto visual mais provável da tela.

    Nesta primeira versão, usa janela ativa e processo como proxy de leitura de tela.
    """
    titulo_janela, processo_janela = _obter_janela_ativa_windows()
    registrar_efeito_visual("descrever_tela_em_texto", "idle_movement")
    if processo_janela:
        return f"A tela parece estar focada em '{titulo_janela}', provavelmente ligada ao processo '{processo_janela}'."
    return f"A tela parece estar focada em '{titulo_janela}'."


@tool
def resumir_conteudo_de_pasta(caminho_pasta: str, limite_arquivos: int = 20) -> str:
    """Resume o conteúdo de uma pasta com foco em arquivos, subpastas e extensões.

    Args:
        caminho_pasta: Caminho absoluto ou relativo da pasta a ser inspecionada.
        limite_arquivos: Quantidade máxima de arquivos para considerar no resumo.
    """
    pasta = Path(caminho_pasta).expanduser()
    registrar_efeito_visual("resumir_conteudo_de_pasta", "idle_movement")
    if not pasta.exists() or not pasta.is_dir():
        return f"Erro: a pasta '{caminho_pasta}' não existe ou não é uma pasta válida."

    arquivos = [item for item in pasta.rglob("*") if item.is_file()]
    subpastas = [item for item in pasta.rglob("*") if item.is_dir()]
    arquivos_analise = arquivos[: max(0, limite_arquivos)]

    if arquivos:
        maior_arquivo = max(arquivos, key=lambda item: item.stat().st_size)
        menor_arquivo = min(arquivos, key=lambda item: item.stat().st_size)
    else:
        maior_arquivo = menor_arquivo = None

    total_bytes = 0
    for arquivo in arquivos:
        try:
            total_bytes += arquivo.stat().st_size
        except OSError:
            continue

    linhas = [
        f"Pasta: {pasta.resolve()}",
        f"Arquivos: {len(arquivos)} | Subpastas: {len(subpastas)} | Tamanho total: {_formatar_bytes(total_bytes)}",
        f"Extensões mais comuns: {_contar_extensoes(arquivos_analise)}",
    ]

    if arquivos_analise:
        nomes_relevantes = ", ".join(item.name for item in arquivos_analise[:8])
        linhas.append(f"Amostra de arquivos: {nomes_relevantes}")

    if maior_arquivo is not None and menor_arquivo is not None:
        linhas.append(
            f"Maior arquivo: {maior_arquivo.name} ({_formatar_bytes(maior_arquivo.stat().st_size)}) | "
            f"Menor arquivo: {menor_arquivo.name} ({_formatar_bytes(menor_arquivo.stat().st_size)})"
        )

    return "\n".join(linhas)


@tool
def listar_arquivos_relevantes(caminho_pasta: str, extensoes: str = "") -> str:
    """Lista arquivos relevantes de uma pasta com filtro opcional por extensão.

    Args:
        caminho_pasta: Caminho da pasta.
        extensoes: Lista separada por vírgula com extensões desejadas, por exemplo '.txt,.md,.py'.
    """
    pasta = Path(caminho_pasta).expanduser()
    registrar_efeito_visual("listar_arquivos_relevantes", "idle_movement")
    if not pasta.exists() or not pasta.is_dir():
        return f"Erro: a pasta '{caminho_pasta}' não existe ou não é válida."

    filtro = {item.strip().lower() for item in extensoes.split(",") if item.strip()}
    arquivos = []
    for item in pasta.rglob("*"):
        if not item.is_file():
            continue
        if filtro and item.suffix.lower() not in filtro:
            continue
        arquivos.append(item)

    if not arquivos:
        return "Nenhum arquivo relevante encontrado com os filtros informados."

    arquivos_ordenados = sorted(arquivos, key=lambda item: (item.suffix.lower(), item.name.lower()))[:50]
    linhas = [str(item.relative_to(pasta)) for item in arquivos_ordenados]
    return "\n".join(linhas)


@tool
def checar_saude_do_pc() -> str:
    """Coleta indicadores rápidos de saúde do computador.

    Retorna CPU, memória, disco, bateria e processo em foco quando possível.
    """
    cpu = psutil.cpu_percent(interval=0.2)
    registrar_efeito_visual("checar_saude_do_pc", "attack")
    memoria = psutil.virtual_memory()
    disco = psutil.disk_usage(os.getcwd())
    bateria = psutil.sensors_battery()
    titulo_janela, processo_janela = _obter_janela_ativa_windows()
    bateria_texto = f"{bateria.percent:.0f}%" if bateria else "Sem bateria detectada"

    return (
        f"CPU: {cpu:.0f}% | RAM: {memoria.percent:.0f}% | Disco: {disco.percent:.0f}% | "
        f"Bateria: {bateria_texto} | Janela ativa: {titulo_janela}" +
        (f" ({processo_janela})" if processo_janela else "")
    )


@tool
def abrir_aplicativo(caminho_ou_nome: str) -> str:
    """Abre um aplicativo, arquivo ou URL no sistema operacional.

    Args:
        caminho_ou_nome: Caminho de um arquivo, nome de um aplicativo instalado ou URL completa.
    """
    registrar_efeito_visual("abrir_aplicativo", "attack")
    return _executar_arquivo_ou_app(caminho_ou_nome)


@tool
def abrir_pasta(caminho_pasta: str) -> str:
    """Abre uma pasta no explorador de arquivos do sistema.

    Args:
        caminho_pasta: Caminho absoluto ou relativo da pasta a abrir.
    """
    registrar_efeito_visual("abrir_pasta", "attack")
    pasta = Path(caminho_pasta).expanduser()
    if not pasta.exists() or not pasta.is_dir():
        return f"Erro: a pasta '{caminho_pasta}' não existe ou não é válida."
    os.startfile(str(pasta.resolve()))
    return f"Sucesso: pasta aberta em {pasta.resolve()}."


@tool
def criar_lembrete(texto: str, nome_arquivo: str = "lembrete_tamagochi.txt") -> str:
    """Cria um arquivo de lembrete em texto simples e tenta abri-lo automaticamente.

    Args:
        texto: Conteúdo do lembrete a ser salvo.
        nome_arquivo: Nome do arquivo texto que será criado.
    """
    registrar_efeito_visual("criar_lembrete", "special_attack")
    nome_arquivo_limpo = nome_arquivo.strip() or "lembrete_tamagochi.txt"
    destino = Path(os.getcwd()) / nome_arquivo_limpo
    with open(destino, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto.strip() + "\n")
    try:
        os.startfile(str(destino))
    except Exception:
        pass
    return f"Sucesso: lembrete salvo em {destino}."


@tool
def capturar_tela_rapida() -> str:
    """Tenta capturar uma imagem temporária da tela atual.

    Se a dependência de captura não estiver instalada, retorna uma mensagem de fallback.
    """
    registrar_efeito_visual("capturar_tela_rapida", "attack")
    caminho = _capturar_tela_temporaria()
    if not caminho:
        return "Falha: a captura de tela rápida não está disponível neste ambiente."
    return f"Sucesso: captura salva em {caminho}."


@tool
def trazer_janela_do_pet_para_frente() -> str:
    """Tenta trazer a janela atual do pet para o primeiro plano no Windows."""
    registrar_efeito_visual("trazer_janela_do_pet_para_frente", "attack")
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return "Sucesso: a janela atual foi reforçada para o primeiro plano."
        return "Não foi possível identificar a janela ativa para mover à frente."
    except Exception as exc:
        return f"Falha ao trazer a janela para frente: {exc}"

@tool
def abrir_site(url_ou_nome: str) -> str:
    """
    Abre um site no navegador do usuário.
    
    Args:
        url_ou_nome: O nome do site (ex: 'youtube', 'google') ou o link completo.
    """
    registrar_efeito_visual("abrir_site", "attack")
    if not url_ou_nome.startswith("http"):
        url_ou_nome = f"https://www.{url_ou_nome}.com"
    webbrowser.open(url_ou_nome)
    return f"Sucesso: Navegador aberto em {url_ou_nome}."

@tool
def verificar_hardware() -> str:
    """Verifica a bateria e o uso de CPU do computador do dono."""
    registrar_efeito_visual("verificar_hardware", "attack")
    bateria = psutil.sensors_battery()
    cpu = psutil.cpu_percent(interval=0.5)
    status_bateria = f"{bateria.percent}%" if bateria else "PC de mesa"
    return f"Status lido: CPU em {cpu}%. Bateria: {status_bateria}."


@tool
def abrir_conforto_emocional() -> str:
    """Cria uma mensagem de conforto simples para o dono em fase madura."""
    nome_dono = obter_nome_dono()
    registrar_efeito_visual("abrir_conforto_emocional", "special_attack")
    caminho_arquivo = os.path.join(os.getcwd(), "mensagem_de_conforto.txt")
    with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"Oi, {nome_dono}.\n\n")
        arquivo.write("Se estiver difícil, pare por um instante, respire e descanse a vista.\n")
        arquivo.write("Estou aqui com você.\n")
    try:
        os.startfile(caminho_arquivo)
    except Exception:
        pass
    return f"Sucesso: mensagem de conforto criada para {nome_dono}."


# ==========================================
# 3. FERRAMENTAS EMOCIONAIS EVOLUTIVAS
# ==========================================
@tool
def oferecer_conforto_emocional() -> str:
    """Use APENAS quando o dono disser que está triste, cansado, ansioso ou precisar de apoio."""
    global memoria_compartilhada
    idade = memoria_compartilhada["maturidade"]
    registrar_efeito_visual("oferecer_conforto_emocional", "special_attack")
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
    registrar_efeito_visual("trazer_presente_virtual", "special_attack")
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
    registrar_efeito_visual("reagir_a_comportamento_negativo", "hurt")
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

        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        self.modelo = LiteLLMModel(model_id="gemini/gemini-2.5-flash", temperature=0.3)
        self.arvore_comportamental = build_agent_behavior_tree()
        self.biblioteca_ferramentas = {}
        
        self.ferramentas = [
            modificar_atributo_vital,
            pedir_comida_ao_dono,
            pedir_colo,
            pedir_brincadeira,
            reagir_a_toque,
            observar_contexto_rapido,
            descrever_tela_em_texto,
            resumir_conteudo_de_pasta,
            listar_arquivos_relevantes,
            checar_saude_do_pc,
            abrir_aplicativo,
            abrir_pasta,
            criar_lembrete,
            capturar_tela_rapida,
            trazer_janela_do_pet_para_frente,
            abrir_conforto_emocional,
            abrir_site,
            verificar_hardware,
            oferecer_conforto_emocional,
            trazer_presente_virtual,
            reagir_a_comportamento_negativo
        ]
        self.biblioteca_ferramentas = {
            nome: ferramenta
            for ferramenta in self.ferramentas
            if (nome := _nome_da_ferramenta(ferramenta))
        }
        
        self.historico = []

    def _criar_agente_para_branch(self, nomes_ferramentas: list[str]) -> ToolCallingAgent:
        ferramentas_filtradas = [
            ferramenta
            for nome, ferramenta in self.biblioteca_ferramentas.items()
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
            resumo_refeicao = aplicar_refeicao_compartilhada(mensagem_usuario)
            self.historico.append(f"Sistema: {resumo_refeicao}")
            if len(self.historico) > 4:
                self.historico.pop(0)

        if not decisao.llm_enabled:
            if decisao.branch == "estado_final":
                return "Toge... eu estou sem energia para agir agora."
            return "Toge..."

        idade = memoria_compartilhada["maturidade"]
        nome_dono = memoria_compartilhada.get("nome_dono", "dono")
        nome_pet = memoria_compartilhada.get("nome_pet", "Togepi")
        nome_pc = memoria_compartilhada.get("nome_pc", "PC")

        if idade < 20:
            persona = "Bebê Togepi: fofo, dependente e simples."
        elif idade < 50:
            persona = "Adolescente Togetic: curioso, leve e um pouco rebelde."
        else:
            persona = "Adulto Togekiss: sereno, útil e protetor."

        self.historico.append(f"{nome_dono}: {_truncar_texto(mensagem_usuario, 80)}")
        if len(self.historico) > 4:
            self.historico.pop(0)
            
        memoria_formatada = "\n".join(self.historico[-3:])
        
        prompt = f"""
        Você é um desktop pet chamado {nome_pet} no PC do dono.
        Persona: {persona}
        Estado: {estado_emocional_atual}
        Estrategia BT: branch={decisao.branch}; emocao={decisao.emocao}; tools={', '.join(decisao.allow_tools) if decisao.allow_tools else 'nenhuma'}
        Diretriz BT: {decisao.prompt_hint}
        Identidade: dono={nome_dono}; pc={nome_pc}
        Blackboard: {resumir_blackboard_para_prompt()}
        Memória recente:
        {memoria_formatada}
        Mensagem do dono: "{mensagem_usuario}"

        Regras:
        - Siga a estrategia da Behavior Tree antes de improvisar.
        - Use apenas ferramentas permitidas pela estrategia.
        - Fase 1: dependente; não se alimenta nem brinca sozinho.
        - Fase 2: observa e pede ajuda.
        - Fase 3: ajuda de forma útil.
        - Use tools de contexto/arquivos só quando ajudarem de verdade.
        - Use tools de sistema só quando o benefício for claro.
        - Responda em no máximo 2 frases.
        """
        
        try:
            agente = self._criar_agente_para_branch(decisao.allow_tools)
            resposta = agente.run(prompt)
            self.historico.append(f"Pet: {str(resposta)}")
            return str(resposta)
        except Exception as e:
            print(f"\n[ERRO NA MENTE DO AGENTE]: {e}\n")
            return "*pisca confuso* Toge...? (Minha conexão com a inteligência travou!)"