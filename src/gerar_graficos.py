"""Gera os gráficos baseados em características das instâncias e a tabela de resultados.

Entrada : resultados_lote/resultados_completos.csv (+ planilha_K1.csv para falhas)
          e os arquivos de instância (cabeçalho/escolas).
Saída   : resultados_lote/figuras/*.pdf, resultados_lote/tabela_resultados.tex e
          resultados_lote/figuras/resumo_estatisticas.txt.

Uso: python src/gerar_graficos.py
"""
import os
import re
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl_cfg"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJETO = Path(__file__).resolve().parent.parent          # DCC136_T1/
LOTE = PROJETO / "resultados_lote"
RAIZ = LOTE                                               # saída única: resultados_lote/
PASTA_FIG = RAIZ / "figuras"
CACHE_INFO = PASTA_FIG / "info_instancias.csv"
PASTA_FIG.mkdir(parents=True, exist_ok=True)

COR = {1: "#3470a3", 2: "#d95f02"}
COR_G4 = "#b2182b"
GRUPO_ALVO = "G4"
LIMITE_TEMPO = 300

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8.5,
    "legend.fontsize": 7.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "pdf.fonttype": 42,
})

MOTIVO_FALHA = {
    "Instancia1_G2": r"$|L|=5$ escolas para $|T|=6$ tipos de prova",
    "Instancia2_G2": r"$|L|=5$ escolas para $|T|=6$ tipos de prova",
    "Instancia2_G3": r"cada tipo exige $\ge 2$ escolas: $6 \times 2 = 12 > 10$",
    "Instancia2_G5": r"4 tipos exigem $\ge 3$ escolas cada: $16 > 15$",
    "Instancia2_G7": r"98,0\% de ocupação e forte assimetria de demanda",
}


def normaliza_nome(nome):
    m = re.search(r"instancia_?(\d)_G(\d+)", str(nome), flags=re.I)
    return f"Instancia{m.group(1)}_G{m.group(2)}" if m else None


def rotulo(inst):
    m = re.match(r"Instancia(\d)_G(\d+)", inst)
    return f"I{m.group(1)}-G{m.group(2)}"


def grupo(inst):
    return inst.split("_")[-1]


def num(x, casas=2):
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def inteiro(x):
    return num(x, 0)


def info_instancia(caminho):
    n_cand = n_esc = salas = cap = 0
    secao = None
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            if linha.startswith("#"):
                if "MATRIZ" in linha:
                    break
                secao = "cand" if "CANDIDATOS" in linha else "esc" if "ESCOLAS" in linha else secao
                continue
            if secao == "cand":
                n_cand += 1
            elif secao == "esc":
                caps = [int(c) for c in linha.split(",")[5].split(";")]
                n_esc += 1
                salas += len(caps)
                cap += sum(caps)
    return dict(candidatos=n_cand, n_escolas=n_esc, salas=salas, capacidade=cap)


def carrega_info(instancias):
    if CACHE_INFO.exists():
        info = pd.read_csv(CACHE_INFO).set_index("inst")
        if set(instancias) <= set(info.index):
            return info
    arquivos = {}
    for p in (LOTE / "instancias").glob("*.txt"):
        nome = normaliza_nome(p.name)
        if nome and (nome not in arquivos or p.stat().st_size > arquivos[nome].stat().st_size):
            arquivos[nome] = p
    linhas = []
    for inst in instancias:
        d = info_instancia(arquivos[inst])
        d["inst"] = inst
        linhas.append(d)
    info = pd.DataFrame(linhas)
    info.to_csv(CACHE_INFO, index=False)
    return info.set_index("inst")


