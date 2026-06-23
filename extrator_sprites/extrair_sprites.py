import cv2
import numpy as np
import os

def classificar_sprite(cx, cy, img_w, img_h):
    """
    Recebe a coordenada X e Y do centro do sprite e compara com 
    o mapa visual da imagem original usando porcentagens (0.0 a 1.0).
    """
    px = cx / img_w  # Posição X relativa (0.0 a 1.0)
    py = cy / img_h  # Posição Y relativa (0.0 a 1.0)

    # ==========================================
    # PAINEL 1: TOGEPI (0% a 33% da imagem)
    # ==========================================
    if px < 0.33:
        pokemon = "1_togepi"
        if px < 0.08:
            acao = "asleep" if py < 0.5 else "hurt"
        elif px < 0.15:
            acao = "idle_attack"
        elif px < 0.25:
            acao = "movement"
        else:
            acao = "special_attack"

    # ==========================================
    # PAINEL 2: TOGETIC (33% a 66% da imagem)
    # ==========================================
    elif px < 0.66:
        pokemon = "2_togetic"
        if px < 0.40:
            acao = "asleep" if py < 0.5 else "hurt"
        elif px < 0.49:
            acao = "idle_movement"
        elif px < 0.56:
            acao = "attack"
        else:
            acao = "special_attack"

    # ==========================================
    # PAINEL 3: TOGEKISS (66% a 100% da imagem)
    # ==========================================
    else:
        pokemon = "3_togekiss"
        if px < 0.74:
            acao = "asleep" if py < 0.5 else "hurt"
        elif px < 0.85:
            acao = "idle_movement"
        elif px < 0.92:
            acao = "attack"
        else:
            acao = "special_attack"

    return os.path.join(pokemon, acao)

def extrair_e_organizar(caminho_imagem, pasta_base):
    img = cv2.imread(caminho_imagem)
    if img is None:
        print("❌ Erro ao carregar imagem.")
        return

    img_h, img_w = img.shape[:2]
    cor_fundo = img[0, 0] 
    b, g, r = int(cor_fundo[0]), int(cor_fundo[1]), int(cor_fundo[2])

    limite_inferior = np.array([max(0, b-10), max(0, g-10), max(0, r-10)], dtype=np.uint8)
    limite_superior = np.array([min(255, b+10), min(255, g+10), min(255, r+10)], dtype=np.uint8)
    
    mascara_fundo = cv2.inRange(img, limite_inferior, limite_superior)
    mascara_sprites = cv2.bitwise_not(mascara_fundo)
    contornos, _ = cv2.findContours(mascara_sprites, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    contador = 0
    for contorno in contornos:
        x, y, w, h = cv2.boundingRect(contorno)
        
        if w > 12 and h > 12:
            # Calcula o centro geométrico do sprite
            centro_x = x + (w / 2)
            centro_y = y + (h / 2)
            
            # Descobre em qual pasta ele deve entrar
            subpasta = classificar_sprite(centro_x, centro_y, img_w, img_h)
            pasta_destino = os.path.join(pasta_base, subpasta)
            
            # Cria a subpasta dinamicamente se não existir
            if not os.path.exists(pasta_destino):
                os.makedirs(pasta_destino)
                
            x_inicio, y_inicio = max(0, x - 1), max(0, y - 1)
            x_fim, y_fim = min(img_w, x + w + 1), min(img_h, y + h + 1)
            
            recorte_bgr = img[y_inicio:y_fim, x_inicio:x_fim]
            recorte_bgra = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2BGRA)
            recorte_bgra[:, :, 3] = mascara_sprites[y_inicio:y_fim, x_inicio:x_fim] 
            
            nome_arquivo = os.path.join(pasta_destino, f"frame_{contador:03d}.png")
            cv2.imwrite(nome_arquivo, recorte_bgra)
            contador += 1
            
    print(f"✅ Organização concluída! {contador} sprites distribuídos em pastas dentro de '{pasta_base}'.")

# ==========================================
# EXECUÇÃO DO SCRIPT
# ==========================================
NOME_DO_ARQUIVO = "DS _ DSi - Pokemon Mystery Dungeon_ Explorers of Time _ Darkness - Pokemon (2nd Generation) - Togepi, Togetic & Togekiss.png" 
PASTA_DE_DESTINO = "sprites_organizados"

extrair_e_organizar(NOME_DO_ARQUIVO, PASTA_DE_DESTINO)