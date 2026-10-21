# Heurística construtiva — solução inicial

Arquivos: `solucao.py` (representação, custo, verificação) e `construtivo.py` (a heurística).
Execução: `python construtivo.py Instancia1_G4.txt`

## 1. Representação da solução

| Campo | Significado |
|---|---|
| `tipo_sala[indice_escola][indice_sala]` | tipo de prova da sala |
| `escola_candidato[indice_candidato]` | escola do candidato |
| `sala_candidato[indice_candidato]` | sala (dentro da escola) do candidato |

O tipo de uma escola é o conjunto dos tipos das suas salas. Assim, "cada sala só tem um tipo"
vale por construção, e o limite de tipos por escola (1 ou 2) é conferir o tamanho desse conjunto.

**Função objetivo:** soma das distâncias (km) entre cada candidato e a escola onde foi alocado.

## 2. Ideia central: duas fases

Cada candidato ocupa **uma vaga** e só disputa vaga com candidatos **do mesmo tipo**. Então:

- **Fase 1 — tipo de cada escola.** Todas as salas da escola recebem o mesmo tipo. É a fase
  difícil: para cada tipo, a soma das capacidades das escolas daquele tipo precisa cobrir
  todos os candidatos dele.
- **Fase 2 — candidatos.** Aloca cada candidato a uma escola do tipo dele. Se a fase 1 cobriu
  todos os tipos, **a fase 2 sempre consegue alocar todo mundo**.

A solução inicial usa **um tipo por escola**, que é viável tanto para o limite de 1 quanto
para o de 2 tipos por escola. Dividir as salas de uma escola entre dois tipos é papel da
busca local (vizinhança de troca de tipo de sala).

## 3. Fase 1 — critério para selecionar os tipos (locais)

**Custo estimado** de a escola atender um tipo: distância média dos candidatos daquele tipo que
estão mais perto da escola (tantos quanto a capacidade da escola comporta).

**Busca com retrocesso:**

1. As escolas são percorridas da **maior para a menor capacidade** (as grandes decidem mais a
   cobertura, e errar nelas aparece cedo).
2. Para cada escola, tenta-se os tipos do **mais barato para o mais caro**.
3. Ao dar um tipo à escola, a capacidade dela é descontada da demanda ainda sem cobertura daquele tipo.
4. **Poda:** se a capacidade das escolas que restam não cobre mais o que falta (soma das
   demandas sem cobertura), volta atrás e tenta o próximo tipo.
5. Terminadas todas as escolas, a solução é aceita se a demanda de todos os tipos foi coberta.
   Limite de 200 mil nós; se estourar, o programa avisa que não conseguiu cobrir a demanda.

Todas as escolas recebem tipo, inclusive as que não eram necessárias para a cobertura: não há
custo fixo por escola, então capacidade extra nunca piora a distância total.

## 4. Fase 2 — ordem dos candidatos e alocação

Os tipos são tratados separadamente:

1. **Ordem dos candidatos:** por **arrependimento decrescente** = distância até a 2ª escola mais
   próxima do tipo menos a distância até a mais próxima. Quem mais perde ao ser mandado
   para longe é atendido primeiro. Empate: ordem do arquivo.
2. **Alocação:** cada candidato vai para a escola **mais próxima que ainda tem vaga**.
3. **Salas:** dentro de cada escola, os candidatos vão enchendo as salas em ordem, uma sala
   cheia por vez.

## 5. Como cada restrição é tratada

| Restrição | Como é garantida |
|---|---|
| **Capacidade** | A fase 2 só aloca enquanto há vaga na escola; as salas são enchidas até a capacidade de cada uma. |
| **Compatibilidade candidato × tipo de prova** | O candidato só considera escolas do tipo dele, e todas as salas de uma escola têm o mesmo tipo. |
| **Uma sala, um tipo** | `tipo_sala` guarda um único tipo por sala. |
| **Máximo de tipos por escola** | A solução inicial usa 1 tipo por escola, que respeita o limite de 1 e o de 2. |

## 6. Escolha atrativa que dificulta a solução completa

O risco está na fase 1: dar o tipo mais barato a uma escola grande pode deixar outro tipo sem
escolas suficientes. A busca com retrocesso trata isso: a **poda** detecta cedo que a cobertura
ficou impossível, e o **retrocesso** desfaz a escolha e tenta o próximo tipo mais barato.
O mesmo mecanismo que escolhe pelo custo também garante a viabilidade, sem etapa de reparo separada.

## 7. Resultados (instâncias do G4)

| Instância | Custo inicial (km) | Média (km/candidato) | Tempo | Viável |
|---|---|---|---|---|
| 1 (3995 candidatos) | 15584,47 | 3,90 | 0,03 s | sim |
| 2 (3970 candidatos) | 11838,54 | 2,98 | 0,01 s | sim |

O construtivo é determinístico, então uma execução por instância basta.

**Teste de robustez.** Em 600 instâncias sintéticas apertadas (8 escolas, 3 tipos, folga de 0,
5 ou 15 vagas por tipo) a heurística achou solução viável em todas, com no máximo 0,01 s por
instância.

## 8. Limitações conhecidas

- **Só um tipo por escola:** com limite de 2 tipos, o construtivo não aproveita a divisão de
  salas; isso fica para a busca local. Se a instância tiver menos escolas que tipos de prova,
  o construtivo não acha solução (cada tipo precisa de pelo menos uma escola inteira).
- **Estimativa simples:** o custo estimado ignora a competição entre escolas pelos mesmos
  candidatos, então a ocupação pode ficar desbalanceada.
- **Ordem estática:** o arrependimento da fase 2 é calculado uma vez, não é atualizado conforme
  as escolas enchem.
- **Limite de nós:** em instâncias muito apertadas, a busca pode estourar o limite e o
  construtivo avisa que não conseguiu cobrir a demanda (não devolve solução inviável).
