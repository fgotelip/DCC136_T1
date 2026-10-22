# Função de avaliação, busca local e experimentos

Arquivos: `busca_local.py` (a busca), `solucao.py` (custo, viabilidade, estatísticas) e
`main.py` (executa os experimentos).
Execução: `python main.py Instancia1_G4.txt --max-tipos 2 --execucoes 10`

## 1. Função de avaliação

**Custo de uma solução** = soma, sobre todos os candidatos, da distância (km) entre o candidato e a
escola onde foi alocado (`calcular_custo`). É o único componente do objetivo, como o enunciado
descreve para estas instâncias.

**Soluções inviáveis: não há função de penalização.** A busca local **nunca sai do espaço de
soluções viáveis**: cada movimento só é aplicado se o resultado respeita todas as restrições
(capacidade das salas, tipo de prova compatível, uma sala com um só tipo, máximo de tipos por
escola). Por isso não há restrição violável nem peso de penalidade a justificar. Duas razões para
essa escolha:

- as instâncias têm folga de capacidade (cerca de 15%), então sempre existem movimentos viáveis;
- uma penalidade exigiria calibrar um peso (ele teria que ser maior que a maior distância da
  matriz, cerca de 13 km, para nunca compensar violar), sem ganho aparente aqui.

A função `verificar_viabilidade` confere a solução inteira ao final de cada execução; o `main.py`
interrompe se encontrar qualquer violação.

## 2. Estruturas de vizinhança

A solução é vista por escola e por tipo: `capacidade[escola][tipo]` (soma das salas daquele tipo na
escola) e `ocupacao[escola][tipo]` (candidatos alocados). Dentro de uma escola, os candidatos de
um tipo podem ocupar quaisquer salas daquele tipo, então a sala só é decidida no final
(`preencher_salas`).

| # | Vizinhança | Movimento | Viabilidade |
|---|---|---|---|
| 1 | **Realocar** | um candidato vai para uma escola mais próxima que ainda tem vaga do tipo dele | só entra em escola com `ocupacao < capacidade` |
| 2 | **Trocar** | dois candidatos do mesmo tipo trocam de escola | a ocupação de cada escola não muda |
| 3 | **Mudar tipos** | máximo 1 tipo por escola: duas escolas de tipos diferentes trocam de tipo. Máximo 2: o tipo de **uma sala** muda | confere a capacidade total do tipo e o limite de tipos por escola (ver 3) |

**Por que essas três.** Realocar e trocar melhoram a atribuição de candidatos com os tipos das
salas fixos. Realocar aproveita vagas livres; trocar resolve o caso de escolas cheias, em que
não há vaga para realocar. Já mudar tipos é o que altera a estrutura da solução (quem atende cada
tipo), que as duas primeiras não conseguem mudar, e é onde está a maior parte do ganho
(seção 6). A mudança por **sala** é o que aproveita o limite de 2 tipos por escola.

## 3. Mudança de tipos (vizinhança 3)

Para cada mudança candidata:

1. Muda o tipo das salas e atualiza `capacidade`. Se a capacidade total de algum tipo afetado
   não cobre mais os candidatos dele, desfaz.
2. **Desaloja**, em cada escola e tipo afetados, o excesso de candidatos (os mais distantes dela).
3. **Recoloca** os desalojados com a mesma alocação gulosa do construtivo (arrependimento
   decrescente, escola mais próxima com vaga), usando só as vagas livres. Se mais de 25% dos
   candidatos do tipo foram desalojados, o tipo inteiro é realocado do zero (caso típico no
   máximo de 1 tipo por escola, em que uma escola inteira muda de tipo).
4. Roda realocar e trocar nos tipos afetados até estabilizar, para aproveitar as vagas novas.
5. **Aceita** se o custo total diminuiu; senão **desfaz** (restaura uma cópia do estado).

## 3.1 Estratégia de busca

Procura de **primeira melhoria**, em níveis:

```
repetir:
    repetir realocar + trocar até nenhum melhorar      (vizinhanças baratas)
    percorrer, em ordem sorteada, as mudanças de tipo possíveis
        aplicando cada uma que melhorar                (vizinhança cara)
    se nenhuma mudança de tipo foi aceita: parar        (ótimo local nas 3 vizinhanças)
```