def carrega_dados():
    bruto = pd.read_csv(LOTE / "resultados_completos.csv")
    bruto["inst"] = bruto["instancia"].map(normaliza_nome)
    bruto["K"] = bruto["max_tipos"]
    bruto["razao"] = 100 * bruto["custo_final"] / bruto["custo_inicial"]

    plan = pd.read_csv(LOTE / "planilha_K1.csv", encoding_errors="replace")
    plan["inst"] = plan["instancia"].map(normaliza_nome)
    falhas = sorted(plan.loc[plan["melhor_resultado"].astype(str).str.startswith("FALHA"), "inst"])
    todas = sorted(plan["inst"], key=ordem_natural)

    info = carrega_info(todas)

    g = bruto.groupby(["inst", "K"])
    agg = g.agg(
        inicial=("custo_inicial", "first"),
        melhor=("custo_final", "min"),
        media=("custo_final", "mean"),
        pior=("custo_final", "max"),
        dp=("custo_final", lambda s: s.std(ddof=0)),
        melh=("melhoria_percentual", "mean"),
        melh_dp=("melhoria_percentual", lambda s: s.std(ddof=0)),
        t_constr=("tempo_construtivo", "mean"),
        t_busca=("tempo_busca_local", "mean"),
        n_lim=("tempo_busca_local", lambda s: int((s >= LIMITE_TEMPO - 1).sum())),
        escolas=("escolas_usadas", "mean"),
        ocup_min=("ocupacao_minima", "mean"),
        ocup_med=("ocupacao_media", "mean"),
        ocup_max=("ocupacao_maxima", "mean"),
        dist_med=("distancia_media", "mean"),
        dist_max=("distancia_maxima", "mean"),
        n=("semente", "count"),
    ).reset_index()
    agg = agg.join(info, on="inst")
    agg["ocup_global"] = agg["candidatos"] / agg["capacidade"]
    agg["folga"] = 100 * (1 - agg["ocup_global"])
    agg["cv"] = 100 * agg["dp"] / agg["media"]
    agg["cauda"] = agg["dist_max"] / agg["dist_med"]
    return bruto, agg, info, todas, falhas


def ordem_natural(inst):
    m = re.match(r"Instancia(\d)_G(\d+)", inst)
    return (int(m.group(1)), int(m.group(2)))


def salva(fig, nome):
    caminho = PASTA_FIG / nome
    fig.savefig(caminho, bbox_inches="tight")
    plt.close(fig)
    print("gerado:", caminho)


