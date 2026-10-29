"""Gera os gráficos e a tabela de resultados do relatório (seção 6 e Seção 5.2).

Entrada : resultados_lote/resultados_completos.csv (+ planilha_K1.csv para as falhas)
          e os arquivos de instância (apenas cabeçalho/escolas, a matriz de distâncias é ignorada).
Saída   : resultados_lote/figuras/*.pdf, resultados_lote/tabela_resultados.tex e
          resultados_lote/figuras/resumo_estatisticas.txt (números citados no texto).

Uso (de qualquer pasta): python src/gerar_graficos.py
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
RAIZ = LOTE                                                 # saída: tabela .tex e pasta figuras/ dentro de resultados_lote/
PASTA_FIG = RAIZ / "figuras"
CACHE_INFO = PASTA_FIG / "info_instancias.csv"
PASTA_FIG.mkdir(parents=True, exist_ok=True)

COR = {1: "#4C72B0", 2: "#DD8452"}
COR_G4 = "#C0392B"
GRUPO_ALVO = "G4"
LIMITE_TEMPO = 300  # limite de tempo (s) da busca local usado no lote (--limite-de-tempo padrão)

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8.5,
    "legend.fontsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
    "pdf.fonttype": 42,
})

# Motivo da inviabilidade na Fase 1 (diagnóstico já presente no relatório)
MOTIVO_FALHA = {
    "Instancia1_G2": r"$|L|=5$ escolas para $|T|=6$ tipos de prova",
    "Instancia2_G2": r"$|L|=5$ escolas para $|T|=6$ tipos de prova",
    "Instancia2_G3": r"cada tipo exige $\ge 2$ escolas: $6 \times 2 = 12 > 10$",
    "Instancia2_G5": r"4 tipos exigem $\ge 3$ escolas cada: $16 > 15$",
    "Instancia2_G7": r"98,0\% de ocupação e forte assimetria de demanda",
}


# ----------------------------------------------------------------------------
# utilitários
# ----------------------------------------------------------------------------
def normaliza_nome(nome):
    """'instancia_1_G13', 'Instancia1_G7(1)', 'instancia2_G8' -> 'Instancia1_G13' etc."""
    m = re.search(r"instancia_?(\d)_G(\d+)", str(nome), flags=re.I)
    return f"Instancia{m.group(1)}_G{m.group(2)}" if m else None


def rotulo(inst):
    """Instancia1_G4 -> I1-G4"""
    m = re.match(r"Instancia(\d)_G(\d+)", inst)
    return f"I{m.group(1)}-G{m.group(2)}"


def grupo(inst):
    return inst.split("_")[-1]


def num(x, casas=2):
    """Número no formato brasileiro (1.234,56)."""
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def inteiro(x):
    return num(x, 0)


def info_instancia(caminho):
    """Lê só o cabeçalho: nº de candidatos, escolas, salas e capacidade total."""
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
        # em caso de duplicatas (ex.: arquivo placeholder de 88 bytes), vale o maior
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


# ----------------------------------------------------------------------------
# carga e agregação
# ----------------------------------------------------------------------------
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

    # desvio padrão populacional (ddof=0), igual ao usado nas tabelas anteriores do relatório
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
    agg["cauda"] = agg["dist_max"] / agg["dist_med"]
    return bruto, agg, info, todas, falhas


def ordem_natural(inst):
    m = re.match(r"Instancia(\d)_G(\d+)", inst)
    return (int(m.group(1)), int(m.group(2)))


# ----------------------------------------------------------------------------
# gráficos
# ----------------------------------------------------------------------------
def estiliza_eixo_x(ax, labels):
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=60, ha="right")
    for t, lab in zip(ax.get_xticklabels(), labels):
        if lab.endswith(GRUPO_ALVO):
            t.set_color(COR_G4)
            t.set_fontweight("bold")


def destaca_g4(ax, labels):
    for i, lab in enumerate(labels):
        if lab.endswith(GRUPO_ALVO):
            ax.axvspan(i - 0.5, i + 0.5, color=COR_G4, alpha=0.10, lw=0)


def salva(fig, nome):
    fig.savefig(PASTA_FIG / nome, bbox_inches="tight")
    plt.close(fig)
    print("gerado:", PASTA_FIG / nome)


def fig_melhoria(agg, ordem):
    """Melhoria percentual média (e desvio entre sementes) por instância, K=1 vs K=2."""
    labels = [rotulo(i) for i in ordem]
    x = np.arange(len(ordem))
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    destaca_g4(ax, labels)
    for k, desl in ((1, -0.2), (2, 0.2)):
        d = agg[agg.K == k].set_index("inst").loc[ordem]
        ax.bar(x + desl, d["melh"], width=0.4, color=COR[k], label=f"$K={k}$",
               yerr=d["melh_dp"], error_kw=dict(lw=0.8, capsize=1.5))
    estiliza_eixo_x(ax, labels)
    ax.set_ylabel("Melhoria sobre a solução inicial (%)")
    ax.set_xlim(-0.7, len(ordem) - 0.3)
    ax.legend(ncol=2, loc="upper right")
    salva(fig, "fig_melhoria.pdf")


def fig_variabilidade(bruto, ordem):
    """Custo final normalizado pelo inicial (=100%) em cada uma das 10 sementes."""
    labels = [rotulo(i) for i in ordem]
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    destaca_g4(ax, labels)
    for k, desl in ((1, -0.2), (2, 0.2)):
        dados = [bruto[(bruto.inst == i) & (bruto.K == k)]["razao"].values for i in ordem]
        bp = ax.boxplot(dados, positions=np.arange(len(ordem)) + desl, widths=0.32,
                        patch_artist=True, showfliers=True, manage_ticks=False,
                        flierprops=dict(marker="o", ms=2, mfc=COR[k], mec="none"),
                        medianprops=dict(color="black", lw=0.9),
                        whiskerprops=dict(lw=0.7), capprops=dict(lw=0.7), boxprops=dict(lw=0.7))
        for caixa in bp["boxes"]:
            caixa.set_facecolor(COR[k])
            caixa.set_alpha(0.85)
    ax.axhline(100, color="gray", ls="--", lw=0.8)
    ax.text(len(ordem) - 0.4, 100.8, "solução inicial (100%)", ha="right", va="bottom", color="gray", fontsize=7)
    estiliza_eixo_x(ax, labels)
    ax.set_xlim(-0.7, len(ordem) - 0.3)
    ax.set_ylabel("Custo final / custo inicial (%)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=COR[k]) for k in (1, 2)]
    ax.legend(handles, ["$K=1$", "$K=2$"], ncol=2, loc="lower right")
    salva(fig, "fig_variabilidade.pdf")


def anota(ax, d, col_y, deslocamentos=None, col_x="candidatos"):
    """Rotula as instâncias do G4 nos gráficos de dispersão."""
    for _, r in d.iterrows():
        if grupo(r["inst"]) == GRUPO_ALVO:
            ax.annotate(rotulo(r["inst"]), (r[col_x], r[col_y]), xytext=(4, 4),
                        textcoords="offset points", fontsize=7, color=COR_G4, fontweight="bold")


def fig_tempo(agg):
    """Tempo de execução (construção e busca local) e custo-benefício da busca local."""
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.3))

    # (a) tempo x candidatos (log-log)
    ax = axs[0]
    base = agg[agg.K == 1]
    ax.scatter(base["candidatos"], base["t_constr"], marker="s", s=14, color="gray", label="construção")
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["candidatos"], d["t_busca"], s=16, color=COR[k], label=f"busca local $K={k}$")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Candidatos $|C|$"); ax.set_ylabel("Tempo médio (s)")
    ax.axhline(LIMITE_TEMPO, color="gray", ls="--", lw=0.8)
    ax.text(ax.get_xlim()[0] * 1.05, LIMITE_TEMPO * 1.15, "limite de 300 s", fontsize=6.5, color="gray")
    ax.set_title("(a) Tempo vs. candidatos")
    ax.legend(fontsize=6.5, loc="lower right")
    anota(ax, agg[agg.K == 2], "t_busca")

    # (b) tempo de busca x salas
    ax = axs[1]
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["salas"], d["t_busca"], s=16, color=COR[k], label=f"$K={k}$")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel(r"Total de salas $\sum_j |S_j|$"); ax.set_ylabel("Tempo de busca local (s)")
    ax.axhline(LIMITE_TEMPO, color="gray", ls="--", lw=0.8)
    ax.set_title("(b) Tempo vs. salas")
    ax.legend(loc="lower right")
    anota(ax, agg[agg.K == 2], "t_busca", col_x="salas")

    # (c) melhoria x tempo
    ax = axs[2]
    for k in (1, 2):
        d = agg[agg.K == k]
        ax.scatter(d["t_busca"], d["melh"], s=16, color=COR[k], label=f"$K={k}$")
    ax.set_xscale("log")
    ax.set_xlabel("Tempo de busca local (s)"); ax.set_ylabel("Melhoria média (%)")
    ax.set_title("(c) Ganho vs. tempo")
    ax.legend(loc="upper left")
    anota(ax, agg[agg.K == 2], "melh", col_x="t_busca")

    fig.tight_layout()
    salva(fig, "fig_tempo.pdf")


def fig_solucao(agg, ordem):
    """Informações da solução: ocupação das escolas utilizadas e cauda de distâncias."""
    labels = [rotulo(i) for i in ordem]
    x = np.arange(len(ordem))
    fig, axs = plt.subplots(2, 1, figsize=(8.5, 5.4), sharex=True)
    for ax in axs:
        destaca_g4(ax, labels)
        ax.set_xlim(-0.7, len(ordem) - 0.3)

    for k, desl in ((1, -0.2), (2, 0.2)):
        d = agg[agg.K == k].set_index("inst").loc[ordem]
        axs[0].bar(x + desl, 100 * d["ocup_min"], width=0.4, color=COR[k], label=f"$K={k}$")
        axs[1].bar(x + desl, d["cauda"], width=0.4, color=COR[k], label=f"$K={k}$")

    dk = agg[agg.K == 1].set_index("inst").loc[ordem]
    axs[0].scatter(x, 100 * dk["ocup_global"], marker="_", s=90, color="black", zorder=5,
                   label="ocupação global da instância")
    axs[0].set_ylim(0, 118)
    axs[0].set_ylabel("Ocupação mínima entre\nas escolas utilizadas (%)")
    axs[0].legend(ncol=3, loc="upper right", fontsize=7)
    axs[1].set_ylabel("Distância máxima /\ndistância média")
    axs[1].legend(ncol=2, loc="upper right")
    estiliza_eixo_x(axs[1], labels)
    fig.tight_layout()
    salva(fig, "fig_solucao.pdf")


def fig_k1_vs_k2(agg):
    """Ilustra a Seção 5.2: quando permitir 2 tipos por escola não ajuda."""
    w = agg.pivot(index="inst", columns="K", values="melh")
    w["folga"] = 100 * (1 - agg[agg.K == 1].set_index("inst")["ocup_global"])
    w["delta"] = w[2] - w[1]
    bloq = w[w[2] <= 1e-9].index.tolist()            # nenhuma melhoria com K=2
    critica = [i for i in w.index if (100 - w.loc[i, "folga"]) > 94 and i not in bloq]

    fig, axs = plt.subplots(1, 2, figsize=(9, 3.7))
    # deslocamentos (pontos) dos rótulos para evitar sobreposição
    OFFS = {"Instancia1_G8": (5, 5, "left"), "Instancia2_G8": (5, 5, "left"),
            "Instancia2_G10": (-5, -9, "right"), "Instancia2_G14": (5, 3, "left"),
            "Instancia2_G4": (5, -9, "left")}
    ax = axs[0]
    lim = max(w[1].max(), w[2].max()) * 1.05
    ax.plot([0, lim], [0, lim], color="gray", ls="--", lw=0.8)
    ax.text(lim * 0.97, lim * 0.90, "$K=2$ melhor", ha="right", color="gray", fontsize=7, rotation=0)
    ax.text(lim * 0.97, lim * 0.05, "$K=1$ melhor", ha="right", color="gray", fontsize=7)
    ax.fill_between([0, lim], [0, lim], [0, 0], color="gray", alpha=0.06, lw=0)
    for i, r in w.iterrows():
        cor = "black"
        marc, tam = "o", 22
        if i in bloq:
            cor = "#8E44AD"; marc = "X"; tam = 50
        elif i in critica:
            cor = "#16A085"; marc = "D"; tam = 28
        elif grupo(i) == GRUPO_ALVO:
            cor = COR_G4; tam = 38
        else:
            cor = "#7F8C8D"
        ax.scatter(r[1], r[2], c=cor, marker=marc, s=tam, edgecolor="white", lw=0.4, zorder=3)
        if i in bloq or i in critica or grupo(i) == GRUPO_ALVO:
            dx, dy, ha = OFFS.get(i, (4, 4, "left"))
            ax.annotate(rotulo(i), (r[1], r[2]), xytext=(dx, dy), ha=ha,
                        textcoords="offset points", fontsize=6.8, color=cor)
    ax.set_xlim(-1, lim); ax.set_ylim(-2, lim)
    ax.set_xlabel("Melhoria média com $K=1$ (%)")
    ax.set_ylabel("Melhoria média com $K=2$ (%)")
    ax.set_title("(a) $K=1$ vs. $K=2$ por instância")

    ax = axs[1]
    ax.axhline(0, color="gray", lw=0.8)
    for i, r in w.iterrows():
        if i in bloq:
            cor, marc, tam = "#8E44AD", "X", 50
        elif i in critica:
            cor, marc, tam = "#16A085", "D", 28
        elif grupo(i) == GRUPO_ALVO:
            cor, marc, tam = COR_G4, "o", 38
        else:
            cor, marc, tam = "#7F8C8D", "o", 22
        ax.scatter(r["folga"], r["delta"], c=cor, marker=marc, s=tam, edgecolor="white", lw=0.4, zorder=3)
        if i in bloq or i in critica or grupo(i) == GRUPO_ALVO:
            ax.annotate(rotulo(i), (r["folga"], r["delta"]), xytext=(4, 3),
                        textcoords="offset points", fontsize=6.8, color=cor)
    ax.set_xlabel("Folga de capacidade da instância (% de vagas livres)")
    ax.set_ylabel("Ganho extra de $K=2$ sobre $K=1$ (p.p.)")
    ax.set_title("(b) Ganho de $K=2$ vs. folga")

    h = [
        plt.Line2D([], [], marker="X", ls="", color="#8E44AD", label="bloqueio da Viz. 3 (sem melhoria com $K=2$)"),
        plt.Line2D([], [], marker="D", ls="", color="#16A085", label="ocupação crítica ($>94\\%$)"),
        plt.Line2D([], [], marker="o", ls="", color=COR_G4, label="Grupo 4"),
        plt.Line2D([], [], marker="o", ls="", color="#7F8C8D", label="demais instâncias"),
    ]
    fig.legend(handles=h, loc="lower center", ncol=4, fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    salva(fig, "fig_k1_vs_k2.pdf")
    return w, bloq, critica


# ----------------------------------------------------------------------------
# tabela LaTeX (única)
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
                # multirow nas colunas fixas
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
    L[-1] = r"% fim"   # a última \midrule é substituída pelo \bottomrule do \endlastfoot
    L.append(r"\end{longtable}")
    L.append(r"}")
    (RAIZ / "tabela_resultados.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("gerado:", RAIZ / "tabela_resultados.tex")


# ----------------------------------------------------------------------------
# números citados no texto
# ----------------------------------------------------------------------------
def resumo(agg, bruto, w, bloq, critica, falhas):
    s = []
    p = lambda *a: s.append(" ".join(str(x) for x in a))
    p("instâncias viáveis:", agg.inst.nunique(), "| inviáveis:", len(falhas), falhas)
    p("execuções:", len(bruto), "| inviáveis nenhuma:", (bruto.custo_final.isna()).sum())
    for k in (1, 2):
        d = agg[agg.K == k]
        p(f"K={k}: melhoria média das médias={d.melh.mean():.2f}% mediana={d.melh.median():.2f}% "
          f"min={d.melh.min():.2f} ({d.loc[d.melh.idxmin(), 'inst']}) max={d.melh.max():.2f} ({d.loc[d.melh.idxmax(), 'inst']})")
        p(f"K={k}: t_busca min={d.t_busca.min():.2f} max={d.t_busca.max():.1f} ({d.loc[d.t_busca.idxmax(), 'inst']}) "
          f"mediana={d.t_busca.median():.1f}; t_constr max={d.t_constr.max():.2f}")
        p(f"K={k}: dp relativo médio (dp/média custo) = {(100 * d.dp / d.media).mean():.2f}%  "
          f"melh_dp médio={d.melh_dp.mean():.2f} p.p.")
    for k in (1, 2):
        d = agg[agg.K == k]
        p(f"K={k}: execuções que pararam no limite de tempo: {int(d.n_lim.sum())} de {int(d.n.sum())}; "
          f"instâncias afetadas: {sorted(rotulo(i) for i in d[d.n_lim > 0].inst)}")
    p("tempo total (s) construção+busca, somando médias K1/K2:",
      round((agg[agg.K == 1].t_busca + agg[agg.K == 1].t_constr).sum()), round((agg[agg.K == 2].t_busca + agg[agg.K == 2].t_constr).sum()))
    p("K=2 > K=1 (média):", int((w[2] > w[1] + 1e-9).sum()), "de", len(w))
    p("K=2 < K=1 (média):", sorted((rotulo(i), round(w.loc[i, 'delta'], 1)) for i in w.index if w.loc[i, 'delta'] < -1e-9))
    p("bloqueio (melhoria K=2 = 0):", bloq)
    p("ocupação crítica >94%:", critica)
    p("folga das instâncias de bloqueio (%):", {rotulo(i): round(w.loc[i, 'folga'], 1) for i in bloq})
    pq = agg[agg.candidatos < 1000].inst.unique()
    p("pequenas (<1000 cand.):", len(pq), "t_busca máx K1/K2:",
      round(agg[(agg.candidatos < 1000) & (agg.K == 1)].t_busca.max(), 2),
      round(agg[(agg.candidatos < 1000) & (agg.K == 2)].t_busca.max(), 2))
    gr = agg[agg.candidatos >= 1000]
    p("grandes (>=1000):", gr.inst.nunique(), "cand min/max", gr.candidatos.min(), gr.candidatos.max())
    p("correlação log(salas)~log(t_busca) K2:",
      round(np.corrcoef(np.log(gr[gr.K == 2].salas), np.log(gr[gr.K == 2].t_busca))[0, 1], 2))
    p("correlação log(cand)~log(t_busca) K2:",
      round(np.corrcoef(np.log(gr[gr.K == 2].candidatos), np.log(gr[gr.K == 2].t_busca))[0, 1], 2))
    p("razão t_busca K2/K1 (grandes) mediana:",
      round((gr[gr.K == 2].set_index('inst').t_busca / gr[gr.K == 1].set_index('inst').t_busca).median(), 2))
    p("escolas usadas / disponíveis K1, K2 (média %):",
      round((100 * agg[agg.K == 1].escolas / agg[agg.K == 1].n_escolas).mean(), 1),
      round((100 * agg[agg.K == 2].escolas / agg[agg.K == 2].n_escolas).mean(), 1))
    p("instâncias com escolas não utilizadas (média de escolas < disponíveis):",
      [(rotulo(r.inst), r.K, round(r.escolas, 1), int(r.n_escolas)) for r in agg.itertuples() if r.escolas < r.n_escolas - 1e-9])
    p("ocupação mín. média K1/K2 (%):", round(100 * agg[agg.K == 1].ocup_min.mean(), 1),
      round(100 * agg[agg.K == 2].ocup_min.mean(), 1))
    p("cauda max/med K1/K2 mediana:", round(agg[agg.K == 1].cauda.median(), 2), round(agg[agg.K == 2].cauda.median(), 2))
    g4 = agg[agg.inst.map(grupo) == GRUPO_ALVO]
    p("\n=== G4 ===")
    p(g4[["inst", "K", "inicial", "melhor", "media", "dp", "pior", "melh", "t_constr", "t_busca",
          "escolas", "ocup_min", "ocup_med", "dist_med", "dist_max", "cauda"]].round(3).to_string())
    p("G4: escolas usadas = 12 em todas as execuções:",
      bool((bruto[bruto.inst.map(grupo) == GRUPO_ALVO].escolas_usadas == 12).all()))
    (PASTA_FIG / "resumo_estatisticas.txt").write_text("\n".join(s), encoding="utf-8")
    print("\n".join(s))


def main():
    bruto, agg, info, todas, falhas = carrega_dados()

    viaveis = sorted(agg.inst.unique(), key=ordem_natural)
    # ordem comum aos gráficos por instância: da maior para a menor melhoria com K=2
    ordem = agg[agg.K == 2].sort_values("melh", ascending=False)["inst"].tolist()

    fig_melhoria(agg, ordem)
    fig_variabilidade(bruto, ordem)
    fig_tempo(agg)
    fig_solucao(agg, ordem)
    w, bloq, critica = fig_k1_vs_k2(agg)
    gera_tabela(agg, info, todas, falhas)
    resumo(agg, bruto, w, bloq, critica, falhas)


if __name__ == "__main__":
    main()