Para quando as três vizinhanças não melhoram mais, ou quando passa o limite de tempo
(`--limite-de-tempo`, padrão 300 s; as soluções continuam viáveis se o limite for atingido).

## 4. Componente aleatório

A ordem em que as mudanças de tipo são testadas e a ordem dos candidatos em realocar são
sorteadas (`--semente-inicial` e `--execucoes` controlam as sementes). O construtivo e a
vizinhança de troca são determinísticos. Como a solução final depende da ordem, o `main.py`
roda várias sementes e reporta média, desvio padrão, melhor e pior custo.

## 5. Experimentos

O `main.py` grava, para cada execução, uma linha em `resultados/tabela_resultados.csv`
(custos inicial e final, melhoria percentual, tempos do construtivo e da busca, escolas usadas,
ocupação mínima/média/máxima e distância média/máxima por candidato) e salva a melhor solução em
`resultados/solucoes/` (tipo(s) de cada escola e, para cada candidato, escola, sala e tipo).

## 6. Resultados (10 sementes por configuração; custos em km)

| Instância | Tipos por escola | Custo inicial | Custo final: média ± desvio | Melhor | Pior | Melhoria média | Tempo médio da busca |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 15584,47 | 12473,79 ± 69,51 | 12362,94 | 12601,35 | 20,0% | 2,9 s |
| 1 | 2 | 15584,47 | 10222,62 ± 703,85 | 8851,44 | 11286,81 | 34,4% | 111,7 s |
| 2 | 1 | 11838,54 | 9902,84 ± 42,02 | 9867,92 | 9988,39 | 16,4% | 2,8 s |
| 2 | 2 | 11838,54 | 8945,42 ± 607,50 | 8216,10 | 9920,12 | 24,4% | 40,1 s |

Todas as soluções finais passaram na verificação de viabilidade. Em todas, as 12 escolas são
usadas. A ocupação média das escolas fica em torno de 85%, e a distância máxima de um candidato
até sua escola fica em torno de 10 a 11,5 km. Os tempos foram medidos em Python 3.13 com
numpy; mudam de máquina para máquina.

- **Efeito do limite de tipos:** permitir 2 tipos por escola reduz bem o custo, mas também
  deixa o resultado mais variável (desvio padrão de 607 a 704 km contra 42 a 70 km com 1 tipo).
- **Tempo:** com 2 tipos o espaço de mudanças é bem maior (uma por sala e por tipo, cerca de 700
  contra 66 pares de escolas), o que explica o tempo maior.
- **Efeito da polarização espacial (Instância 1 vs. Instância 2):** na Instância 1 (base), os
  candidatos de todos os tipos estão espalhados uniformemente pelas zonas da cidade. Já na
  Instância 2 (diferenciada), os candidatos de `M1` estão concentrados na Zona Sul e os de `M2`
  na Zona Norte. Essa concentração geográfica explica por que a Instância 2 apresenta custos
  substancialmente menores desde o construtivo (11838,54 km contra 15584,47 km): escolas inteiras
  alocadas na Zona Sul para `M1` e na Zona Norte para `M2` já atendem esses perfis com
  deslocamentos curtos, exigindo menos reestruturação na busca local (ganho médio de 16,4% e
  24,4% na Instância 2 contra 20,0% e 34,4% na Instância 1).

## 7. Limitações

- **Ótimo local:** a busca para no primeiro ponto em que nenhuma das três vizinhanças melhora.
  Com 2 tipos, execuções diferentes terminam em custos bem diferentes (instância 2: de 8216 a
  9920 km). Seria preciso rodar várias sementes e ficar com a melhor, ou acrescentar reinícios ou
  perturbações.
- **Mudança de tipos testada de uma em uma:** não há movimentos que combinem várias salas ou
  escolas além da troca de tipos de duas escolas (máximo 1 tipo).
- **Desalojamento guloso:** escolher quem sai da escola (os mais distantes) e recolocar com
  a heurística gulosa pode rejeitar mudanças que, com outra reorganização, seriam boas.
- **Escolas com baixa ocupação:** a ocupação da escola menos ocupada ficou entre 30% e 47%, pois o
  objetivo não tem custo fixo por escola e prefere atender candidatos mais perto.