# ----------------------------------------------------------------------------
# 1. Eficácia da Busca Local em função da Ocupação e Folga (com Seção 5.2)
# ----------------------------------------------------------------------------
def fig_desempenho_ocupacao(agg):
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.8))

    # (a) Melhoria vs Ocupação Global
    ax = axs[0]
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.errorbar(100 * d["ocup_global"], d["melh"], yerr=d["melh_dp"], fmt="o",
                    color=COR[k], alpha=0.55, ms=5, elinewidth=0.8, capsize=1.5,
                    label=f"$K={k}$")

    # Destaque G4
    offsets_a = {
        ("Instancia1_G4", 2): (6, 3),
        ("Instancia2_G4", 2): (6, 3),
        ("Instancia1_G4", 1): (6, -6),
        ("Instancia2_G4", 1): (6, -6),
    }
    for _, r in agg[agg.inst.map(grupo) == GRUPO_ALVO].iterrows():
        ax.scatter(100 * r["ocup_global"], r["melh"], color=COR_G4, s=36, zorder=5, edgecolor="black", lw=0.5)
        k_txt = f"$K={r.K}$"
        dx, dy = offsets_a.get((r.inst, r.K), (5, 0))
        ax.annotate(f"{rotulo(r.inst)} ({k_txt})", (100 * r["ocup_global"], r["melh"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=6.8,
                    color=COR_G4, fontweight="bold")

    ax.set_xlabel("Taxa de ocupação global da instância (%)")
    ax.set_ylabel("Melhoria sobre o construtivo (%)")
    ax.set_title("(a) Eficácia da busca local vs. ocupação")
    ax.legend(loc="upper right", frameon=True)

    # (b) Ganho Marginal de K=2 vs Folga (Ilustração Seção 5.2)
    ax = axs[1]
    w = agg.pivot(index="inst", columns="K", values="melh")
    w["folga"] = 100 * (1 - agg[agg.K == 1].set_index("inst")["ocup_global"])
    w["delta"] = w[2] - w[1]
    bloq = ["Instancia1_G8", "Instancia2_G8"]
    critica = [i for i in w.index if (100 - w.loc[i, "folga"]) > 94 and i not in bloq]

    ax.axhline(0, color="gray", ls="--", lw=0.8)

    offsets_b = {
        "Instancia1_G8": (5, 3),
        "Instancia2_G8": (5, -7),
        "Instancia2_G9": (5, -5),
        "Instancia2_G10": (5, -3),
        "Instancia2_G14": (5, 3),
        "Instancia1_G4": (5, 3),
        "Instancia2_G4": (5, 3),
    }

    for i, r in w.iterrows():
        if i in bloq:
            cor, marc, tam = "#8e44ad", "X", 55
        elif i in critica:
            cor, marc, tam = "#16a085", "D", 32
        elif grupo(i) == GRUPO_ALVO:
            cor, marc, tam = COR_G4, "o", 42
        else:
            cor, marc, tam = "#7f8c8d", "o", 22
        ax.scatter(r["folga"], r["delta"], c=cor, marker=marc, s=tam, edgecolor="black", lw=0.4, zorder=4)

        if i in bloq or i in critica or grupo(i) == GRUPO_ALVO:
            dx, dy = offsets_b.get(i, (5, 3))
            ax.annotate(rotulo(i), (r["folga"], r["delta"]), xytext=(dx, dy),
                        textcoords="offset points", fontsize=6.8, color=cor, fontweight="bold")

    ax.set_ylim(-19, 18)
    ax.set_xlabel("Folga de capacidade da instância (% de vagas livres)")
    ax.set_ylabel("Ganho adicional de $K=2$ sobre $K=1$ (p.p.)")
    ax.set_title("(b) Ganho de $K=2$ vs. folga (análise Seção 5.2)")

    h = [
        plt.Line2D([], [], marker="X", ls="", color="#8e44ad", ms=6, label="Bloqueio Viz. 3 (melhoria K=2 nula)"),
        plt.Line2D([], [], marker="D", ls="", color="#16a085", ms=5, label="Ocupação crítica ($>94\\%$)"),
        plt.Line2D([], [], marker="o", ls="", color=COR_G4, ms=6, label="Grupo 4"),
        plt.Line2D([], [], marker="o", ls="", color="#7f8c8d", ms=5, label="Demais instâncias"),
    ]
    ax.legend(handles=h, loc="lower left", fontsize=6.5, frameon=True)

    fig.tight_layout()
    salva(fig, "fig_desempenho_ocupacao.pdf")


# ----------------------------------------------------------------------------
# 2. Escalabilidade e Tempo de Execução vs. Porte da Instância
# ----------------------------------------------------------------------------
def fig_escalabilidade_porte(agg):
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.8))

    # (a) Tempo de busca vs Salas
    ax = axs[0]
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["salas"], d["t_busca"], s=20, color=COR[k], alpha=0.7, label=f"$K={k}$")

    ax.axhline(LIMITE_TEMPO, color="gray", ls="--", lw=0.8)
    ax.text(22, LIMITE_TEMPO * 1.15, "limite de tempo (300 s)", fontsize=7, color="gray")

    for _, r in agg[agg.inst.map(grupo) == GRUPO_ALVO].iterrows():
        ax.scatter(r["salas"], r["t_busca"], color=COR_G4, s=36, zorder=5, edgecolor="black", lw=0.5)
        if r.K == 2:
            ax.annotate(rotulo(r.inst), (r["salas"], r["t_busca"]), xytext=(5, 3),
                        textcoords="offset points", fontsize=7, color=COR_G4, fontweight="bold")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel(r"Total de salas na rede escolar ($\sum_j |S_j|$)")
    ax.set_ylabel("Tempo de busca local (s)")
    ax.set_title(r"(a) Tempo de busca vs. total de salas $\sum |S_j|$")
    ax.legend(loc="lower right", frameon=True)

    # (b) Tempo de execução vs Candidatos
    ax = axs[1]
    base = agg[agg.K == 1]
    ax.scatter(base["candidatos"], base["t_constr"], marker="s", s=16, color="#7f8c8d", label="Construção (Fases 1+2)")
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["candidatos"], d["t_busca"], s=20, color=COR[k], alpha=0.7, label=f"Busca local $K={k}$")

    ax.axhline(LIMITE_TEMPO, color="gray", ls="--", lw=0.8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Número de candidatos ($|C|$)")
    ax.set_ylabel("Tempo médio de execução (s)")
    ax.set_title("(b) Tempo de execução vs. número de candidatos")
    ax.legend(loc="lower right", fontsize=6.8, frameon=True)

    fig.tight_layout()
    salva(fig, "fig_escalabilidade_porte.pdf")


# ----------------------------------------------------------------------------
# 3. Variabilidade e Sensibilidade da Busca Local vs. Complexidade
# ----------------------------------------------------------------------------
def fig_variabilidade_complexidade(agg):
    fig, ax = plt.subplots(figsize=(6.2, 3.8))

    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["salas"], d["cv"], s=24, color=COR[k], alpha=0.75, label=f"$K={k}$")

    offsets_cv = {
        ("Instancia1_G4", 2): (5, 5),
        ("Instancia2_G4", 2): (-48, -12),
        ("Instancia1_G4", 1): (5, 4),
        ("Instancia2_G4", 1): (-48, -9),
    }
    for _, r in agg[agg.inst.map(grupo) == GRUPO_ALVO].iterrows():
        ax.scatter(r["salas"], r["cv"], color=COR_G4, s=40, zorder=5, edgecolor="black", lw=0.5)
        dx, dy = offsets_cv.get((r.inst, r.K), (5, 0))
        ax.annotate(f"{rotulo(r.inst)} (K={r.K})", (r["salas"], r["cv"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=6.8,
                    color=COR_G4, fontweight="bold")

    ax.set_xlabel(r"Complexidade estrutural: total de salas ($\sum_j |S_j|$)")
    ax.set_ylabel("Coeficiente de variação entre sementes (%)")
    ax.set_title("Variabilidade da solução final vs. complexidade estrutural")
    ax.legend(loc="upper left", frameon=True)

    fig.tight_layout()
    salva(fig, "fig_variabilidade_complexidade.pdf")


# ----------------------------------------------------------------------------
# 4. Comportamento e Equilíbrio da Solução Encontrada vs. Características
# ----------------------------------------------------------------------------
def fig_comportamento_solucao(agg):
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.8))

    # (a) Ocupação Mínima vs Ocupação Global
    ax = axs[0]
    ax.plot([75, 100], [75, 100], color="gray", ls="--", lw=0.8, label="Equilíbrio ideal ($y=x$)")

    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(100 * d["ocup_global"], 100 * d["ocup_min"], s=22, color=COR[k], alpha=0.7, label=f"$K={k}$")

    offsets_min = {
        ("Instancia1_G4", 1): (5, 4),
        ("Instancia2_G4", 1): (-45, 4),
        ("Instancia1_G4", 2): (5, -4),
        ("Instancia2_G4", 2): (-45, -8),
    }
    for _, r in agg[agg.inst.map(grupo) == GRUPO_ALVO].iterrows():
        ax.scatter(100 * r["ocup_global"], 100 * r["ocup_min"], color=COR_G4, s=38, zorder=5, edgecolor="black", lw=0.5)
        dx, dy = offsets_min.get((r.inst, r.K), (5, 0))
        ax.annotate(f"{rotulo(r.inst)} (K={r.K})", (100 * r["ocup_global"], 100 * r["ocup_min"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=6.8,
                    color=COR_G4, fontweight="bold")

    ax.set_xlim(78, 100)
    ax.set_ylim(10, 102)
    ax.set_xlabel("Taxa de ocupação global da instância (%)")
    ax.set_ylabel("Ocupação mínima entre escolas utilizadas (%)")
    ax.set_title("(a) Desbalanceamento da ocupação escolar")
    ax.legend(loc="upper left", fontsize=6.8, frameon=True)

    # (b) Razão Distância Máxima / Média vs Ocupação
    ax = axs[1]
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(100 * d["ocup_global"], d["cauda"], s=22, color=COR[k], alpha=0.7, label=f"$K={k}$")

    med_cauda = agg["cauda"].median()
    ax.axhline(med_cauda, color="gray", ls="--", lw=0.8, label=f"Mediana global ({med_cauda:.1f}$\\times$)")

    offsets_cauda = {
        ("Instancia1_G4", 2): (5, 4),
        ("Instancia2_G4", 2): (5, 4),
        ("Instancia1_G4", 1): (5, -6),
        ("Instancia2_G4", 1): (-45, 4),
    }
    for _, r in agg[agg.inst.map(grupo) == GRUPO_ALVO].iterrows():
        ax.scatter(100 * r["ocup_global"], r["cauda"], color=COR_G4, s=38, zorder=5, edgecolor="black", lw=0.5)
        dx, dy = offsets_cauda.get((r.inst, r.K), (5, 0))
        ax.annotate(f"{rotulo(r.inst)} (K={r.K})", (100 * r["ocup_global"], r["cauda"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=6.8,
                    color=COR_G4, fontweight="bold")

    ax.set_xlabel("Taxa de ocupação global da instância (%)")
    ax.set_ylabel("Razão distância máxima / distância média")
    ax.set_title("(b) Equidade espacial: proporção do pior caso")
    ax.legend(loc="upper right", fontsize=6.8, frameon=True)

    fig.tight_layout()
    salva(fig, "fig_comportamento_solucao.pdf")


# ----------------------------------------------------------------------------
# 5. Análise Comparativa Dedicada Exclusivamente ao Grupo 4 (I1-G4 vs. I2-G4)
# ----------------------------------------------------------------------------
def fig_comparativo_g4(agg):
    fig, axs = plt.subplots(1, 2, figsize=(9.0, 3.8))

    g4 = agg[agg.inst.map(grupo) == GRUPO_ALVO].sort_values(["inst", "K"])
    i1_k1 = g4[(g4.inst == "Instancia1_G4") & (g4.K == 1)].iloc[0]
    i1_k2 = g4[(g4.inst == "Instancia1_G4") & (g4.K == 2)].iloc[0]
    i2_k1 = g4[(g4.inst == "Instancia2_G4") & (g4.K == 1)].iloc[0]
    i2_k2 = g4[(g4.inst == "Instancia2_G4") & (g4.K == 2)].iloc[0]

    # (a) Custo Inicial vs Custo Final
    ax = axs[0]
    x = np.array([0, 1.2])
    w = 0.24

    ax.bar(x - w, [i1_k1["inicial"], i2_k1["inicial"]], width=w, color="#7f8c8d", label="Solução Inicial")
    ax.bar(x, [i1_k1["media"], i2_k1["media"]], width=w, yerr=[i1_k1["dp"], i2_k1["dp"]],
           color=COR[1], capsize=2, label="Busca Local $K=1$")
    ax.bar(x + w, [i1_k2["media"], i2_k2["media"]], width=w, yerr=[i1_k2["dp"], i2_k2["dp"]],
           color=COR[2], capsize=2, label="Busca Local $K=2$")

    ax.set_xticks(x)
    ax.set_xticklabels(["Instancia1_G4\n(Base: Uniforme)", "Instancia2_G4\n(Diferenciada: Polarizada)"], fontweight="bold")
    ax.set_ylabel("Distância total percorrida (km)")
    ax.set_title("(a) Custo inicial e final nas instâncias do G4")
    ax.legend(loc="upper right", frameon=True)

    ax.text(x[0] - w, i1_k1["inicial"] + 300, f"{num(i1_k1['inicial'], 0)}", ha="center", fontsize=7)
    ax.text(x[1] - w, i2_k1["inicial"] + 300, f"{num(i2_k1['inicial'], 0)}\n(-24%)", ha="center", fontsize=7, color="#c0392b", fontweight="bold")

    # (b) Redução percentual
    ax = axs[1]
    ax.bar(x - w/2, [i1_k1["melh"], i2_k1["melh"]], width=w, color=COR[1], label="Melhoria $K=1$ (%)")
    ax.bar(x + w/2, [i1_k2["melh"], i2_k2["melh"]], width=w, color=COR[2], label="Melhoria $K=2$ (%)")

    ax.text(x[0] - w/2, i1_k1["melh"] + 1, f"{i1_k1['melh']:.1f}%", ha="center", fontsize=7.5)
    ax.text(x[0] + w/2, i1_k2["melh"] + 1, f"{i1_k2['melh']:.1f}%\n(+14.4 p.p.)", ha="center", fontsize=7.5, color=COR[2], fontweight="bold")

    ax.text(x[1] - w/2, i2_k1["melh"] + 1, f"{i2_k1['melh']:.1f}%", ha="center", fontsize=7.5)
    ax.text(x[1] + w/2, i2_k2["melh"] + 1, f"{i2_k2['melh']:.1f}%\n(+8.0 p.p.)", ha="center", fontsize=7.5, color=COR[2], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(["Instancia1_G4\n(Uniforme)", "Instancia2_G4\n(Polarizada)"], fontweight="bold")
    ax.set_ylabel("Melhoria sobre a solução inicial (%)")
    ax.set_ylim(0, 44)
    ax.set_title("(b) Comparativo de melhoria obtida pela busca local")
    ax.legend(loc="upper right", frameon=True)

    fig.tight_layout()
    salva(fig, "fig_comparativo_g4.pdf")


# ----------------------------------------------------------------------------
# Tabela LaTeX Única (mantida na íntegra para transparência e completude)
# ----------------------------------------------------------------------------
def gera_tabela(agg, info, todas, falhas):
    por = {(r.inst, r.K): r for r in agg.itertuples()}
    L = []
    L.append(r"% Arquivo gerado por gerar_graficos.py -- não editar manualmente")
    L.append(r"{\scriptsize")
    L.append(r"\setlength{\tabcolsep}{2.6pt}")
    L.append(r"\begin{longtable}{lrrrcrrrrrrrrrrr}")
    L.append(r"\caption{Resultados experimentais nas 28 instâncias do conjunto da turma (10 sementes por configuração; "
             r"execução em lote com 4 processos paralelos). Custos em km; desvio padrão populacional; tempos médios em segundos; "
             r"``Lim.'' é o número de execuções cuja busca local parou no limite de 300~s; ``Escolas'', ``Ocup. mín.'' e ``Dist.'' são médias das 10 execuções (ocupação das escolas utilizadas; "
             r"distância média/máxima por candidato). Em destaque, as instâncias do Grupo~4.}\label{tab:resultados}\\")
    cab = (r"\textbf{Instância} & $|C|$ & $|L|$ / salas & \textbf{Ocup.} & $K$ & \textbf{Inicial} & \textbf{Melhor} & "
           r"\textbf{Média $\pm$ dp} & \textbf{Pior} & \textbf{Melh.} & \textbf{T. constr.} & \textbf{T. busca} & "
           r"\textbf{Lim.} & \textbf{Escolas} & \textbf{Ocup. mín.} & \textbf{Dist. méd./máx.} \\")
    L += [r"\toprule", cab, r"\midrule", r"\endfirsthead",
          r"\toprule", cab, r"\midrule", r"\endhead",
          r"\midrule \multicolumn{16}{r}{\textit{continua na próxima página}} \\ \endfoot",
          r"\bottomrule \endlastfoot"]
    for inst in todas:
        i = info.loc[inst]
        nome = inst.replace("_", r"\_")
        fixo = (f"& {inteiro(i.candidatos)} & {int(i.n_escolas)} / {int(i.salas)} "
                f"& {num(100 * i.candidatos / i.capacidade, 1)}\\%")
        destaque = grupo(inst) == GRUPO_ALVO
        pref = r"\rowcolor{gray!18}" if destaque else ""
        nome_fmt = rf"\texttt{{{nome}}}"
        if destaque:
            nome_fmt = rf"\textbf{{{nome_fmt}}}"
        if inst in falhas:
            L.append(rf"{pref}{nome_fmt} {fixo} & \multicolumn{{12}}{{l}}"
                     rf"{{\textit{{Inviável na Fase 1 ({MOTIVO_FALHA[inst]})}}}} \\")
            L.append(r"\midrule")
            continue
        for k in (1, 2):
            r = por[(inst, k)]
            if k == 1:
                partes = [inteiro(i.candidatos), f"{int(i.n_escolas)} / {int(i.salas)}",
                          f"{num(100 * i.candidatos / i.capacidade, 1)}\\%"]
                fixo_mr = " ".join(f"& \\multirow{{2}}{{*}}{{{p}}}" for p in partes)
                cabeca = f"\\multirow{{2}}{{*}}{{{nome_fmt}}} {fixo_mr}"
            else:
                cabeca = "& & &"
            ini_txt = f"\\multirow{{2}}{{*}}{{{num(r.inicial)}}}" if k == 1 else ""
            linha = (f"{pref}{cabeca} & {k} & {ini_txt} & {num(r.melhor)} & ${num(r.media)} \\pm {num(r.dp)}$ & "
                     f"{num(r.pior)} & {num(r.melh, 1)}\\% & {f"\\multirow{{2}}{{*}}{{{num(r.t_constr, 2)}}}" if k == 1 else ''} & "
                     f"{num(r.t_busca, 1)} & {r.n_lim}/{r.n} & {num(r.escolas, 1)} & {num(100 * r.ocup_min, 1)}\\% & "
                     f"{num(r.dist_med)} / {num(r.dist_max)} \\\\")
            L.append(linha)
        L.append(r"\midrule")
    L[-1] = r"% fim"
    L.append(r"\end{longtable}")
    L.append(r"}")
    conteudo = "\n".join(L) + "\n"
    (RAIZ / "tabela_resultados.tex").write_text(conteudo, encoding="utf-8")
    print("gerado:", RAIZ / "tabela_resultados.tex")


def resumo(agg, bruto, falhas):
    s = []
    p = lambda *a: s.append(" ".join(str(x) for x in a))
    p("=== RESUMO DOS EXPERIMENTOS ===")
    p("instâncias viáveis:", agg.inst.nunique(), "| inviáveis:", len(falhas), falhas)
    p("total de execuções:", len(bruto))
    for k in (1, 2):
        d = agg[agg.K == k]
        p(f"K={k}: melhoria média={d.melh.mean():.2f}% mediana={d.melh.median():.2f}% min={d.melh.min():.2f}% max={d.melh.max():.2f}%")
        p(f"K={k}: tempo busca médio={d.t_busca.mean():.1f}s mediana={d.t_busca.median():.1f}s max={d.t_busca.max():.1f}s")
        p(f"K={k}: cv médio={d.cv.mean():.2f}%")
    (PASTA_FIG / "resumo_estatisticas.txt").write_text("\n".join(s), encoding="utf-8")
    print("\n".join(s))


def main():
    bruto, agg, info, todas, falhas = carrega_dados()
    fig_desempenho_ocupacao(agg)
    fig_escalabilidade_porte(agg)
    fig_variabilidade_complexidade(agg)
    fig_comportamento_solucao(agg)
    fig_comparativo_g4(agg)
    gera_tabela(agg, info, todas, falhas)
    resumo(agg, bruto, falhas)


if __name__ == "__main__":
    main()
