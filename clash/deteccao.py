"""Fase fina (fine-phase): para cada par candidato do broad-phase,
classifica como hard clash, soft clash (folga insuficiente) ou
duplicado — ou devolve None se, examinado de perto, não há
interferência real."""
import fcl
import numpy as np


def _bvh(malha):
    modelo = fcl.BVHModel()
    modelo.beginModel(len(malha.vertices), len(malha.faces))
    modelo.addSubModel(malha.vertices, malha.faces)
    modelo.endModel()
    return fcl.CollisionObject(modelo)


def _eh_duplicado(elemento_a, elemento_b, regras):
    if elemento_a.disciplina != elemento_b.disciplina:
        return False

    centro_a = (elemento_a.bbox_min + elemento_a.bbox_max) / 2.0
    centro_b = (elemento_b.bbox_min + elemento_b.bbox_max) / 2.0
    distancia_centros = float(np.linalg.norm(centro_a - centro_b))
    limite_distancia = regras.duplicados.get("distancia_centro_m", 0.02)
    if distancia_centros > limite_distancia:
        return False

    volume_a = max(elemento_a.malha.volume, 1e-9)
    volume_b = max(elemento_b.malha.volume, 1e-9)
    diferenca_pct = abs(volume_a - volume_b) / max(volume_a, volume_b) * 100.0
    return diferenca_pct <= regras.duplicados.get("tolerancia_volume_pct", 2.0)


def classificar_par(elemento_a, elemento_b, regras):
    """Retorna um dict descrevendo a interferência (tipo, distância,
    penetração, volume de interseção quando viável) ou None quando,
    examinado de perto, o par não representa um problema real."""
    folga_exigida = regras.folga_minima(elemento_a.disciplina, elemento_b.disciplina)

    if _eh_duplicado(elemento_a, elemento_b, regras):
        return {
            "tipo": "duplicado",
            "distancia_m": 0.0,
            "penetracao_m": None,
            "volume_intersecao_m3": None,
            "folga_exigida_m": folga_exigida,
        }

    objeto_a = _bvh(elemento_a.malha)
    objeto_b = _bvh(elemento_b.malha)

    req_colisao = fcl.CollisionRequest(enable_contact=True, num_max_contacts=4)
    res_colisao = fcl.CollisionResult()
    fcl.collide(objeto_a, objeto_b, req_colisao, res_colisao)

    if res_colisao.is_collision:
        penetracao = max((c.penetration_depth for c in res_colisao.contacts), default=0.0)
        if penetracao < regras.tolerancia_hard_clash_m:
            return None  # penetração irrelevante — ruído de modelagem/arredondamento

        volume_intersecao = None
        try:
            intersecao = elemento_a.malha.intersection(elemento_b.malha, engine="manifold")
            if intersecao is not None and not intersecao.is_empty:
                volume_intersecao = float(intersecao.volume)
        except Exception:
            pass  # volume exato é "se viável" (pedido explícito) — segue sem ele

        return {
            "tipo": "hard",
            "distancia_m": 0.0,
            "penetracao_m": float(penetracao),
            "volume_intersecao_m3": volume_intersecao,
            "folga_exigida_m": folga_exigida,
        }

    req_distancia = fcl.DistanceRequest()
    res_distancia = fcl.DistanceResult()
    fcl.distance(objeto_a, objeto_b, req_distancia, res_distancia)
    distancia = float(res_distancia.min_distance)

    if distancia < folga_exigida:
        return {
            "tipo": "folga",
            "distancia_m": distancia,
            "penetracao_m": None,
            "volume_intersecao_m3": None,
            "folga_exigida_m": folga_exigida,
        }

    return None
