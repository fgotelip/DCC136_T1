"""Programa principal: roda o construtivo e a busca local e grava os resultados dos experimentos.

Duas formas de uso:

    # uma instância (acumula em resultados/tabela_resultados.csv)
    python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10

    # lote: todas as instâncias de um zip, em paralelo (tudo em resultados_lote/)
    python main.py --zip ../drive-download.zip --jobs 4

Veja o README.md para a descrição completa dos parâmetros e das saídas.
"""

import argparse
import csv
import glob
import os
import re
import shutil
import statistics
import sys
import time
import traceback
import zipfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import construtivo
from busca_local import busca_local
from construtivo import construir
from instancia import ler_instancia
from solucao import calcular_custo, calcular_estatisticas, verificar_viabilidade

PASTA_DO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DOS_RESULTADOS = os.path.join(PASTA_DO_PROJETO, "resultados")
PASTA_DO_LOTE = os.path.join(PASTA_DO_PROJETO, "resultados_lote")

# colunas de cada execução (as mesmas da tabela_resultados.csv e dos csv individuais do lote)
CAMPOS = ["instancia", "max_tipos", "semente", "custo_inicial", "custo_final", "melhoria_percentual",
          "tempo_construtivo", "tempo_busca_local", "escolas_usadas", "ocupacao_minima", "ocupacao_media",
          "ocupacao_maxima", "distancia_media", "distancia_maxima"]
CAMPOS_DA_FALHA = ["instancia", "max_tipos", "erro"]    # csv individual de uma (instância, K) que falhou

# média das métricas por (instância, K): vão depois das 3 colunas de colar na planilha
METRICAS_MEDIAS = ["melhoria_percentual", "tempo_busca_local", "escolas_usadas", "ocupacao_minima",
                   "ocupacao_media", "ocupacao_maxima", "distancia_media", "distancia_maxima"]
CAMPOS_DA_PLANILHA = (["instancia", "melhor_resultado", "media_dos_resultados", "tempo_medio_s",
                       "pior_resultado", "desvio_padrao", "custo_inicial", "tempo_construtivo"]
                      + [f"media_{m}" for m in METRICAS_MEDIAS] + ["execucoes"])

LIMITE_DE_NOS_DO_LOTE = 5_000_000
GRUPOS_DA_PLANILHA = range(1, 15)    # linhas da planilha: Instancia1_G1..G14 e Instancia2_G1..G14
PADRAO_DO_NOME = re.compile(r"instancia_?([12])_?g(\d+)", re.IGNORECASE)


class SolucaoInviavel(Exception):
    pass


# ---------------------------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------------------------

