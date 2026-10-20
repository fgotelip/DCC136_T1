import numpy as np


def ler_instancia(caminho):
    ids_cand, tipo_cand = [], []
    ids_esc, salas = [], []
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
                ids_cand.append(campos[0])
                tipo_cand.append(campos[2])

            elif secao == "escolas":
                # id, CEP, latitude, longitude, num_salas, capacidades (25;40;50)
                campos = [campo_sujo.strip() for campo_sujo in linha.split(",")]
                ids_esc.append(campos[0])
                salas.append([int(capacidade) for capacidade in campos[5].split(";")])

            elif secao == "matriz":
                distancias.append([float(dist) for dist in linha.split(",")])

    # vira matriz numpy e confere o tamanho esperado (candidatos x escolas)
    distancias = np.array(distancias)
    assert distancias.shape == (len(ids_cand), len(ids_esc)), f"matriz com shape {distancias.shape}"

    return ids_cand, tipo_cand, ids_esc, salas, distancias


# teste básico 
if __name__ == "__main__":
    instancia = input("Digite o nome da instancia desejada presente na raiz do diretório: ")
    ids_cand, tipo_cand, ids_esc, salas, distancias = ler_instancia(instancia)

    print(len(ids_cand), "candidatos,", len(ids_esc), "escolas")

    tipos = sorted(set(tipo_cand))
    print("candidatos por tipo:", {t: tipo_cand.count(t) for t in tipos})

    cap_total = sum(sum(s) for s in salas)
    print("capacidade total:", cap_total, "(folga:", cap_total - len(ids_cand), ")")
    print("salas por escola:", [len(s) for s in salas])
