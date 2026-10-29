# DCC136 — Trabalho 1: localização de locais de prova

Heurística (construtivo + busca local) para o problema de alocação de candidatos a escolas de
prova, baseado em Oliveira, Martinelli Pinto e Milanez (2021). O objetivo é minimizar a distância
total percorrida pelos candidatos, respeitando a capacidade das salas, a compatibilidade entre
candidato e tipo de prova (uma sala só aplica um tipo) e o número máximo de tipos de prova por
escola (1 ou 2, escolhido na execução).

## Requisitos

- Python 3.9 ou mais novo
- numpy
- pandas e matplotlib (só para gerar os gráficos e a tabela do relatório)

```
pip install -r requirements.txt
```

## Como executar

Tudo é feito pelo `src/main.py`, que tem dois modos. Rode a partir da pasta `src/` (também funciona
da raiz do projeto, com `python src/main.py ...`).

### Modo 1 — uma instância

```
python main.py Instancia1_G4.txt --max-tipos 1
python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10
python main.py Instancia1_G4.txt --max-tipos 1 2 --execucoes 10     # os dois K de uma vez
```

O nome da instância pode ser o caminho completo ou só o nome do arquivo: o programa procura também
na pasta `instancias/`. Os resultados são **acrescentados** em `resultados/tabela_resultados.csv`.

### Modo 2 — lote (todas as instâncias de um zip, em paralelo)

**Comando para rodar tudo** (2 valores de K, 10 execuções cada, 4 instâncias em paralelo):

```
python main.py --zip ../drive-download.zip --jobs 4
```

Troque `../drive-download.zip` pelo caminho do zip com as instâncias e ajuste `--jobs` para o número de
núcleos da sua máquina. O zip pode ter zips dentro; nomes como `Instancia1_G7(1).txt` e
`instancia_2_G13.txt` são reconhecidos (se houver arquivos repetidos, vale o maior).
Outros exemplos:

```
python main.py --zip ../drive-download.zip --jobs 4 --so-instancias Instancia1_G4 Instancia2_G4
python main.py --zip ../drive-download.zip --jobs 4 --max-tipos 1          # só K=1
python main.py --zip ../drive-download.zip --jobs 4 --refazer-falhas       # tenta de novo o que falhou
```

- **Retomada:** o lote pode ser interrompido (Ctrl+C) e rodado de novo com o mesmo comando. O que já
  foi calculado (lido de `resultados_lote/lote.zip` e da pasta `lote/`) é pulado.
- **Falhas:** uma (instância, K) que falhou não é refeita na retomada (o construtivo é determinístico);
  use `--refazer-falhas` para forçar uma nova tentativa.
- Com `--jobs` maior que 1 os tempos medidos ficam maiores (as instâncias disputam a CPU). Para tempos
  fiéis use `--jobs 1`.

### Parâmetros

| Parâmetro | Padrão | Significado |
|---|---|---|
| `instancia` | — | arquivo da instância (modo 1) |
| `--zip` | — | zip com as instâncias; **liga o modo lote** (modo 2) |
| `--max-tipos` | `1` (modo 1) / `1 2` (modo 2) | máximo(s) de tipos de prova por escola; aceita `1`, `2` ou `1 2` |
| `--execucoes` | `1` (modo 1) / `10` (modo 2) | execuções da busca local, cada uma com uma semente diferente |
| `--semente-inicial` | `1` | semente da primeira execução (as seguintes usam +1, +2, ...) |
| `--limite-de-tempo` | `300` | tempo máximo, em segundos, de cada busca local |
| `--limite-nos` | do construtivo (modo 1) / `5000000` (modo 2) | limite de nós do backtracking do construtivo |
| `--jobs` | `1` | modo 2: instâncias em paralelo |
| `--saida` | `resultados_lote/` | modo 2: pasta de saída |
| `--so-instancias` | todas | modo 2: roda só estas, ex.: `Instancia1_G4 Instancia2_G4` |
| `--refazer-falhas` | desligado | modo 2: refaz as (instância, K) que falharam antes |

O construtivo é determinístico (uma só execução). A busca local tem componente aleatório
(ordem em que testa os movimentos), por isso o parâmetro `--execucoes`.

### Reproduzir os experimentos do relatório

```
python main.py Instancia1_G4.txt --max-tipos 1 2 --execucoes 10
python main.py Instancia2_G4.txt --max-tipos 1 2 --execucoes 10
```

Com 1 tipo por escola cada execução leva poucos segundos; com 2 tipos, de 15 a 80 segundos
(Python 3.13, varia de máquina para máquina).

## Saídas

### Modo 1 (pasta `resultados/`, na raiz do projeto)

- `tabela_resultados.csv`: uma linha por execução, com custo inicial, custo final, melhoria
  percentual, tempos do construtivo e da busca local, número de escolas usadas, ocupação
  mínima/média/máxima das escolas e distância média/máxima por candidato. **As linhas são
  acrescentadas** a cada execução; apague o arquivo para recomeçar a tabela.
- `solucoes/<instancia>_max<K>tipos.txt`: a melhor solução encontrada, com o(s) tipo(s) de prova de
  cada escola e, para cada candidato, a escola, a sala (numeradas a partir de 1) e o tipo de prova.
  É **sobrescrito** a cada execução da mesma instância e do mesmo K.

### Modo 2 (pasta `resultados_lote/`, ou a indicada em `--saida`)