def registrar(pasta_do_log, mensagem):
    """Mostra na tela e, no lote, acrescenta em progresso.log (com horário)."""
    linha = f"[{time.strftime('%H:%M:%S')}] {mensagem}\n"
    print(linha, end="", flush=True)
    if pasta_do_log:
        try:
            with open(os.path.join(pasta_do_log, "progresso.log"), "a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
        except OSError:
            pass


def registrar_falha(pasta_do_log, nome, k, etapa, erro, contexto):
    """Detalhe completo de uma falha (etapa, erro, contexto da instância e traceback) em falhas.log."""
    cabecalho = f"{nome} K={k}" if k else nome
    texto = [f"===== [{time.strftime('%Y-%m-%d %H:%M:%S')}] {cabecalho} =====",
             f"etapa   : {etapa}",
             f"erro    : {type(erro).__name__}: {erro}"]
    texto += [f"contexto: {linha}" for linha in contexto]
    texto += ["traceback:", "".join(traceback.format_exception(type(erro), erro, erro.__traceback__)), ""]
    texto = "\n".join(texto)
    if pasta_do_log:
        try:
            with open(os.path.join(pasta_do_log, "falhas.log"), "a", encoding="utf-8") as arquivo:
                arquivo.write(texto + "\n")
        except OSError:
            pass
    else:
        print(texto, file=sys.stderr, flush=True)


def descrever_erro(etapa, erro):
    """Mensagem curta (uma linha) para o progresso.log e para as colunas da planilha."""
    texto = " ".join(str(erro).split())
    return f"FALHA em {etapa}: {type(erro).__name__}: {texto}"


def descrever_contexto(caminho, tipos, capacidades_das_salas, ids_dos_candidatos, ids_das_escolas):
    """Números da instância que ajudam a entender por que ela falhou."""
    demanda = Counter(tipos)
    capacidade_total = sum(sum(salas) for salas in capacidades_das_salas)
    return [f"arquivo {os.path.basename(caminho)} ({os.path.getsize(caminho) / 1024:.0f} KB)",
            f"{len(ids_dos_candidatos)} candidatos, {len(ids_das_escolas)} escolas, "
            f"capacidade total das salas = {capacidade_total}",
            "candidatos por tipo de prova: " + ", ".join(f"{t}={q}" for t, q in sorted(demanda.items()))]


# ---------------------------------------------------------------------------------------------
# núcleo: uma instância, para um ou mais valores de K
# ---------------------------------------------------------------------------------------------

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


def processar_instancia(caminho, maximos, execucoes, semente_inicial, limite_de_tempo, limite_de_nos,
                        pasta_das_solucoes, pasta_do_log):
    """Lê, constrói a solução inicial e roda a busca local para cada K.

    Devolve {k: (linhas, None)} se deu certo ou {k: (None, mensagem_de_erro)} se falhou. Nunca levanta
    exceção por problema da instância: a falha é registrada (progresso.log e falhas.log) e devolvida.
    """
    nome = os.path.splitext(os.path.basename(caminho))[0]
    if limite_de_nos:
        construtivo.LIMITE_DE_NOS_DA_BUSCA = limite_de_nos
    registrar(pasta_do_log, f"Iniciando {nome} (arquivo: {os.path.basename(caminho)})")
    contexto, etapa = [f"arquivo {os.path.basename(caminho)}"], "leitura da instância"
    try:
        (ids_dos_candidatos, tipo_de_prova_do_candidato, ids_das_escolas,
         capacidades_das_salas, distancias) = ler_instancia(caminho)
        contexto = descrever_contexto(caminho, tipo_de_prova_do_candidato, capacidades_das_salas,
                                      ids_dos_candidatos, ids_das_escolas)
        etapa = "construtivo"
        instante_inicial = time.perf_counter()
        solucao_inicial = construir(tipo_de_prova_do_candidato, capacidades_das_salas, distancias)
        tempo_do_construtivo = time.perf_counter() - instante_inicial
        custo_inicial = calcular_custo(solucao_inicial, distancias)
        registrar(pasta_do_log, f"{nome}: construtivo concluído em {tempo_do_construtivo:.2f}s | "
                                f"custo inicial = {custo_inicial:.2f} km")
    except Exception as erro:
        registrar(pasta_do_log, f"{nome}: {descrever_erro(etapa, erro)} (detalhes em falhas.log)")
        registrar_falha(pasta_do_log, nome, None, etapa, erro, contexto)
        return {k: (None, descrever_erro(etapa, erro)) for k in maximos}

    resultado = {}
    for k in maximos:
        linhas, melhor_solucao, melhor_custo = [], None, float("inf")
        etapa = "busca local"
        try:
            for semente in range(semente_inicial, semente_inicial + execucoes):
                etapa = f"busca local (semente {semente})"
                instante_inicial = time.perf_counter()
                solucao = busca_local(solucao_inicial, tipo_de_prova_do_candidato, capacidades_das_salas,
                                      distancias, k, semente, limite_de_tempo)
                tempo_da_busca = time.perf_counter() - instante_inicial

                etapa = f"verificação de viabilidade (semente {semente})"
                problemas = verificar_viabilidade(solucao, tipo_de_prova_do_candidato,
                                                  capacidades_das_salas, k)
                if problemas:
                    raise SolucaoInviavel(f"{len(problemas)} violações, primeiras: {problemas[:3]}")

                etapa = f"estatísticas (semente {semente})"
                custo_final = calcular_custo(solucao, distancias)
                linha = {"instancia": nome, "max_tipos": k, "semente": semente,
                         "custo_inicial": custo_inicial, "custo_final": custo_final,
                         "melhoria_percentual": 100 * (custo_inicial - custo_final) / custo_inicial,
                         "tempo_construtivo": tempo_do_construtivo, "tempo_busca_local": tempo_da_busca,
                         **calcular_estatisticas(solucao, capacidades_das_salas, distancias)}
                linhas.append(linha)
                registrar(pasta_do_log, f"{nome} (K={k}) | semente {semente:2d}: custo = {custo_final:10.2f} km | "
                                        f"melhoria {linha['melhoria_percentual']:4.1f}% | "
                                        f"{linha['escolas_usadas']} escolas | tempo = {tempo_da_busca:6.1f}s")
                if custo_final < melhor_custo:
                    melhor_solucao, melhor_custo = solucao, custo_final

            etapa = "gravação da melhor solução"
            os.makedirs(pasta_das_solucoes, exist_ok=True)
            salvar_solucao(os.path.join(pasta_das_solucoes, f"{nome}_max{k}tipos.txt"), melhor_solucao,
                           ids_dos_candidatos, ids_das_escolas)
            resultado[k] = (linhas, None)
        except Exception as erro:
            registrar(pasta_do_log, f"{nome} (K={k}): {descrever_erro(etapa, erro)} (detalhes em falhas.log)")
            registrar_falha(pasta_do_log, nome, k, etapa, erro, contexto)
            resultado[k] = (None, descrever_erro(etapa, erro))
    return resultado


def arredondar(linha):
    return {chave: round(valor, 4) if isinstance(valor, float) else valor for chave, valor in linha.items()}


def gravar_csv(caminho, campos, linhas, modo="w"):
    novo = modo == "w" or not os.path.exists(caminho)
    with open(caminho, modo, newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        if novo:
            escritor.writeheader()
        escritor.writerows(arredondar(linha) for linha in linhas)


def resumo_do_k(linhas):
    return (f"melhor {min(l['custo_final'] for l in linhas):.2f} | "
            f"média {statistics.mean(l['custo_final'] for l in linhas):.2f} | "
            f"tempo médio {statistics.mean(l['tempo_construtivo'] + l['tempo_busca_local'] for l in linhas):.2f}s")


# ---------------------------------------------------------------------------------------------
# modo instância única
# ---------------------------------------------------------------------------------------------

def modo_instancia(a):
    caminho = encontrar_instancia(a.instancia)
    maximos = a.max_tipos or [1]
    resultado = processar_instancia(caminho, maximos, a.execucoes or 1, a.semente_inicial,
                                    a.limite_de_tempo, a.limite_nos, os.path.join(PASTA_DOS_RESULTADOS, "solucoes"),
                                    None)
    os.makedirs(PASTA_DOS_RESULTADOS, exist_ok=True)
    falhou = False
    for k, (linhas, erro) in resultado.items():
        if erro:
            falhou = True
            continue
        print(f"K={k}: {resumo_do_k(linhas)}")
        gravar_csv(os.path.join(PASTA_DOS_RESULTADOS, "tabela_resultados.csv"), CAMPOS, linhas, modo="a")
        print(f"melhor solução salva em {os.path.join(PASTA_DOS_RESULTADOS, 'solucoes')}")
    sys.exit(1 if falhou else 0)


# ---------------------------------------------------------------------------------------------
# modo lote
# ---------------------------------------------------------------------------------------------

def chave_da_instancia(nome):
    """Instancia1_G7(1).txt -> (1, 7); None se o nome não parece uma instância."""
    achou = PADRAO_DO_NOME.search(nome.replace("(1)", ""))
    return (int(achou.group(1)), int(achou.group(2))) if achou else None


def extrair(caminho_do_zip, pasta):
    """Extrai o zip (e zips dentro dele) de forma plana para a pasta."""
    os.makedirs(pasta, exist_ok=True)
    fila = [caminho_do_zip]
    while fila:
        with zipfile.ZipFile(fila.pop()) as arquivo_zip:
            for info in arquivo_zip.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                destino = os.path.join(pasta, os.path.basename(info.filename))
                with arquivo_zip.open(info) as origem, open(destino, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
                if destino.lower().endswith(".zip"):
                    fila.append(destino)


def achar_arquivos(pasta):
    """Um arquivo por (tipo, grupo); se houver repetidos fica o maior (ignora arquivos quebrados)."""
    arquivos = {}
    for caminho in glob.glob(os.path.join(pasta, "*.txt")):
        chave = chave_da_instancia(os.path.basename(caminho))
        if chave and (chave not in arquivos or os.path.getsize(caminho) > os.path.getsize(arquivos[chave])):
            arquivos[chave] = caminho
    return arquivos


def ler_csv_individual(caminho):
    """Devolve ('ok', linhas) | ('falha', mensagem) | ('invalido', motivo) para um csv do lote."""
    try:
        with open(caminho, newline="", encoding="utf-8") as arquivo:
            leitor = csv.DictReader(arquivo)
            campos, linhas = leitor.fieldnames, list(leitor)
    except (OSError, UnicodeDecodeError, csv.Error) as erro:
        return "invalido", f"não foi possível ler ({erro})"
    if campos == CAMPOS_DA_FALHA and linhas:
        return "falha", linhas[0]["erro"]
    if campos == CAMPOS and linhas:
        return "ok", linhas
    return "invalido", "colunas diferentes do escopo atual (csv de uma versão antiga ou vazio)"


def tarefa_do_lote(argumentos):
    """Roda uma instância (todos os K pedidos) e grava um csv por K. Executada em processos paralelos."""
    (nome, caminho, maximos, execucoes, semente_inicial, limite_de_tempo, limite_de_nos,
     pasta_do_lote, pasta_das_solucoes, pasta_do_log) = argumentos
    resultado = processar_instancia(caminho, maximos, execucoes, semente_inicial, limite_de_tempo,
                                    limite_de_nos, pasta_das_solucoes, pasta_do_log)
    for k, (linhas, erro) in resultado.items():
        caminho_do_csv = os.path.join(pasta_do_lote, f"{nome}_K{k}.csv")
        if erro:
            gravar_csv(caminho_do_csv, CAMPOS_DA_FALHA, [{"instancia": nome, "max_tipos": k, "erro": erro}])
            registrar(pasta_do_log, f"{nome} K={k} SEM RESULTADO: {erro}")
        else:
            gravar_csv(caminho_do_csv, CAMPOS, linhas)
            registrar(pasta_do_log, f"{nome} K={k} FINALIZADA: {resumo_do_k(linhas)}")
    return nome


def juntar_resultados(pasta_do_lote, pasta_de_saida, maximos, nomes_esperados):
    """Junta os csv individuais: resultados_completos.csv (linha por execução) e planilha_K<k>.csv."""
    por_k = {}    # {k: {nome: ('ok', linhas) | ('falha', mensagem)}}
    for caminho in sorted(glob.glob(os.path.join(pasta_do_lote, "*.csv"))):
        nome, k = os.path.basename(caminho)[:-4].rsplit("_K", 1)
        situacao, conteudo = ler_csv_individual(caminho)
        if situacao != "invalido":
            por_k.setdefault(int(k), {})[nome] = (situacao, conteudo)

    def ordem(nome):
        return chave_da_instancia(nome) or (99, 0)

    todas = [linha for k in sorted(por_k) for nome in sorted(por_k[k], key=ordem)
             if por_k[k][nome][0] == "ok" for linha in por_k[k][nome][1]]
    gravar_csv(os.path.join(pasta_de_saida, "resultados_completos.csv"), CAMPOS, todas)

    linhas_da_planilha = [f"Instancia{t}_G{g}" for t in (1, 2) for g in GRUPOS_DA_PLANILHA]
    for k in maximos:
        resultados = por_k.get(k, {})
        nomes = linhas_da_planilha + sorted(set(resultados) - set(linhas_da_planilha), key=ordem)
        saida = []
        for nome in nomes:
            situacao, conteudo = resultados.get(nome, ("falha", "NAO EXECUTADA (sem arquivo da instancia no zip)"))
            if situacao == "falha":
                saida.append({"instancia": nome, "melhor_resultado": conteudo,
                              "media_dos_resultados": conteudo, "tempo_medio_s": conteudo})
                continue
            custos = [float(l["custo_final"]) for l in conteudo]
            tempos = [float(l["tempo_construtivo"]) + float(l["tempo_busca_local"]) for l in conteudo]
            linha = {"instancia": nome, "melhor_resultado": min(custos),
                     "media_dos_resultados": statistics.mean(custos), "tempo_medio_s": statistics.mean(tempos),
                     "pior_resultado": max(custos),
                     "desvio_padrao": statistics.pstdev(custos),
                     "custo_inicial": float(conteudo[0]["custo_inicial"]),
                     "tempo_construtivo": float(conteudo[0]["tempo_construtivo"]),
                     "execucoes": len(conteudo)}
            for metrica in METRICAS_MEDIAS:
                linha[f"media_{metrica}"] = statistics.mean(float(l[metrica]) for l in conteudo)
            saida.append(linha)
        gravar_csv(os.path.join(pasta_de_saida, f"planilha_K{k}.csv"), CAMPOS_DA_PLANILHA, saida)
    return por_k


def modo_lote(a):
    pasta_de_saida = os.path.abspath(a.saida)
    pasta_das_instancias = os.path.join(pasta_de_saida, "instancias")
    pasta_do_lote = os.path.join(pasta_de_saida, "lote")
    caminho_do_zip = os.path.join(pasta_de_saida, "lote.zip")
    pasta_das_solucoes = os.path.join(pasta_de_saida, "solucoes")
    maximos = a.max_tipos or [1, 2]
    execucoes = a.execucoes or 10
    limite_de_nos = a.limite_nos or LIMITE_DE_NOS_DO_LOTE
    os.makedirs(pasta_do_lote, exist_ok=True)
    log = pasta_de_saida

    if not os.path.isdir(pasta_das_instancias):
        extrair(a.zip, pasta_das_instancias)

    # retomada: restaura no lote/ os csv do zip da rodada anterior (sem sobrescrever o que já está lá)
    if os.path.exists(caminho_do_zip):
        with zipfile.ZipFile(caminho_do_zip) as arquivo_zip:
            for nome_no_zip in arquivo_zip.namelist():
                destino = os.path.join(pasta_do_lote, os.path.basename(nome_no_zip))
                if nome_no_zip.lower().endswith(".csv") and not os.path.exists(destino):
                    with arquivo_zip.open(nome_no_zip) as origem, open(destino, "wb") as saida:
                        shutil.copyfileobj(origem, saida)
        registrar(log, f"retomada: csv de {os.path.basename(caminho_do_zip)} restaurados")

    arquivos = achar_arquivos(pasta_das_instancias)
    tarefas, nomes_esperados = [], []
    for (tipo, grupo), caminho in sorted(arquivos.items()):
        nome = f"Instancia{tipo}_G{grupo}"
        if a.so_instancias and nome not in a.so_instancias:
            continue
        nomes_esperados.append(nome)
        faltam = []
        for k in maximos:
            caminho_do_csv = os.path.join(pasta_do_lote, f"{nome}_K{k}.csv")
            if os.path.exists(caminho_do_csv):
                situacao, detalhe = ler_csv_individual(caminho_do_csv)
                if situacao == "ok" or (situacao == "falha" and not a.refazer_falhas):
                    continue
                motivo = detalhe if situacao == "invalido" else "refazendo falha anterior"
                registrar(log, f"{nome} K={k}: csv existente descartado ({motivo})")
                os.remove(caminho_do_csv)
            faltam.append(k)
        print(f"{nome:16} <- {os.path.basename(caminho)}" + ("" if faltam else "  (já calculada)"))
        if faltam:
            tarefas.append((nome, caminho, faltam, execucoes, a.semente_inicial, a.limite_de_tempo,
                            limite_de_nos, pasta_do_lote, pasta_das_solucoes, log))

    registrar(log, f"lote: {len(tarefas)} instância(s) para rodar, {a.jobs} em paralelo")
    if a.jobs > 1 and len(tarefas) > 1:
        with ProcessPoolExecutor(a.jobs) as pool:
            futuros = {pool.submit(tarefa_do_lote, t): t[0] for t in tarefas}
            for futuro in as_completed(futuros):
                try:
                    futuro.result()
                except Exception as erro:    # o processo inteiro caiu (memória, kill...): o csv não foi gravado
                    registrar(log, f"{futuros[futuro]}: PROCESSO DO LOTE CAIU ({type(erro).__name__}: {erro})")
                    registrar_falha(log, futuros[futuro], None, "processo do lote", erro, [])
    else:
        for tarefa in tarefas:
            tarefa_do_lote(tarefa)

    por_k = juntar_resultados(pasta_do_lote, pasta_de_saida, maximos, nomes_esperados)

    # zip com os csv individuais; a pasta só é apagada depois do zip pronto
    zip_temporario = caminho_do_zip + ".tmp"
    with zipfile.ZipFile(zip_temporario, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        for caminho in sorted(glob.glob(os.path.join(pasta_do_lote, "*.csv"))):
            arquivo_zip.write(caminho, os.path.basename(caminho))
    os.replace(zip_temporario, caminho_do_zip)
    shutil.rmtree(pasta_do_lote)

    falhas = [(nome, k, dado[1]) for k in sorted(por_k) for nome, dado in sorted(por_k[k].items())
              if dado[0] == "falha"]
    registrar(log, f"lote concluído: {sum(1 for k in por_k for d in por_k[k].values() if d[0] == 'ok')} "
                   f"(instância, K) com resultado, {len(falhas)} sem resultado")
    for nome, k, mensagem in falhas:
        registrar(log, f"SEM RESULTADO {nome} K={k}: {mensagem}")
    if falhas:
        registrar(log, "detalhes e traceback de cada falha em falhas.log")
    print(f"arquivos em {pasta_de_saida}: resultados_completos.csv, "
          + ", ".join(f"planilha_K{k}.csv" for k in maximos) + ", lote.zip")


if __name__ == "__main__":
    leitor_de_argumentos = argparse.ArgumentParser(
        description="Instância única: python main.py Instancia1_G4.txt | Lote: python main.py --zip arquivo.zip")
    leitor_de_argumentos.add_argument("instancia", nargs="?", help="arquivo de uma instância (modo instância única)")
    leitor_de_argumentos.add_argument("--zip", help="zip com as instâncias (liga o modo lote)")
    leitor_de_argumentos.add_argument("--max-tipos", type=int, nargs="+", choices=[1, 2],
                                      help="máximo(s) de tipos de prova por escola (padrão: 1 na instância única, 1 2 no lote)")
    leitor_de_argumentos.add_argument("--execucoes", type=int,
                                      help="execuções da busca local, uma semente diferente cada "
                                           "(padrão: 1 na instância única, 10 no lote)")
    leitor_de_argumentos.add_argument("--semente-inicial", type=int, default=1)
    leitor_de_argumentos.add_argument("--limite-de-tempo", type=float, default=300,
                                      help="segundos máximos de cada busca local")
    leitor_de_argumentos.add_argument("--limite-nos", type=int,
                                      help=f"limite do backtracking do construtivo (padrão: o do construtivo; "
                                           f"{LIMITE_DE_NOS_DO_LOTE:,} no lote)")
    leitor_de_argumentos.add_argument("--jobs", type=int, default=1,
                                      help="lote: instâncias em paralelo (>1 distorce os tempos)")
    leitor_de_argumentos.add_argument("--saida", default=PASTA_DO_LOTE, help="lote: pasta de saída")
    leitor_de_argumentos.add_argument("--so-instancias", nargs="*",
                                      help="lote: rodar só estas, ex: Instancia1_G4 Instancia2_G4")
    leitor_de_argumentos.add_argument("--refazer-falhas", action="store_true",
                                      help="lote: tenta de novo as (instância, K) que falharam na rodada anterior")
    argumentos = leitor_de_argumentos.parse_args()

    if argumentos.zip:
        modo_lote(argumentos)
    elif argumentos.instancia:
        modo_instancia(argumentos)
    else:
        leitor_de_argumentos.error("informe uma instância ou --zip")
