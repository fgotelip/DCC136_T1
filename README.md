# DCC136 — Trabalho 1: localização de locais de prova

Heurística (construtivo + busca local) para o problema de alocação de candidatos a escolas de
prova, baseado em Oliveira, Martinelli Pinto e Milanez (2021). O objetivo é minimizar a distância
total percorrida pelos candidatos, respeitando a capacidade das salas, a compatibilidade entre
candidato e tipo de prova (uma sala só aplica um tipo) e o número máximo de tipos de prova por
escola (1 ou 2, escolhido na execução).

## Requisitos

- Python 3.9 ou mais novo
- numpy

```
pip install -r requirements.txt
```

## Como executar

Dentro da pasta `src/`:

```
python main.py Instancia1_G4.txt --max-tipos 1
python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10
```

Também funciona a partir da raiz do projeto (`python src/main.py ...`). O nome da instância pode ser
o caminho completo ou só o nome do arquivo: o programa procura também na pasta `instancias/`.

### Parâmetros

| Parâmetro | Padrão | Significado |
|---|---|---|
| `instancia` | (obrigatório) | arquivo da instância |
| `--max-tipos` | `1` | máximo de tipos de prova por escola: `1` ou `2` |
| `--execucoes` | `1` | quantas execuções da busca local, cada uma com uma semente diferente |
| `--semente-inicial` | `1` | semente da primeira execução (as seguintes usam +1, +2, ...) |
| `--limite-de-tempo` | `300` | tempo máximo, em segundos, de cada busca local |

O construtivo é determinístico (uma só execução). A busca local tem componente aleatório
(ordem em que testa os movimentos), por isso o parâmetro `--execucoes`: com várias sementes
o programa mostra média, desvio padrão, melhor e pior custo.

### Exemplo de saída

```
Instancia1_G4 | máximo de tipos por escola = 1
solução inicial: 15584.47 km (0.01s)
semente 1: 12533.80 km (melhoria 19.6%, 2.2s, 12 escolas usadas)
semente 2: 12452.33 km (melhoria 20.1%, 2.9s, 12 escolas usadas)
custo final: média 12493.07 | desvio padrão 40.74 | melhor 12452.33 | pior 12533.80
melhor solução salva em .../resultados/solucoes/Instancia1_G4_max1tipos.txt
```

### Reproduzir os experimentos do relatório

```
python main.py Instancia1_G4.txt --max-tipos 1 --execucoes 10
python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10
python main.py Instancia2_G4.txt --max-tipos 1 --execucoes 10
python main.py Instancia2_G4.txt --max-tipos 2 --execucoes 10
```

Com 1 tipo por escola cada execução leva poucos segundos; com 2 tipos, de 15 a 80 segundos
(Python 3.13, varia de máquina para máquina).

## Saídas

Tudo é gravado na pasta `resultados/`, na raiz do projeto (criada automaticamente):

- `resultados/tabela_resultados.csv`: uma linha por execução, com custo inicial, custo final,
  melhoria percentual, tempos do construtivo e da busca local, número de escolas usadas,
  ocupação mínima/média/máxima das escolas e distância média/máxima por candidato. **As linhas
  são acrescentadas** a cada execução do programa; apague o arquivo para recomeçar a tabela.
- `resultados/solucoes/<instancia>_max<K>tipos.txt`: a melhor solução encontrada, com o(s)
  tipo(s) de prova de cada escola e, para cada candidato, a escola, a sala (numeradas a partir
  de 1) e o tipo de prova. Esse arquivo é **sobrescrito** a cada execução da mesma instância
  e do mesmo `--max-tipos`.

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
| `src/main.py` | executa os experimentos e grava os resultados |
| `docs/construtivo.md` | descrição e justificativa do construtivo |
| `docs/busca_local.md` | função de avaliação, vizinhanças, busca e resultados |

Para testar só a solução inicial, sem a busca local: `python construtivo.py <instancia>` gera
a solução, mostra o resumo e verifica a viabilidade.