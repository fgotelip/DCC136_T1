"""Representação da solução, custo e verificação de viabilidade.

Uma solução é um dicionário com 3 partes:

    solucao["tipo_da_sala"][indice_da_escola][indice_da_sala]  -> tipo de prova da sala
    solucao["escola_do_candidato"][indice_do_candidato]        -> escola do candidato
    solucao["sala_do_candidato"][indice_do_candidato]          -> sala do candidato (dentro da escola)
"""

import numpy as np


def calcular_custo(solucao, distancias):
    """Distância total (km) entre cada candidato e a escola onde ele foi alocado."""
    indices_dos_candidatos = np.arange(len(solucao["escola_do_candidato"]))
    return float(distancias[indices_dos_candidatos, solucao["escola_do_candidato"]].sum())


def verificar_viabilidade(solucao, tipo_de_prova_do_candidato, capacidades_das_salas,
                          maximo_de_tipos_por_escola):
    """Devolve a lista de restrições violadas (lista vazia = solução viável)."""
    problemas = []
    tipo_da_sala = solucao["tipo_da_sala"]
    ocupacao_das_salas = {}

    for indice_da_escola, tipos_das_salas in enumerate(tipo_da_sala):
        if len(set(tipos_das_salas)) > maximo_de_tipos_por_escola:
            problemas.append(f"escola {indice_da_escola} usa mais de {maximo_de_tipos_por_escola} tipos")

    for indice_do_candidato, tipo in enumerate(tipo_de_prova_do_candidato):
        escola = solucao["escola_do_candidato"][indice_do_candidato]
        sala = solucao["sala_do_candidato"][indice_do_candidato]
        if tipo_da_sala[escola][sala] != tipo:
            problemas.append(f"candidato {indice_do_candidato}: tipo de prova diferente do da sala")
        ocupacao_das_salas[(escola, sala)] = ocupacao_das_salas.get((escola, sala), 0) + 1

    for (escola, sala), quantidade in ocupacao_das_salas.items():
        if quantidade > capacidades_das_salas[escola][sala]:
            problemas.append(f"escola {escola} sala {sala}: acima da capacidade")

    return problemas


def montar_resumo(solucao, ids_das_escolas, capacidades_das_salas, distancias):
    custo_total = calcular_custo(solucao, distancias)
    linhas = [f"custo total = {custo_total:.2f} km"]
    for indice_da_escola, id_da_escola in enumerate(ids_das_escolas):
        quantidade = int((solucao["escola_do_candidato"] == indice_da_escola).sum())
        tipos = ",".join(sorted(set(solucao["tipo_da_sala"][indice_da_escola])))
        linhas.append(f"  {id_da_escola:>4}: tipo={tipos:<5} candidatos={quantidade:>4} "
                      f"/ capacidade={sum(capacidades_das_salas[indice_da_escola]):>4}")
    return "\n".join(linhas)


def preencher_salas(escola_do_candidato, tipo_da_sala, capacidades_das_salas, tipo_de_prova_do_candidato):
    """Dentro de cada escola, os candidatos de cada tipo vão enchendo as salas daquele tipo, uma por vez."""
    sala_do_candidato = np.full(len(escola_do_candidato), -1)
    tipos_como_vetor = np.array(tipo_de_prova_do_candidato)
    for escola, capacidades in enumerate(capacidades_das_salas):
        for tipo in set(tipo_da_sala[escola]):
            candidatos = np.where((escola_do_candidato == escola) & (tipos_como_vetor == tipo))[0]
            inicio = 0
            for sala, capacidade in enumerate(capacidades):
                if tipo_da_sala[escola][sala] == tipo:
                    sala_do_candidato[candidatos[inicio:inicio + capacidade]] = sala
                    inicio += capacidade
    return sala_do_candidato


def calcular_estatisticas(solucao, capacidades_das_salas, distancias):
    """Números que descrevem a solução (para a tabela de experimentos)."""
    escola_do_candidato = solucao["escola_do_candidato"]
    candidatos_por_escola = np.bincount(escola_do_candidato, minlength=len(capacidades_das_salas))
    capacidade_por_escola = np.array([sum(capacidades) for capacidades in capacidades_das_salas])
    escolas_usadas = candidatos_por_escola > 0
    ocupacao = candidatos_por_escola[escolas_usadas] / capacidade_por_escola[escolas_usadas]
    distancia_por_candidato = distancias[np.arange(len(escola_do_candidato)), escola_do_candidato]
    return {
        "escolas_usadas": int(escolas_usadas.sum()),
        "ocupacao_minima": float(ocupacao.min()),
        "ocupacao_media": float(ocupacao.mean()),
        "ocupacao_maxima": float(ocupacao.max()),
        "distancia_media": float(distancia_por_candidato.mean()),
        "distancia_maxima": float(distancia_por_candidato.max()),
    }