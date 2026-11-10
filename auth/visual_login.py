"""Renderização (PIL) da tela de login no estilo do Figma: fundo azul
escuro em tela cheia, cartão de vidro translúcido centralizado com
cantos arredondados, campos brancos e botões arredondados. Tudo que é
estático é desenhado numa única imagem de fundo; os widgets Tk
(entradas) e os botões ficam por cima, posicionados pelo Canvas."""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

from config import FUNDO_LOGIN_FOTO, FUNDO_LOGIN_TEXTURA

CARTAO_LARGURA = 430
CARTAO_ALTURA = 530
CARTAO_RAIO = 26

AZUL_FUNDO = (9, 38, 52)
BRANCO = (255, 255, 255)


def _cobrir(imagem, largura, altura):
    """Redimensiona/corta `imagem` para cobrir largura x altura sem
    distorcer (equivalente a `background-size: cover`)."""
    escala = max(largura / imagem.width, altura / imagem.height)
    nova = imagem.resize((max(1, round(imagem.width * escala)),
                          max(1, round(imagem.height * escala))), Image.LANCZOS)
    x = (nova.width - largura) // 2
    y = (nova.height - altura) // 2
    return nova.crop((x, y, x + largura, y + altura))


def _fundo_procedural(largura, altura):
    """Sem foto do prédio: textura listrada da marca escurecida, com
    vinheta e faixas curvas claras sugerindo a fachada da imagem do
    Figma."""
    if os.path.exists(FUNDO_LOGIN_TEXTURA):
        base = _cobrir(Image.open(FUNDO_LOGIN_TEXTURA).convert("RGB"), largura, altura)
    else:
        base = Image.new("RGB", (largura, altura), (14, 70, 92))
    base = Image.blend(base, Image.new("RGB", base.size, AZUL_FUNDO), 0.45)

    # faixas curvas (fachada) — arcos concêntricos claros e suaves
    faixas = Image.new("L", (largura, altura), 0)
    d = ImageDraw.Draw(faixas)
    cx, cy = int(largura * 0.72), int(altura * 1.35)
    for i in range(14):
        r = int(altura * (0.55 + i * 0.075))
        d.arc((cx - r * 1.6, cy - r, cx + r * 1.6, cy + r), 180, 330,
              fill=60 - i * 3, width=max(2, altura // 160))
    faixas = faixas.filter(ImageFilter.GaussianBlur(altura / 300))
    base.paste(Image.new("RGB", base.size, (120, 170, 190)), (0, 0), faixas)

    # vinheta: escurece as bordas, centro um pouco mais claro
    vinheta = Image.new("L", (largura, altura), 0)
    dv = ImageDraw.Draw(vinheta)
    dv.ellipse((-largura * 0.2, -altura * 0.3, largura * 1.2, altura * 1.3), fill=255)
    vinheta = vinheta.filter(ImageFilter.GaussianBlur(min(largura, altura) / 5))
    escuro = Image.new("RGB", base.size, (4, 20, 30))
    return Image.composite(base, escuro, vinheta)


def renderizar_fundo(largura, altura):
    if os.path.exists(FUNDO_LOGIN_FOTO):
        foto = _cobrir(Image.open(FUNDO_LOGIN_FOTO).convert("RGB"), largura, altura)
        return Image.blend(foto, Image.new("RGB", foto.size, AZUL_FUNDO), 0.08)  # a foto já vem tratada
    return _fundo_procedural(largura, altura)


def mascara_arredondada(largura, altura, raio, supersample=4):
    """Máscara 'L' de retângulo arredondado com borda suavizada."""
    s = supersample
    m = Image.new("L", (largura * s, altura * s), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, largura * s - 1, altura * s - 1),
                                        radius=raio * s, fill=255)
    return m.resize((largura, altura), Image.LANCZOS)


def aplicar_cartao_vidro(fundo, x, y, largura=CARTAO_LARGURA, altura=CARTAO_ALTURA,
                         raio=CARTAO_RAIO, tom=(150, 185, 200), opacidade=0.16):
    """Efeito 'glassmorphism': desfoca a região do fundo sob o cartão,
    mistura com `tom` (clarear: tom claro e pouca opacidade; o cartão
    azul do "Criar usuário": tom azul e opacidade alta) e contorna com
    uma borda branca translúcida."""
    regiao = fundo.crop((x, y, x + largura, y + altura)).filter(ImageFilter.GaussianBlur(22))
    regiao = Image.blend(regiao, Image.new("RGB", regiao.size, tom), opacidade)
    mascara = mascara_arredondada(largura, altura, raio)
    fundo.paste(regiao, (x, y), mascara)

    s = 4
    borda = Image.new("RGBA", (largura * s, altura * s), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle(
        (s, s, largura * s - s - 1, altura * s - s - 1), radius=raio * s,
        outline=(255, 255, 255, 80), width=s * 1)
    borda = borda.resize((largura, altura), Image.LANCZOS)
    fundo.paste(borda, (x, y), borda)


def colar_retangulo(fundo, x, y, largura, altura, raio, cor):
    mascara = mascara_arredondada(largura, altura, raio)
    fundo.paste(Image.new("RGB", (largura, altura), cor), (x, y), mascara)


def imagem_botao(largura, altura, raio, cor, borda=None, fundo_rgba=(0, 0, 0, 0)):
    """Botão arredondado RGBA (com transparência nos cantos)."""
    s = 4
    img = Image.new("RGBA", (largura * s, altura * s), fundo_rgba)
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, largura * s - 1, altura * s - 1), radius=raio * s, fill=cor,
        outline=borda, width=s if borda else 0)
    return img.resize((largura, altura), Image.LANCZOS)


def imagem_olho(tamanho=20, cor=(40, 50, 60), riscado=False):
    """Ícone de olho (mostrar/ocultar senha) desenhado vetorialmente."""
    s = 4
    t = tamanho * s
    img = Image.new("RGBA", (t, t), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    w = max(1, int(1.6 * s))
    # pálpebras: duas curvas formando uma amêndoa
    pontos_sup, pontos_inf = [], []
    for i in range(41):
        a = i / 40
        px = t * 0.08 + a * t * 0.84
        py = math.sin(a * math.pi) * t * 0.28
        pontos_sup.append((px, t / 2 - py))
        pontos_inf.append((px, t / 2 + py))
    d.line(pontos_sup, fill=cor, width=w, joint="curve")
    d.line(pontos_inf, fill=cor, width=w, joint="curve")
    r = t * 0.13
    d.ellipse((t / 2 - r, t / 2 - r, t / 2 + r, t / 2 + r), fill=cor)
    if riscado:
        d.line((t * 0.15, t * 0.85, t * 0.85, t * 0.15), fill=cor, width=w)
    return img.resize((tamanho, tamanho), Image.LANCZOS)


def carregar_logo(caminho, largura_max, altura_max):
    if not os.path.exists(caminho):
        return None
    img = Image.open(caminho).convert("RGBA")
    img.thumbnail((largura_max, altura_max), Image.LANCZOS)
    return img


def colar_retangulo_rgba(fundo, x, y, largura, altura, raio, preenchimento, contorno=None):
    """Retângulo arredondado semitransparente (RGBA) sobre o fundo RGB."""
    s = 4
    img = Image.new("RGBA", (largura * s, altura * s), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, largura * s - 1, altura * s - 1), radius=raio * s,
                                          fill=preenchimento, outline=contorno, width=s if contorno else 0)
    img = img.resize((largura, altura), Image.LANCZOS)
    fundo.paste(img, (x, y), img)
