"""Busca local: melhora a solução inicial sem nunca sair do espaço de soluções viáveis.

Vizinhanças (da mais barata para a mais cara):
  1. realocar: um candidato muda para uma escola mais próxima que ainda tem vaga do tipo dele;
  2. trocar:   dois candidatos do mesmo tipo trocam de escola;
  3. mudar tipos: troca o tipo de salas (máximo 1 tipo por escola: duas escolas trocam de tipo;
                  máximo 2: o tipo de uma sala muda), reorganiza os candidatos afetados
                  e só mantém a mudança se o custo total diminuir.

Detalhes e justificativas: busca_local.md
"""

import random
import time

import numpy as np

from construtivo import alocar_candidatos_do_tipo
from solucao import preencher_salas

TOLERANCIA = 1e-9


def busca_local(solucao, tipo_de_prova_do_candidato, capacidades_das_salas, distancias,
                maximo_de_tipos_por_escola, semente, limite_de_tempo):
    sorteador = random.Random(semente)
    instante_limite = time.perf_counter() + limite_de_tempo

    tipos_de_prova = sorted(set(tipo_de_prova_do_candidato))
    posicao_do_tipo = {tipo: posicao for posicao, tipo in enumerate(tipos_de_prova)}
    tipo_do_candidato = np.array([posicao_do_tipo[tipo] for tipo in tipo_de_prova_do_candidato])
    todos_os_candidatos = np.arange(len(tipo_do_candidato))
    candidatos_de_cada_tipo = [np.where(tipo_do_candidato == posicao)[0]
                               for posicao in range(len(tipos_de_prova))]
    todos_os_tipos = list(range(len(tipos_de_prova)))

    # ---- estado da busca ----
    escola = solucao["escola_do_candidato"].copy()
    tipo_da_sala = [list(tipos) for tipos in solucao["tipo_da_sala"]]
    capacidade = np.zeros((len(capacidades_das_salas), len(tipos_de_prova)), dtype=int)  # [escola][tipo]
    for indice_da_escola, tipos in enumerate(tipo_da_sala):
        for indice_da_sala, tipo in enumerate(tipos):
            capacidade[indice_da_escola, posicao_do_tipo[tipo]] += capacidades_das_salas[indice_da_escola][indice_da_sala]
    ocupacao = np.zeros_like(capacidade)
    np.add.at(ocupacao, (escola, tipo_do_candidato), 1)

    def custo_atual():
        return float(distancias[todos_os_candidatos, escola].sum())

    # ---- vizinhança 1: realocar ----
    def realocar(tipos_considerados):
        melhorou = False
        for tipo in tipos_considerados:
            candidatos = candidatos_de_cada_tipo[tipo]
            escolas_com_vaga = np.where(capacidade[:, tipo] > ocupacao[:, tipo])[0]
            if len(escolas_com_vaga) == 0:
                continue
            # só vale olhar quem tem uma escola com vaga mais perto do que a atual
            melhor_distancia = distancias[np.ix_(candidatos, escolas_com_vaga)].min(axis=1)
            distancia_atual = distancias[candidatos, escola[candidatos]]
            candidatos_que_podem_melhorar = list(candidatos[melhor_distancia < distancia_atual - TOLERANCIA])
            sorteador.shuffle(candidatos_que_podem_melhorar)
            for candidato in candidatos_que_podem_melhorar:
                escolas_com_vaga = np.where(capacidade[:, tipo] > ocupacao[:, tipo])[0]   # as vagas mudam
                nova_escola = escolas_com_vaga[np.argmin(distancias[candidato, escolas_com_vaga])]
                if distancias[candidato, nova_escola] < distancias[candidato, escola[candidato]] - TOLERANCIA:
                    ocupacao[escola[candidato], tipo] -= 1
                    ocupacao[nova_escola, tipo] += 1
                    escola[candidato] = nova_escola
                    melhorou = True
        return melhorou

    # ---- vizinhança 2: trocar dois candidatos do mesmo tipo ----
    def trocar(tipos_considerados):
        melhorou = False
        for tipo in tipos_considerados:
            candidatos = candidatos_de_cada_tipo[tipo]
            while True:
                escolas_dos_candidatos = escola[candidatos]
                distancia_atual = distancias[candidatos, escolas_dos_candidatos]
                # distancia_cruzada[a][b] = distância do candidato a até a escola do candidato b
                distancia_cruzada = distancias[np.ix_(candidatos, escolas_dos_candidatos)]
                ganho = (distancia_atual[:, None] + distancia_atual[None, :]
                         - distancia_cruzada - distancia_cruzada.T)          # ganho de cada par (a, b)
                melhor_par = np.argmax(ganho, axis=1)                    # melhor troca de cada candidato
                melhor_ganho = ganho[np.arange(len(candidatos)), melhor_par]
                ja_trocados = set()
                for primeiro in np.argsort(-melhor_ganho):               # da troca mais vantajosa para a menos
                    segundo = melhor_par[primeiro]
                    if melhor_ganho[primeiro] <= TOLERANCIA:
                        break
                    if primeiro in ja_trocados or segundo in ja_trocados:   # pares disjuntos não interferem
                        continue
                    escola[candidatos[primeiro]], escola[candidatos[segundo]] = (
                        escolas_dos_candidatos[segundo], escolas_dos_candidatos[primeiro])
                    ja_trocados |= {primeiro, segundo}
                if not ja_trocados:
                    break
                melhorou = True
        return melhorou

    # ---- vizinhança 3: mudar o tipo de salas ----
    def listar_mudancas_de_tipo():
        """Cada mudança é uma lista de (escola, sala, tipo_antigo, tipo_novo)."""
        mudancas = []
        if maximo_de_tipos_por_escola == 1:      # duas escolas de tipos diferentes trocam de tipo
            for primeira in range(len(tipo_da_sala)):
                for segunda in range(primeira + 1, len(tipo_da_sala)):
                    tipo_primeira, tipo_segunda = tipo_da_sala[primeira][0], tipo_da_sala[segunda][0]
                    if tipo_primeira != tipo_segunda:
                        mudancas.append(
                            [(primeira, sala, tipo_primeira, tipo_segunda) for sala in range(len(tipo_da_sala[primeira]))]
                            + [(segunda, sala, tipo_segunda, tipo_primeira) for sala in range(len(tipo_da_sala[segunda]))])
        else:                                    # o tipo de uma única sala muda
            for indice_da_escola, tipos in enumerate(tipo_da_sala):
                for indice_da_sala, tipo_antigo in enumerate(tipos):
                    for tipo_novo in tipos_de_prova:
                        if tipo_novo != tipo_antigo:
                            mudancas.append([(indice_da_escola, indice_da_sala, tipo_antigo, tipo_novo)])
        sorteador.shuffle(mudancas)
        return mudancas

    def tentar_mudanca_de_tipo(mudanca):
        """Aplica a mudança, reorganiza os candidatos afetados e desfaz se o custo não diminuir."""
        # a lista foi feita antes: confere se ainda vale e respeita o máximo de tipos por escola
        if any(tipo_da_sala[e][s] != antigo for e, s, antigo, novo in mudanca):
            return False
        tipo_novo_da_sala = {(e, s): novo for e, s, antigo, novo in mudanca}
        for e in {e for e, s, antigo, novo in mudanca}:
            tipos_resultantes = {tipo_novo_da_sala.get((e, s), tipo_da_sala[e][s]) for s in range(len(tipo_da_sala[e]))}
            if len(tipos_resultantes) > maximo_de_tipos_por_escola:
                return False

        custo_antes = custo_atual()
        copia = (escola.copy(), [tipos[:] for tipos in tipo_da_sala], capacidade.copy(), ocupacao.copy())

        def desfazer():
            escola[:] = copia[0]
            tipo_da_sala[:] = copia[1]
            capacidade[:] = copia[2]
            ocupacao[:] = copia[3]
            return False

        tipos_afetados = set()
        for e, s, antigo, novo in mudanca:
            tipo_da_sala[e][s] = novo
            capacidade[e, posicao_do_tipo[antigo]] -= capacidades_das_salas[e][s]
            capacidade[e, posicao_do_tipo[novo]] += capacidades_das_salas[e][s]
            tipos_afetados |= {posicao_do_tipo[antigo], posicao_do_tipo[novo]}

        # viabilidade: a capacidade total de cada tipo ainda precisa cobrir os candidatos dele
        if any(capacidade[:, tipo].sum() < len(candidatos_de_cada_tipo[tipo]) for tipo in tipos_afetados):
            return desfazer()

        # tira de cada escola os candidatos que não cabem mais (os mais distantes dela) e os
        # recoloca com a alocação gulosa do construtivo, usando só as vagas livres...
        for tipo in tipos_afetados:
            desalojados = []
            for e in np.where(ocupacao[:, tipo] > capacidade[:, tipo])[0]:
                excesso = ocupacao[e, tipo] - capacidade[e, tipo]
                ocupantes = candidatos_de_cada_tipo[tipo][escola[candidatos_de_cada_tipo[tipo]] == e]
                desalojados += list(ocupantes[np.argsort(-distancias[ocupantes, e])[:excesso]])
                ocupacao[e, tipo] -= excesso
            if len(desalojados) > 0.25 * len(candidatos_de_cada_tipo[tipo]):   # mudou muito: recomeça o tipo
                desalojados = list(candidatos_de_cada_tipo[tipo])
                ocupacao[:, tipo] = 0
            if desalojados:
                alocar_candidatos_do_tipo(np.array(desalojados), capacidade[:, tipo] - ocupacao[:, tipo],
                                          distancias, escola)
                ocupacao[:, tipo] = np.bincount(escola[candidatos_de_cada_tipo[tipo]], minlength=len(ocupacao))
        # ...e aproveita as vagas novas
        while realocar(tipos_afetados) | trocar(tipos_afetados):
            pass

        return True if custo_atual() < custo_antes - TOLERANCIA else desfazer()

    # ---- laço principal: vizinhanças baratas até travar; depois a vizinhança de tipos ----
    while time.perf_counter() < instante_limite:
        while realocar(todos_os_tipos) | trocar(todos_os_tipos):
            pass
        mudou_algum_tipo = False
        for mudanca in listar_mudancas_de_tipo():
            if time.perf_counter() >= instante_limite:
                break
            mudou_algum_tipo |= tentar_mudanca_de_tipo(mudanca)
        if not mudou_algum_tipo:
            break

    return {
        "tipo_da_sala": tipo_da_sala,
        "escola_do_candidato": escola,
        "sala_do_candidato": preencher_salas(escola, tipo_da_sala, capacidades_das_salas,
                                             tipo_de_prova_do_candidato),
    }