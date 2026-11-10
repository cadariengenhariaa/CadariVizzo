# Detecção de Interferências (Clash Detection)

Módulo independente do visualizador manual de issues (PDF/IFC) que
verifica automaticamente interferências entre disciplinas a partir dos
mesmos arquivos IFC já suportados pelo app, e gera relatório exportável
em PDF, XLSX, BCF 2.1 e JSON.

> **Importante**: nenhum valor numérico deste módulo (tolerâncias,
> folgas, severidades) é uma norma técnica. São estimativas de mercado
> marcadas no arquivo de regras como "padrão a validar pela equipe" — a
> equipe de projeto deve revisar e ajustar antes de confiar cegamente
> no relatório.

## Como usar

1. Abra **⚠ Clash Detection** na tela inicial do app.
2. **📂 Adicionar IFC(s)** — carregue um ou mais arquivos (um modelo de
   coordenação: arquitetura, estrutura, hidrossanitário, elétrica etc.).
3. **▶ Rodar Clash** — processa os modelos e lista as interferências na
   aba **Resultados**. Se aparecer um aviso de qualidade (unidades
   diferentes entre arquivos, modelos possivelmente desalinhados),
   leia com atenção antes de confiar na lista — ver [Pré-checagens](#pré-checagens-de-qualidade).
4. Selecione um item na lista para ver detalhes, mudar o **status**,
   atribuir um **responsável**, definir um **prazo** e escrever um
   **comentário**. **👁 Ver em 3D** abre o visualizador IFC com os dois
   elementos da interferência destacados (vermelho/azul) e a câmera
   enquadrada neles.
5. **💾 Exportar** — escolha o formato (PDF/XLSX/BCF/JSON) e,
   opcionalmente, filtre por disciplina/severidade/status antes de
   gerar o arquivo.

Também é possível rodar pela linha de comando, sem abrir o app:

```bash
python -m clash.cli modelo_arquitetura.ifc modelo_estrutura.ifc modelo_hidraulica.ifc
```

Use `--regras caminho/outro_regras.yaml` para usar um arquivo de regras
diferente do padrão, e `--nao-salvar` para só inspecionar o resultado
sem mesclar com a revisão anterior nem gravar `db_clashes.json`.

## Configurando as regras (`clash/regras_clash.yaml`)

Pode ser editado direto no arquivo (versionado em Git) ou pela aba
**Regras** da tela do app. Principais seções:

- **`disciplinas`**: o vocabulário de disciplinas usado pelo motor
  (mais granular que o `LISTA_DISCIPLINAS` das issues manuais, porque
  aqui é preciso diferenciar, por exemplo, Hidrossanitário de Gás e de
  Combate a Incêndio).
- **`tolerancia_hard_clash_m`**: penetrações menores que isso (metros)
  são ignoradas — ruído de modelagem, não uma interferência real.
- **`folga_padrao_m`** e **`matriz_disciplinas`**: qual folga mínima
  (metros) é exigida entre cada par de disciplinas, e se o par deve ser
  testado. Pares ausentes da matriz ainda são testados, com a folga
  padrão.
- **`severidade`**: lista de regras avaliadas em ordem — a primeira
  cujas condições baterem (`disciplina_a`, `disciplina_b`, `par`,
  `tipo`) define o nível (Crítica/Alta/Média/Baixa) da interferência.
  A última regra (`quando: {}`) é o padrão.
- **`ordem_rigidez_disciplinas`**: do mais rígido para o mais flexível
  — o responsável **sugerido** pela correção é sempre a disciplina mais
  flexível do par (Estrutura e SPDA raramente se movem). É só uma
  sugestão; a decisão final é da equipe.
- **`exclusoes`**: liga/desliga as exclusões automáticas (furos
  previstos, mesmo sistema, isolamento sobre o próprio duto) e a lista
  de GUIDs ignorados manualmente.
- **`duplicados`**: distância entre centros e diferença de volume ainda
  consideradas "o mesmo elemento duplicado".
- **`mapeamento_disciplina`**: como a disciplina de cada elemento é
  inferida (ver próxima seção).

## Como a disciplina de um elemento é inferida

Em ordem de prioridade (a primeira fonte que encontrar algo vence):

1. **Caminho do arquivo de origem** — um padrão (regex) configurável
   bate contra o caminho completo do IFC. Útil porque os arquivos já
   costumam vir organizados em pastas por disciplina
   (ex.: `.../1386-ARQ/...`, `.../1386-HID/...`).
2. **Propriedade explícita** num Pset do elemento (`Disciplina` ou
   `Discipline`).
3. **PredefinedType** do `IfcSystem`/`IfcDistributionSystem` ao qual o
   elemento está associado (ex.: `FIREPROTECTION` → PCI,
   `DOMESTICCOLDWATER` → HID).
4. **Classe IFC** do próprio elemento, como último recurso (ex.:
   `IfcBeam` → EST, `IfcDuctSegment` → CLIM).

Se nada bater, a disciplina vira **`OUTRO`** — o elemento é listado no
relatório, nunca descartado silenciosamente.

## Pré-checagens de qualidade

Rodadas automaticamente antes do clash propriamente dito, para não
gerar interferências enganosas:

- **Unidades**: cada arquivo é normalizado para metros antes de
  qualquer teste (`ifcopenshell.geom` não faz essa conversão sozinho).
  Um alerta aparece se os arquivos do modelo de coordenação usam
  unidades de comprimento diferentes entre si — vale a pena confirmar
  que não é um erro de exportação.
- **Desalinhamento**: se os modelos parecem fisicamente distantes uns
  dos outros (ex.: um arquivo georreferenciado e outro modelado perto
  da origem), um alerta aparece com a distância entre os centros.
- **GUIDs duplicados**, **elementos sem geometria**, **elementos sem
  pavimento associado** e **geometria inválida** (vértices não-finitos
  ou bounding box "achatado") são listados no resumo executivo do
  relatório.
- **Nomenclatura de pavimento**: se os arquivos não têm nenhum nome de
  pavimento em comum, um alerta indica que o filtro "por pavimento" do
  relatório pode não funcionar bem entre disciplinas.

## Tipos de interferência

- **`hard`** — interseção física real entre sólidos. Reporta a
  profundidade de penetração (sempre) e o volume exato de interseção
  quando o cálculo booleano é viável (`trimesh` + `manifold3d`).
- **`folga`** (soft clash) — distância medida entre os elementos menor
  que a folga mínima exigida para aquele par de disciplinas.
- **`duplicado`** — dois elementos da MESMA disciplina com centro e
  volume quase idênticos (checado antes de qualquer teste de colisão,
  para não aparecer também como hard clash).

## Exclusões automáticas

- **Furo previsto**: se um dos elementos é uma estrutura/vedação que já
  tem uma `IfcOpeningElement` (furo/passagem) no mesmo lugar onde o
  outro elemento passa, a interferência é descartada — o furo já estava
  previsto no projeto.
- **Mesmo sistema**: elementos que compartilham um `IfcSystem` em comum
  não geram hard clash entre si (aproximação — não verifica
  conectividade porta-a-porta).
- **Isolamento sobre o próprio duto**: um `IfcCovering` cujo bounding
  box contém quase inteiramente outro elemento é tratado como a camada
  de isolamento daquele próprio tubo/duto, não uma interferência real.
- **Exclusão manual**: GUIDs listados em
  `exclusoes.guids_aceitos_manualmente` nunca entram em nenhum teste.

## Rastreamento entre revisões

Cada interferência tem um **ID estável** (hash dos dois GUIDs + tipo),
que não muda entre rodadas mesmo que a ordem dos elementos no IFC mude.
A cada nova rodada, comparando com a revisão anterior salva
(`db_clashes.json`):

- **Novo** — nunca tinha aparecido antes.
- **Ativo** — já existia e continua sendo detectada; status, comentário
  e prazo são preservados.
- **Resolvido** — existia antes e não aparece mais nesta rodada (o
  elemento foi corrigido, movido ou removido).
- **Reaberto** — tinha sido marcada Resolvido/Aprovado/Aceito numa
  rodada anterior, mas voltou a ser detectada — nunca fica "Aceito" em
  silêncio depois de reaparecer.

O fluxo de status (editável pelo usuário, na aba Resultados) é: **Novo
→ Em análise → Atribuído → Resolvido → Aprovado**, ou **Aceito**
(sempre com justificativa no campo de comentário).

## Interpretando o relatório

O **resumo executivo** (início do PDF/XLSX, ou o campo
`resumo_executivo` do JSON) traz:

- Dados do projeto/arquivos analisados e o resultado das pré-checagens.
- Totais por severidade, status e tipo.
- Matriz disciplina x disciplina (quantas interferências por par).
- Distribuição por pavimento.
- Comparativo com a revisão anterior (Novo/Ativo/Resolvido/Reaberto).
- Top elementos (os GUIDs que aparecem em mais interferências — útil
  para achar um "problema sistêmico", como uma viga rebaixada cruzando
  várias tubulações).
- Pendências por disciplina responsável (sugerida) — **pendências**
  excluem o que já foi decidido como Aprovado/Aceito, mas esses itens
  continuam aparecendo na lista completa como "ativos".

Cada interferência no relatório traz uma **sugestão de ação** simples
(ex.: "desviar tubulação", "prever furo, consultar estrutura") e o
**responsável sugerido** — ambos são só sugestões automáticas baseadas
em regras simples, nunca uma decisão de projeto.

O **BCF 2.1** gerado pode ser aberto direto no Revit, Navisworks,
Solibri, BIMcollab etc. — cada tópico já vem com os dois elementos da
interferência selecionados e, quando possível, uma imagem 3D da cena.

## Limitações conhecidas (v1)

- "Mesmo sistema conectado" é aproximado por compartilhar um
  `IfcSystem`, não por conectividade real de porta a porta.
- A câmera do viewpoint BCF usa uma direção genérica — cada software
  BIM reenquadra automaticamente pela seleção de componentes ao abrir.
- O snapshot 3D mostra só os dois elementos da interferência, sem o
  restante do modelo ao redor, para manter a geração rápida em modelos
  grandes.
