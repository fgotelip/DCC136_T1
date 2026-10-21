"""Heurística construtiva: gera uma solução inicial viável.

  FASE 1 - decide o tipo de prova de cada ESCOLA (todas as salas dela recebem o mesmo tipo).
  FASE 2 - aloca cada candidato a uma escola do tipo dele e depois a uma sala.

Detalhes e justificativas: construtivo.md
"""

import os
import time

import numpy as np

from solucao import montar_resumo, preencher_salas, verificar_viabilidade

LIMITE_DE_NOS_DA_BUSCA = 200_000


def definir_tipo_de_cada_escola(tipo_de_prova_do_candidato, capacidades_das_salas, distancias):
    """Busca com retrocesso: percorre as escolas (da maior para a menor) e tenta dar a cada uma
    o tipo mais barato primeiro. Volta atrás se a capacidade restante não cobrir mais a demanda."""
    tipos_de_prova = sorted(set(tipo_de_prova_do_candidato))
    quantidade_de_escolas = len(capacidades_das_salas)
    capacidade_da_escola = [sum(capacidades) for capacidades in capacidades_das_salas]
    demanda_sem_cobertura = {tipo: tipo_de_prova_do_candidato.count(tipo) for tipo in tipos_de_prova}

    # custo estimado de a escola atender o tipo: distância média dos candidatos
    # do tipo que estão mais perto dela (tantos quanto cabem na escola)
    custo_estimado = {}
    for tipo in tipos_de_prova:
        indices_do_tipo = [i for i, t in enumerate(tipo_de_prova_do_candidato) if t == tipo]
        for escola in range(quantidade_de_escolas):
            mais_proximos = np.sort(distancias[indices_do_tipo, escola])[:capacidade_da_escola[escola]]
            custo_estimado[(escola, tipo)] = mais_proximos.mean()

    escolas_da_maior_para_a_menor = sorted(range(quantidade_de_escolas),
                                           key=lambda escola: -capacidade_da_escola[escola])
    tipo_da_escola = {}
    nos_visitados = 0

    def escolher_tipo(posicao):
        nonlocal nos_visitados
        nos_visitados += 1
        if nos_visitados > LIMITE_DE_NOS_DA_BUSCA:
            return False
        if posicao == quantidade_de_escolas:
            return all(falta <= 0 for falta in demanda_sem_cobertura.values())

        # poda: a capacidade das escolas que restam precisa cobrir o que ainda falta
        capacidade_restante = sum(capacidade_da_escola[e] for e in escolas_da_maior_para_a_menor[posicao:])
        if capacidade_restante < sum(max(0, falta) for falta in demanda_sem_cobertura.values()):
            return False

        escola = escolas_da_maior_para_a_menor[posicao]
        for tipo in sorted(tipos_de_prova, key=lambda tipo: custo_estimado[(escola, tipo)]):
            demanda_sem_cobertura[tipo] -= capacidade_da_escola[escola]
            tipo_da_escola[escola] = tipo
            if escolher_tipo(posicao + 1):
                return True
            demanda_sem_cobertura[tipo] += capacidade_da_escola[escola]   # desfaz e tenta o próximo tipo
        return False

    if not escolher_tipo(0):
        raise ValueError("não foi possível cobrir a demanda de todos os tipos de prova")
    return [tipo_da_escola[escola] for escola in range(quantidade_de_escolas)]


def alocar_candidatos_do_tipo(candidatos, vagas_por_escola, distancias, escola_do_candidato):
    """Aloca os candidatos de UM tipo. vagas_por_escola[e] = vagas que a escola e oferece para o tipo."""
    escolas = np.where(vagas_por_escola > 0)[0]
    vagas_livres = vagas_por_escola[escolas].copy()
    distancias_do_tipo = distancias[np.ix_(candidatos, escolas)]

    # ordem: maior arrependimento primeiro = quem mais perde se não ficar na escola mais próxima
    ordenadas = np.sort(distancias_do_tipo, axis=1)
    arrependimento = ordenadas[:, 1] - ordenadas[:, 0] if len(escolas) > 1 else np.zeros(len(candidatos))

    for posicao in np.argsort(-arrependimento, kind="stable"):
        for coluna in np.argsort(distancias_do_tipo[posicao], kind="stable"):   # da mais perto à mais longe
            if vagas_livres[coluna] > 0:
                escola_do_candidato[candidatos[posicao]] = escolas[coluna]
                vagas_livres[coluna] -= 1
                break


def alocar_candidatos(tipo_de_prova_do_candidato, capacidades_das_salas, tipo_da_escola, distancias):
    tipos_como_vetor = np.array(tipo_de_prova_do_candidato)
    escola_do_candidato = np.full(len(tipo_de_prova_do_candidato), -1)

    # Cada tipo é independente dos outros: só disputa vagas com candidatos do mesmo tipo
    for tipo in set(tipo_de_prova_do_candidato):
        vagas_por_escola = np.array([sum(capacidades) if tipo_da_escola[escola] == tipo else 0
                                     for escola, capacidades in enumerate(capacidades_das_salas)])
        alocar_candidatos_do_tipo(np.where(tipos_como_vetor == tipo)[0], vagas_por_escola,
                                  distancias, escola_do_candidato)

    # dentro de cada escola, os candidatos vão enchendo as salas uma por vez
    tipo_da_sala = [[tipo_da_escola[escola]] * len(capacidades)
                    for escola, capacidades in enumerate(capacidades_das_salas)]
    sala_do_candidato = preencher_salas(escola_do_candidato, tipo_da_sala, capacidades_das_salas,
                                        tipo_de_prova_do_candidato)
    return escola_do_candidato, sala_do_candidato


def construir(tipo_de_prova_do_candidato, capacidades_das_salas, distancias):
    tipo_da_escola = definir_tipo_de_cada_escola(tipo_de_prova_do_candidato, capacidades_das_salas, distancias)
    escola_do_candidato, sala_do_candidato = alocar_candidatos(
        tipo_de_prova_do_candidato, capacidades_das_salas, tipo_da_escola, distancias)
    return {
        "tipo_da_sala": [[tipo_da_escola[e]] * len(capacidades_das_salas[e]) for e in range(len(tipo_da_escola))],
        "escola_do_candidato": escola_do_candidato,
        "sala_do_candidato": sala_do_candidato,
    }


if __name__ == "__main__":
    import sys
    from instancia import ler_instancia

    caminho = sys.argv[1]
    if not os.path.exists(caminho):          # procura ao lado do script
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), caminho)
    (ids_dos_candidatos, tipo_de_prova_do_candidato, ids_das_escolas,
     capacidades_das_salas, distancias) = ler_instancia(caminho)

    instante_inicial = time.perf_counter()
    solucao = construir(tipo_de_prova_do_candidato, capacidades_das_salas, distancias)
    print(f"tempo = {time.perf_counter() - instante_inicial:.2f}s")

    print(montar_resumo(solucao, ids_das_escolas, capacidades_das_salas, distancias))
    problemas = verificar_viabilidade(solucao, tipo_de_prova_do_candidato, capacidades_das_salas, 1)
    print("viável!" if not problemas else f"INVIÁVEL: {problemas[:5]}")