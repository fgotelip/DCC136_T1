import numpy as np
import os

def ler_instancia(caminho):
    ids_candidatos, tipo_prova_candidato = [], []
    ids_escolas, capacidade_salas = [], []
    distancias = []

    secao = None  # em qual parte do arquivo estamos
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue

            # linhas que começam com '#' marcam o início de uma seção
            if linha.startswith("#"):
                if "CANDIDATOS" in linha:
                    secao = "candidatos"
                elif "ESCOLAS" in linha:
                    secao = "escolas"
                elif "MATRIZ" in linha:
                    secao = "matriz"
                continue

            if secao == "candidatos":
                # id, CEP, tipo_prova, latitude, longitude
                campos = [campo_sujo.strip() for campo_sujo in linha.split(",")]
                ids_candidatos.append(campos[0])
                tipo_prova_candidato.append(campos[2])

            elif secao == "escolas":
                # id, CEP, latitude, longitude, num_capacidade_salas, capacidades (25;40;50)
                campos = [campo_sujo.strip() for campo_sujo in linha.split(",")]
                ids_escolas.append(campos[0])
                capacidade_salas.append([int(capacidade) for capacidade in campos[5].split(";")])

            elif secao == "matriz":
                distancias.append([float(dist) for dist in linha.split(",")])

    # vira matriz numpy e confere o tamanho esperado (candidatos x escolas)
    distancias = np.array(distancias)
    assert distancias.shape == (len(ids_candidatos), len(ids_escolas)), f"matriz com shape {distancias.shape}"

    return ids_candidatos, tipo_prova_candidato, ids_escolas, capacidade_salas, distancias


# teste básico 
if __name__ == "__main__":
    import sys
    ids_candidatos, tipo_prova_candidato, ids_escolas, capacidade_salas, distancias = ler_instancia(sys.argv[1])

    print(len(ids_candidatos), "candidatos,", len(ids_escolas), "escolas")

    tipos = sorted(set(tipo_prova_candidato))
    print("candidatos por tipo de prova:", {tipo: tipo_prova_candidato.count(tipo) for tipo in tipos})

    cap_total = sum(sum(sala) for sala in capacidade_salas)
    print("capacidade total:", cap_total, "(folga:", cap_total - len(ids_candidatos), ")")
    print("quantidade de salas por escola:", [len(s) for s in capacidade_salas])