| Arquivo | Conteúdo |
|---|---|
| `lote.zip` | um csv por (instância, K), com as mesmas colunas da `tabela_resultados.csv`. A pasta `lote/` onde eles são gerados é apagada depois do zip |
| `resultados_completos.csv` | junção de todos os csv: uma linha por execução, sem resumir, no escopo da `tabela_resultados.csv` |
| `planilha_K1.csv` | uma linha por instância (K=1), na ordem da planilha do trabalho: Instancia1_G1…G14 e depois Instancia2_G1…G14 |
| `planilha_K2.csv` | o mesmo para K=2 |
| `solucoes/` | a melhor solução de cada (instância, K) |
| `progresso.log` | andamento: início, construtivo, cada semente, final de cada K e um resumo das falhas |
| `falhas.log` | detalhe de cada falha: etapa, erro, dados da instância (candidatos, escolas, capacidade, demanda por tipo) e traceback |
| `instancias/` | instâncias extraídas do zip |
| `tabela_resultados.tex` e `figuras/` | tabela e gráficos do relatório, gerados por `src/gerar_graficos.py` (veja a seção abaixo) |

**Colunas de `planilha_K<k>.csv`:** `instancia`, **`melhor_resultado`, `media_dos_resultados`,
`tempo_medio_s`** (as 3 colunas para copiar e colar na planilha; o tempo é construtivo + busca local),
e depois `pior_resultado`, `desvio_padrao`, `custo_inicial`, `tempo_construtivo`, as médias das demais
métricas (`media_melhoria_percentual`, `media_tempo_busca_local`, `media_escolas_usadas`,
`media_ocupacao_*`, `media_distancia_*`) e `execucoes`.

**Falhas na planilha:** se uma instância falhou, a mensagem do erro (etapa + tipo do erro + texto) aparece
nas 3 colunas de colar; se não há arquivo da instância no zip, aparece `NAO EXECUTADA`.
Os possíveis erros são: leitura da instância, construtivo (por exemplo, não conseguir cobrir a demanda
de todos os tipos de prova), busca local, solução inviável e falha ao gravar a solução. O progresso do
lote aparece na tela e em `progresso.log`; o `falhas.log` guarda o traceback.

Formato do arquivo de solução:

```
# TIPO(S) DE PROVA DE CADA ESCOLA
E1: M2, M3e
E2: M1, M3e
...

# ALOCAÇÃO (candidato, escola, sala, tipo de prova)
C1, E1, 2, M3e
C2, E5, 7, M2
...
```

## Gráficos e tabela do relatório

O script `src/gerar_graficos.py` lê os resultados do lote (`resultados_lote/resultados_completos.csv` e
`planilha_K1.csv`) e gera, na própria pasta `resultados_lote/`, tudo o que a seção de experimentos do
relatório usa. Rode depois do modo lote (modo 2):

```
python src/gerar_graficos.py
```

| Saída | Conteúdo |
|---|---|
| `resultados_lote/tabela_resultados.tex` | tabela única com as 28 instâncias, K=1 e K=2 lado a lado (inicial, melhor, média ± desvio, pior, melhoria, tempos, execuções que pararam no limite de tempo, escolas usadas, ocupação e distâncias) |
| `resultados_lote/figuras/fig_melhoria.pdf` | melhoria percentual por instância, com desvio entre sementes |
| `resultados_lote/figuras/fig_variabilidade.pdf` | custo final / custo inicial em cada semente (boxplot) |
| `resultados_lote/figuras/fig_tempo.pdf` | tempo de construção e de busca vs. candidatos e salas, e ganho vs. tempo |
| `resultados_lote/figuras/fig_solucao.pdf` | ocupação mínima das escolas e razão distância máxima / média |
| `resultados_lote/figuras/fig_k1_vs_k2.pdf` | K=1 vs. K=2 e o efeito da folga de capacidade (Seção 5.2) |
| `resultados_lote/figuras/resumo_estatisticas.txt` | números citados no texto do relatório |
| `resultados_lote/figuras/info_instancias.csv` | cache com candidatos, escolas e salas de cada instância (apague para recalcular) |

Observações:

- Os nomes das instâncias são normalizados (por exemplo, `instancia_1_G13` e `Instancia1_G7(1)`
  viram `Instancia1_G13` e `Instancia1_G7`). Instâncias que falharam na construção aparecem como
  "inviável" na tabela e ficam fora dos gráficos.
- O desvio padrão é populacional, e o limite de tempo considerado é o padrão de 300 s
  (constante `LIMITE_TEMPO` do script).

## Formato da instância

Arquivo de texto com as seções `# CANDIDATOS`, `# ESCOLAS` e `# MATRIZ_DISTANCIAS` (linhas =
candidatos, colunas = escolas, em km), como nas instâncias fornecidas. O número de escolas,
de salas e de tipos de prova é lido do arquivo, não é fixo no código.

## Organização do código

| Arquivo | O que faz |
|---|---|
| `src/instancia.py` | lê o arquivo da instância |
| `src/solucao.py` | representação da solução, custo, verificação de viabilidade, estatísticas |
| `src/construtivo.py` | heurística construtiva (solução inicial) |
| `src/busca_local.py` | busca local com três vizinhanças |
| `src/main.py` | executa os experimentos (uma instância ou lote), grava os csv, o zip e os logs |
| `src/gerar_graficos.py` | gera os gráficos e a tabela do relatório a partir dos resultados do lote |
| `relatorios/` | relatório em LaTeX (SBC) e slides |
| `docs/construtivo.md` | descrição e justificativa do construtivo |
| `docs/busca_local.md` | função de avaliação, vizinhanças, busca e resultados |

Para testar só a solução inicial, sem a busca local: `python construtivo.py <instancia>` gera
a solução, mostra o resumo e verifica a viabilidade.