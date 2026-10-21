"""Programa principal: roda o construtivo e a busca local e grava os resultados dos experimentos.

Exemplo:
    python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10
"""

import argparse
import csv
import os
import time

import numpy as np

from busca_local import busca_local
from construtivo import construir
from instancia import ler_instancia
from solucao import calcular_custo, calcular_estatisticas, verificar_viabilidade

PASTA_DO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DOS_RESULTADOS = os.path.join(PASTA_DO_PROJETO, "resultados")


def encontrar_instancia(nome):
    """Procura a instância como foi digitada, na pasta instancias/ e ao lado deste arquivo."""
    pasta_deste_arquivo = os.path.dirname(os.path.abspath(__file__))
    for pasta in ["", os.path.join(PASTA_DO_PROJETO, "instancias"), pasta_deste_arquivo]:
        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            return caminho
    raise FileNotFoundError(f"instância não encontrada: {nome}")


def salvar_solucao(caminho, solucao, ids_dos_candidatos, ids_das_escolas):
    """Arquivo de saída: tipo(s) de prova de cada escola e, para cada candidato, escola e sala."""
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("# TIPO(S) DE PROVA DE CADA ESCOLA\n")
        for indice_da_escola, id_da_escola in enumerate(ids_das_escolas):
            tipos = sorted(set(solucao["tipo_da_sala"][indice_da_escola]))
            arquivo.write(f"{id_da_escola}: {', '.join(tipos)}\n")
        arquivo.write("\n# ALOCAÇÃO (candidato, escola, sala, tipo de prova)\n")
        for indice_do_candidato, id_do_candidato in enumerate(ids_dos_candidatos):
            escola = solucao["escola_do_candidato"][indice_do_candidato]
            sala = solucao["sala_do_candidato"][indice_do_candidato]
            tipo = solucao["tipo_da_sala"][escola][sala]
            arquivo.write(f"{id_do_candidato}, {ids_das_escolas[escola]}, {sala + 1}, {tipo}\n")


if __name__ == "__main__":
    leitor_de_argumentos = argparse.ArgumentParser()
    leitor_de_argumentos.add_argument("instancia")
    leitor_de_argumentos.add_argument("--max-tipos", type=int, choices=[1, 2], default=1,
                                      help="máximo de tipos de prova por escola")
    leitor_de_argumentos.add_argument("--execucoes", type=int, default=1,
                                      help="quantas execuções da busca local (uma semente diferente cada)")
    leitor_de_argumentos.add_argument("--semente-inicial", type=int, default=1)
    leitor_de_argumentos.add_argument("--limite-de-tempo", type=float, default=300,
                                      help="segundos máximos de cada busca local")
    argumentos = leitor_de_argumentos.parse_args()

    caminho_da_instancia = encontrar_instancia(argumentos.instancia)
    nome_da_instancia = os.path.splitext(os.path.basename(caminho_da_instancia))[0]
    (ids_dos_candidatos, tipo_de_prova_do_candidato, ids_das_escolas,
     capacidades_das_salas, distancias) = ler_instancia(caminho_da_instancia)

    instante_inicial = time.perf_counter()
    solucao_inicial = construir(tipo_de_prova_do_candidato, capacidades_das_salas, distancias)
    tempo_do_construtivo = time.perf_counter() - instante_inicial
    custo_inicial = calcular_custo(solucao_inicial, distancias)
    print(f"{nome_da_instancia} | máximo de tipos por escola = {argumentos.max_tipos}")
    print(f"solução inicial: {custo_inicial:.2f} km ({tempo_do_construtivo:.2f}s)")

    resultados, melhor_solucao, melhor_custo = [], None, float("inf")
    for execucao in range(argumentos.execucoes):
        semente = argumentos.semente_inicial + execucao
        instante_inicial = time.perf_counter()
        solucao = busca_local(solucao_inicial, tipo_de_prova_do_candidato, capacidades_das_salas,
                              distancias, argumentos.max_tipos, semente, argumentos.limite_de_tempo)
        tempo_da_busca = time.perf_counter() - instante_inicial

        problemas = verificar_viabilidade(solucao, tipo_de_prova_do_candidato, capacidades_das_salas,
                                          argumentos.max_tipos)
        assert not problemas, f"solução inviável: {problemas[:3]}"

        custo_final = calcular_custo(solucao, distancias)
        resultado = {
            "instancia": nome_da_instancia, "max_tipos": argumentos.max_tipos, "semente": semente,
            "custo_inicial": custo_inicial, "custo_final": custo_final,
            "melhoria_percentual": 100 * (custo_inicial - custo_final) / custo_inicial,
            "tempo_construtivo": tempo_do_construtivo, "tempo_busca_local": tempo_da_busca,
            **calcular_estatisticas(solucao, capacidades_das_salas, distancias),
        }
        resultados.append(resultado)
        print(f"semente {semente}: {custo_final:.2f} km (melhoria {resultado['melhoria_percentual']:.1f}%, "
              f"{tempo_da_busca:.1f}s, {resultado['escolas_usadas']} escolas usadas)")
        if custo_final < melhor_custo:
            melhor_solucao, melhor_custo = solucao, custo_final

    if argumentos.execucoes > 1:
        custos = np.array([r["custo_final"] for r in resultados])
        print(f"custo final: média {custos.mean():.2f} | desvio padrão {custos.std():.2f} | "
              f"melhor {custos.min():.2f} | pior {custos.max():.2f}")

    # grava a tabela (acumulando execuções) e a melhor solução encontrada
    os.makedirs(os.path.join(PASTA_DOS_RESULTADOS, "solucoes"), exist_ok=True)
    caminho_da_tabela = os.path.join(PASTA_DOS_RESULTADOS, "tabela_resultados.csv")
    tabela_nova = not os.path.exists(caminho_da_tabela)
    with open(caminho_da_tabela, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(resultados[0]))
        if tabela_nova:
            escritor.writeheader()
        escritor.writerows({chave: round(valor, 4) if isinstance(valor, float) else valor
                            for chave, valor in resultado.items()} for resultado in resultados)
    caminho_da_solucao = os.path.join(PASTA_DOS_RESULTADOS, "solucoes",
                                      f"{nome_da_instancia}_max{argumentos.max_tipos}tipos.txt")
    salvar_solucao(caminho_da_solucao, melhor_solucao, ids_dos_candidatos, ids_das_escolas)
    print(f"melhor solução salva em {caminho_da_solucao}")