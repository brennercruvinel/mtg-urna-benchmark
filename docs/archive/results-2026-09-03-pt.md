<!-- archived: superseded, kept verbatim as the historical record -->

> **superseded.** this is the hand-written report of 2026-09-03 (in portuguese), kept verbatim
> as the record of how the numbers were first read. the maintained results are generated into
> `RESULTS.md` from `benchmark/experiments/*/results.json`; where the two disagree, the json wins.
> the only edit below is the section 6 heading: the machine-local data path was replaced by
> `${MTG_DATA}` so no tracked file names a machine.
>
> unit and provenance errors found in the 2026-09-11 audit and corrected in the generated report:
>
> - sec 8: "jxl-transcode -e 7 | 1.124x" is 1.115x (211018809 / 189231744); 1.124x belongs to -e 9. the prose "-11.1%" is e9 (-11.0%), e7 is -10.3%. "perde por 3.3-3.8x" is against the source jpeg; against jxl e9 the lossless video rows lose 3.7x to 4.3x.
> - sec 13: "retrieval-only (crf40) | 0.935 GB" is MiB labelled GB; the file is 980715452 bytes = 0.981 GB. "4.22x" is the media-only ratio (3975063106 / 941331425); on the .urna it is 4.05x, while the other rows of the same table use .urna bytes. "-31% vs o still" is -27.7% with correct bytes; "-74% vs a fonte (4.22x)" is inconsistent with itself (4.22x means -76.3%; correct .urna ratio gives -75.3%; -74% is against the archive, not the source).
> - sec 14: "crf50 | 0.508 GB | 7.82x" and "crf50: 508 MB" are MiB; the file is 532671548 bytes = 0.533 GB, 7.46x on the .urna (8.06x media only). "avif q48 | 1.101 GB | 3.61x": the .urna is 1195973116 bytes = 1.196 GB (3.32x; 3.45x media only); 1.101 is most likely the media blob in MiB. "-20% de bytes (1.101 vs 1.374 GB)" is -13.0% on .urna bytes (-13.6% media vs media), so the claim that the i-frame prediction (-12.4%) "materialized larger" does not hold; it came out about equal.
> - sec 6: "6.9 GB" and "3.0 GB" are GiB from du (allocated blocks); the sum of file sizes is 7201468217 bytes for images/ and 3107627150 for art_crop/. "~2.800 imagens orfas por classe" is wrong: those are the back faces, referenced by cards.image_uri_back (2824 rows); the true front orphans are 3 (38630 stems vs 38627 cards). the jsonl.gz files no longer exist.
> - sec 9: "difere pouco no g unico (1.8pt)" is 1.8 MB (96.8 - 95.0); in percentage points vs intra it is 1.5 pp. the matrix compares bytes at fixed crf and is not quality matched.
> - sec 5 vs sec 12: the same still file is quoted at 3.02x (media bytes) and 2.93x (urna bytes); the generated report always shows both ratios. sec 12 names the file mtgdataset.urna but it was built as spellbook.urna (chunker_version spellbook/1 inside).
> - sec 2 and header: "seed 42" is a provenance error; the 2048-card sample is evenly spaced (rows[int(i * 38627 / 2048)] over rows sorted by (img_id, oracle_id)) and seed independent. the table omits three measured variants (selfcontained-neardup, selfcontained-jxl-transcode, selfcontained-avif) that the generated report carries.
> - measurements.json and the avif candidate manifest: avif source_bytes (1138810355 on the sample, 21450566470 on the full corpus, ratio 18.61) are the letterboxed png intermediates, an avif backend bug in the urna forge; the ratios in the tables always use the jpeg source.
> - sec 8 also points at `benchmark/sample-2048/lossless/jxl-e9/`, which was deleted after measurement; only the results record survived (now `benchmark/experiments/08-lossless/battery.json`).

# MTG dataset compression benchmark

Data: 2026-08-31. Pipeline: `urna build --spec`, um TOML por variante em `benchmark/sample-2048/specs/`, saidas em `benchmark/sample-2048/runs/<variante>/`. Amostra: 2048 cartas, seed 42, deterministica e identica em todas as variantes.

Metodologia de qualidade: 96 frames amostrados (seed 7), medidos uniformemente em duas dimensoes — SSIMULACRA2 (fonte letterboxed vs frame decodificado) e deriva de cosseno CLIP (embedding da fonte vs embedding do decodificado). Sao as mesmas duas metricas do gate `crf=auto`. Medidor: `benchmark/sample-2048/measure_variants.py`; dados brutos: `benchmark/sample-2048/measurements.json`; tabela regeneravel por `benchmark/sample-2048/render_report.py`.

## 1. Baselines de arquivamento

Mesmos 2048 JPEGs fonte (211.0 MB).

| baseline      |    MB | ratio |
|---------------|------:|------:|
| fonte (JPEG)  | 211.0 | 1.00x |
| tar           | 216.8 | 0.97x |
| tar + zstd-19 | 210.0 | 1.00x |

Arquivadores genericos nao comprimem JPEG. Qualquer ganho vem de codec de imagem/video.

## 2. Variantes

| variante              | midia MB | ratio | arquivos | encode s | ssim2 p50 | p10  | min  | deriva clip p10 | sem perda |
|-----------------------|---------:|------:|---------:|---------:|----------:|-----:|-----:|----------------:|-----------|
| control (PNG)         |   1138.8 | 0.19x |     2048 |     33.9 |     100.0 | 100.0| 100.0|          1.0000 | bytes     |
| jxl-transcode         |    189.2 | 1.12x |     2048 |     74.7 |      92.8 | 91.3 | 88.2 |          0.9969 | bytes [1] |
| jxl-lossless          |    189.2 | 1.12x |     2048 |     43.4 |      92.8 | 91.3 | 88.2 |          0.9969 | pixels [1]|
| av1-v02-crf35-s8      |     63.6 | 3.32x |        1 |     13.8 |      51.8 | 44.0 | 34.1 |          0.9549 | nao       |
| av1-still-s6-crf35    |     70.1 | 3.01x |        1 |     36.4 |      62.7 | 55.7 | 45.3 |          0.9651 | nao       |
| av1-fps30-intra-crf35 |     70.1 | 3.01x |        1 |     45.6 |      62.7 | 55.7 | 45.3 |          0.9651 | nao       |
| av1-inter-crf35       |     82.6 | 2.55x |        1 |     38.0 |      62.1 | 53.1 | 41.8 |          0.9698 | nao       |
| av1-fps30-inter-crf35 |     82.6 | 2.55x |        1 |    116.9 |      62.1 | 53.1 | 41.8 |          0.9698 | nao       |
| av1-cluster-crf35     |     70.1 | 3.01x |        1 |     95.6 |      62.7 | 55.7 | 45.3 |          0.9651 | nao       |
| av1-auto-dualgate     |     93.9 | 2.25x |        1 |     69.2 |      70.6 | 65.3 | 58.6 |          0.9674 | nao       |
| avif-crf35            |     38.5 | 5.48x |     2048 |     77.3 |      43.4 | 34.1 | 17.8 |          0.9566 | nao       |
| selfcontained-still-s6|     70.1 | 3.01x |        1 |     37.3 |      62.7 | 55.7 | 45.3 |          0.9651 | nao       |

Descricao das variantes:

- control: letterbox PNG sem perda; regua de referencia.
- jxl-transcode: `cjxl --lossless_jpeg=1`; JPEG original reconstrutivel bit-exato, 2048/2048 round-trips verificados por sha256 no build.
- jxl-lossless: `cjxl -d 0` sobre a fonte.
- av1-v02-crf35-s8: replica do build v0.2 (crf 35, speed 8, tune default; 1.86 GB no corpus completo da geracao anterior).
- av1-still-s6-crf35: isola tune=still + speed 6, mesmo crf.
- av1-fps30-intra-crf35: isola fps=30 em all-intra (verificacao da observacao de campo sobre aceleracao de video).
- av1-inter-crf35 / av1-fps30-inter-crf35: predicao inter, ordem da fonte, com e sem fps=30.
- av1-cluster-crf35: ordenacao semantica por CLIP (order=cluster) + probe de gop por segmento.
- av1-auto-dualgate: crf escolhido pelo gate duplo; caiu em crf=30.
- avif-crf35: baseline por-imagem via avifenc.
- selfcontained-still-s6: mesmas configuracoes do still-s6, com a midia embutida no proprio .urna (`embed_media = true`, secao 0x17). Arquivo unico de 72.2 MB (midia 70.1 + 2.1 de indices/vetores/texto).

[1] O ssim2 92.8 do jxl e artefato de medicao, nao perda do codec: PIL e djxl decodificam o mesmo JPEG com arredondamentos diferentes. A reversibilidade do transcode e bit-exata, verificada por sha256 no build (2048/2048).

## 3. Conclusoes

1. tar+zstd-19 sobre JPEG rende 1.00x. A compressao util vem exclusivamente do codec.
2. jxl-transcode e a unica compressao sem perda real sobre fontes JPEG: -10.3% com reversibilidade bit-exata verificada. Qualquer ganho maior e com perda, e a tabela quantifica quanto.
3. tune=still e o upgrade imediato sobre o v0.2: +10.9 pontos de ssim2 p50 (51.8 para 62.7) por +10% de bytes, no mesmo crf. O v0.2 (crf35/speed8/tune default) era o pior ponto da curva qualidade-por-byte.
4. fps nao altera bytes: fps30-intra e still-s6 sao byte-identicos. A reducao de ~50% observada no teste de campo veio de re-encodar midia ja comprimida (perda geracional); o caminho correto para o mesmo tamanho e subir o crf a partir da fonte, com qualidade superior. O experimento expos um bug real: `decode_frame` assumia fps=1 no acesso aleatorio a frame; corrigido nesta sessao (fps flui do manifest ao seek).
5. inter e cluster nao pagam neste corpus: inter custa +18% de bytes com qualidade inferior (cartas distintas equivalem a scene-cut por frame); a ordenacao semantica foi aplicada (permutacao registrada no manifest) mas o probe de gop escolheu intra, ganho ~0 — como o RFC-2 previa para corpus 1-por-oracle. A alavanca permanece para datasets com quase-duplicatas (scans, frames de video, catalogos de produto).
6. avif-crf35 nao e comparavel ponto-a-ponto: a escala de qualidade do avifenc nao corresponde ao crf do SVT-AV1; 5.48x com p10=34.1 e outro ponto da curva, nao um vencedor.
7. crf=auto caiu no menor crf da ladder: os floors (visual_floor_p10=85, visual_floor_min=72) sao inatingiveis para cartas 488x680 yuv420. Pendencia: recalibrar floors por classe de corpus, ou estender a ladder abaixo de 30.
8. O custo do single-file e +3.0% sobre a midia: 2048 cartas em um unico .urna de 72.2 MB com busca offline; `urna media --export` reconstroi o mp4 com verificacao de hash.

## 4. Default recomendado

Corpora de imagens distintas: `backend=av1, tune=still, speed=6, crf=35, gop=intra`, shard unico, `dedup=true`, `embed_media=true`.
Exigencia de reversibilidade bit-exata: `backend=jxl-transcode`.
Corpora com quase-duplicatas: adicionar `order=cluster, gop=auto` (o probe decide por segmento).

## 5. Corpus completo (38.627 cartas)

Receita recomendada (`mtgdataset-v03.toml`). Build: 18 min (encode 723 s, clip 292 s, potion 3 s).

| metrica                    | v0.2 (legacy-v02/)                                            | v0.3 self-contained                                  |
|----------------------------|---------------------------------------------------------------|------------------------------------------------------|
| arquivos servidos          | .urna 58 MB + 38 mp4 (1.7 GB, art+normal) + manifest 12 MB + cache 176 MB | 1 arquivo: mtgdataset.urna, 1.356 GB     |
| midia                      | 1.19 GB (classe normal), crf35/speed8/tune default            | 1.317 GB embutida (0x17), crf35/speed6/tune still    |
| ssim2 p50 (amostra)        | ~52                                                           | ~63                                                  |
| ratio vs fonte (3.98 GB)   | 3.34x                                                         | 3.02x                                                |
| busca                      | ask/retrieve/search-space com sidecar obrigatorio             | identica, em arquivo unico                           |
| indices no arquivo         | potion int8 + 2 espacos clip                                  | potion int8 + clip int8 + HNSW + BM25 + grafo        |
| integridade                | —                                                             | `urna validate` prova o blob por sha256; `urna media --export` reconstroi o mp4 |

Overhead do single-file: 39 MB de indices/texto/vetores sobre 1.317 GB de midia (+3.0%). O diretorio `mtgdataset-v03/mtgdataset.media/` (1.2 GB) e cache de build para `--rebuild-only`/`--resume`; deletavel.

## 6. Dados brutos (${MTG_DATA})

- 82.905 jpgs, 6.9 GB. Duplicatas exatas por md5: 38 (0.05%) — dedup por bytes nao e o problema.
- `images/art_crop/` (3.0 GB) e recorte derivavel de `images/normal/`; armazenar coordenadas de crop em vez da classe economiza 3 GB. Nada foi deletado.
- ~2.800 imagens orfas por classe (nao referenciadas pela tabela `cards`).
- `all-cards.jsonl.gz` (374 MB) e `oracle-cards.jsonl.gz` (23 MB) duplicam conteudo do `mtg.sqlite`.

## 7. Estado da arte (pesquisa 2026-08-31)

- Formatos: Lance/LanceDB e o vizinho mais proximo (blob semantics, vetores, FTS), mas um dataset Lance e um diretorio, nao um arquivo. sqlite-vec+FTS5 e single-file, sem ANN nem midia. FFCV/WebDataset/TFRecord nao tem busca. Nenhum formato entrega midia codec-comprimida + HNSW + BM25 + grafo num unico arquivo mmap-avel.
- Codecs: JXL destravou em 2026 (Chrome 145, Firefox 157). AV2 1.0 saiu em mai/2026, ~30% sobre AV1; encoder de referencia ainda impraticavel — o campo `codec` versionado do container cobre a migracao futura. WebP2 descontinuado. Codecs neurais (Cool-Chic v5, MLIC++) seguem research-grade; Cool-Chic e o unico com decoder C em CPU, candidato a spike.
- Literatura de colecao-como-video: MST/album coding (2004-2015) mostra que o ganho relevante vem de predicao inter sobre quase-duplicatas ordenadas; nao ha ferramenta OSS moderna que faca isso. O par order=cluster + gop probe do urna implementa exatamente essa alavanca.
- Tecnicas anotadas para proximas rodadas: template-frame por cluster (golden frame AV1), travessia HNSW binaria com rescoring int8 (reducao de 32x no indice), dedup em cascata pHash -> CNN (imagededup/fastdup), busca de crf por alvo de metrica (estilo ab-av1).
## 8. Bateria lossless profunda (mesmos 2048 JPEGs, 211.0 MB)

| geracao                    |    MB | ratio  | encode s | classe                  | verificacao |
|----------------------------|------:|-------:|---------:|-------------------------|-------------|
| jxl-transcode -e 7 (sec.2) | 189.2 | 1.124x |     74.7 | byte-reversivel         | 2048/2048 sha256 no build |
| jxl-transcode -e 9         | 187.7 | 1.124x |    493.2 | byte-reversivel         | 64/64 roundtrips sha256 |
| jxl-transcode + zstd-19    | 188.9 | 1.117x |      1.4 | byte-reversivel         | dupla compressao: nula |
| jpegtran -optimize         | 209.6 | 1.007x |     74.7 | pixel-exato (re-save)   | 32/32 pixels identicos |
| jpegtran -progressive      | 209.6 | 1.007x |     56.1 | pixel-exato (re-save)   | 32/32 pixels identicos |
| jpegoptim --strip-all      | 211.0 | 1.000x |     16.5 | pixel-exato (re-save)   | 32/32 pixels identicos |
| webp -lossless             | 803.3 | 0.263x |    335.0 | pixel-domain (decodado) | |
| video ffv1, ordem fonte    | 783.2 | 0.269x |      9.9 | pixel-domain (decodado) | |
| video ffv1, ordem semantica| 783.0 | 0.269x |      9.0 | pixel-domain (decodado) | |
| video x264 qp0, ord. sem.  | 699.8 | 0.302x |     11.6 | pixel-domain (yuv444)   | |

Conclusao definitiva sobre "sem perda": para fontes JPEG, o teto e a recompressao
byte-reversivel — jxl-transcode, 1.124x (-11.1%), bit-exato verificado. O caminho
"inventado" (video lossless com ordenacao semantica, ffv1 e x264 qp0) foi testado e
PERDE por 3.3-3.8x: pixels decodificados de JPEG nao recomprimem abaixo do proprio
JPEG, e a ordenacao nao muda nada no regime lossless (783.0 vs 783.2 MB). Re-saves
pixel-exatos (jpegtran/jpegoptim) rendem <1% porque os JPEGs do Scryfall ja sao
otimizados. e-9 sobre e-7 rende 0.8% por 6.6x o tempo de encode; e-7 permanece o
default sensato. Artefatos vencedores em benchmark/sample-2048/lossless/jxl-e9/ + results.json;
geracoes perdedoras deletadas apos medicao (numeros preservados no results.json).

## 9. Matriz inter/ordenacao: a alavanca de similaridade, medida e corrigida

Corpus A = as 2048 cartas unicas do bench. Corpus B = 2787 reimpressoes reais da
MESMA arte (1359 grupos via printings.illustration_id, fonte 245.7 MB) — o perfil
"alta similaridade visual" da tese. Todos crf35/speed6/yuv420, sem tune salvo nota.

| corpus | config                                   |    MB | vs intra |
|--------|------------------------------------------|------:|---------:|
| A      | intra (sem tune)                         |  85.8 |     0.0% |
| A      | intra tune=still (still-s6, sec. 2)      |  70.1 |   -18.3% |
| A      | inter scd=0, ordem fonte                 |  82.5 |    -3.8% |
| A      | inter scd=0, ordem semantica             |  70.1 |   -18.3% |
| A      | inter low-delay + tune IQ, ord. sem.     | 103.6 |   +20.7% |
| B      | intra (sem tune)                         | 119.8 |     0.0% |
| B      | inter g=unico, agrupado por arte         |  95.0 |   -20.7% |
| B      | inter g=unico, embaralhado               |  96.8 |   -19.2% |
| B      | inter g=8, agrupado                      |  91.2 |   -23.9% |
| B      | inter g=16, agrupado                     |  85.0 |   -29.1% |
| B      | inter g=32, agrupado                     |  90.6 |   -24.4% |
| B      | inter low-delay + tune IQ                | 144.9 |   +21.0% |

Leituras:
1. A tese "quanto mais similaridade visual, melhor a otimizacao" esta CONFIRMADA e
   quantificada: -29% no corpus de reimpressoes (inter g=16 agrupado vs intra).
2. O culpado do resultado anterior (sec. 3.5, inter +18%) era a composicao: scene-change
   detection ligado + gop default + comparacao contra intra COM tune. Com scd=0 e
   ordenacao semantica, inter empata com tune=still no corpus de cartas unicas e
   ganha -29% no corpus similar.
3. gop LIMITADO (16) vence keyframe unico (85.0 vs 95.0 MB) e mantem o acesso
   aleatorio decodificavel em <=16 frames — o requisito do urna.
4. tune=still (IQ) e inter nao empilham: o SVT so aceita IQ em all-intra/low-delay,
   e low-delay destroi a eficiencia (+21%).
5. Embaralhado vs agrupado difere pouco no g unico (1.8pt): parte do ganho inter vem
   do chrome compartilhado entre TODAS as cartas (moldura, caixa de texto), nao so
   da arte repetida.

Decisao de produto (implementada nesta sessao): gop=inter agora emite keyint=16 +
scd=0 (constante INTER_KEYINT em image_encode.py; probe do gop=auto usa os mesmos
parametros), suite test_image_corpus atualizada e verde. Default por corpus: cartas
unicas => intra tune=still; corpora com quase-duplicatas => order=cluster + gop=auto
(o probe agora decide com o inter competitivo de verdade).

## 10. O experimento do CapCut, reproduzido e diagnosticado

Reproducao programatica (acelerar 60x, export 30fps, H.264 default de editor) sobre
o shard still-s6 de 70.1 MB / 2048 frames:

| medida            | original | apos "acelerar" |
|-------------------|---------:|----------------:|
| bytes             | 70.1 MB  | 30.2 MB (-57%)  |
| frames (cartas)   | 2048     | 1055            |

A reducao pela metade e real, mas vem de DUAS fontes: (1) o export a 30fps amostra a
timeline acelerada e DESCARTA 993 das 2048 cartas (48% do dataset perdido); (2) o
restante e re-encodado H.264 sobre material ja comprimido (perda geracional). Nao e
um caminho de compressao: e perda de dados. O ganho legitimo que o experimento
apontava — explorar redundancia entre frames — e exatamente o que a sec. 9 entrega
sem perder nenhuma carta (-29% com inter g=16 em corpus similar). O experimento
tambem expos um bug real, corrigido: decode_frame assumia fps=1 no acesso aleatorio.
## 11. Bateria all-intra (i-frame): velocidade e compacidade, mesmos 2048 JPEGs

Metodo: encode das 2048 cartas por codec, qualidade calibrada para ssimulacra2
medio 61.96 +-2 na amostra fixa de 96 (mesma regua das secs. 2 e 8); tempos de
parede na maquina do bench. Baseline reproduzido byte-identico ao measurements.json.
Dados completos: benchmark/sample-2048/iframe/results.json e benchmark/sample-2048/iframe/table.md.

| experimento              |    MB | ratio | enc (s) | ssim2 medio |
|--------------------------|------:|------:|--------:|------------:|
| avif/aom s6 q48          |  61.4 | 3.44x |    50.8 |       60.72 |
| svt p4 crf35             |  69.0 | 3.06x |   167.3 |       62.54 |
| svt p6 crf35 (baseline)  |  70.1 | 3.01x |    74.1 |       61.96 |
| svt p6 tune=3 (IQ real)  |  71.0 | 2.97x |    71.6 |       63.22 |
| svt p8 crf35             |  72.5 | 2.91x |    12.6 |       60.12 |
| jxl d4 e7 (calibrado)    |  73.0 | 2.89x |    71.1 |       60.91 |
| svt p10 crf35            |  74.7 | 2.83x |     7.0 |       59.03 |
| x264 intra crf31         |  76.0 | 2.78x |     4.8 |       60.77 |
| vvenc fast qp22 (VVC)    |  76.2 | 2.77x |   463.4 |       62.71 |
| avif/aom s9 q52          |  79.7 | 2.65x |     7.2 |       62.54 |
| x265 intra crf32         |  80.9 | 2.61x |    61.9 |       61.21 |
| webp q45                 |  85.1 | 2.48x |     9.5 |       62.20 |

Vereditos:
- Mais compacto em qualidade equivalente: avif/libaom speed 6 q48 (61.4 MB, -12.4%
  vs o stream SVT do forge). libaom ainda out-comprime SVT-AV1 em all-intra.
- Mais rapido em qualidade equivalente: x264 all-intra (4.8 s). Melhor equilibrio:
  svt p6 com lp=8 (17 s, mesmos bytes e qualidade do baseline — so threads).
- VVC intra (vvenc fast): 100x o custo do x264 para tamanho de meio de tabela;
  nao compensa neste corpus. cjxl lossy so compete em fidelidade alta (d1-d2,
  ssim2 76-90), fora da janela de qualidade deste perfil.
- Fix de produto saido da bateria: probe_tune_still sondava sem keyint=1, o Tune
  IQ (3) era rejeitado e o forge caia SILENCIOSAMENTE para tune=4 (MS_SSIM).
  Corrigido; tune=3 mede +1.26 ssim2 por +1.4% de bytes e passa a valer em todo
  encode still daqui em diante (manifests gravam tune_resolved).

Pesquisa (2025-2026, fontes no relatorio do agente): SVT-AV1 3.0 trouxe modo
still-picture/lossless e 15-25% de speedup nos presets medios; JPEG XL lidera
ssimulacra2 em alta fidelidade mas o AVIF vence na faixa de qualidade media deste
perfil (confirmado acima); WebP2 foi abandonado (2024); JPEG AI neural reivindica
~28% sobre VTM all-intra mas sem toolchain praticavel local hoje.

## 12. Tabela final — corpus completo, 38.627 cartas, um arquivo por linha

Fonte: 3.975 GB de JPEG (normal/front). Cada linha e UM .urna auto-contido
(midia embutida 0x17 + potion + CLIP int8 + HNSW + BM25 + grafo), validado
blob a blob por sha256. Os tres compartilham o MESMO content_hash
(c993ceda...): citacoes estaveis entre os gemeos por construcao (N3).

| corpus                    | bytes    | vs fonte | qualidade                     |
|---------------------------|---------:|---------:|-------------------------------|
| neardup (recomendado)     | 1.374 GB |    2.89x | ssim2 +1.26 vs v03 (tune IQ real); ordenacao semantica; gate de qualidade por segmento gravado |
| mtgdataset-v03 (still s6)  | 1.356 GB |    2.93x | ssim2 p50 62.7 (tune MS-SSIM, fallback silencioso da epoca) |
| archive (lossless)        | 3.606 GB |    1.10x | bit-exata: 38627/38627 JPEGs originais reconstruiveis, roundtrip sha256 verificado no build E no validate |

Concorrente generico no mesmo dado: tar+zstd-19 = 1.00x, sem indice, sem
busca, sem grafo (sec. 8). O unico caminho que comprime JPEG sem perda e o
que o archive usa (jxl-transcode, 1.12x na midia); o "video lossless
ordenado" perde 3.3-3.8x (sec. 8) e o inter lossy em cartas unicas troca
bytes por qualidade — vetado automaticamente pelo probe quality-aware nos
19 segmentos, com os numeros no manifest (secs. 9 e 11).

Decisao de produto consolidada: perfil "near-dup" para corpora com
quase-duplicatas (inter paga -29% quando a redundancia e real), "stills"
para imagens unicas, "archive" quando perda e inaceitavel. Uma linha de
spec cada; chave explicita sempre vence.

## 13. Candidato retrieval-only: crf sobe, a busca nao cai (2026-09-03)

Hipotese: o gate duplo trava no floor VISUAL; se o .urna serve retrieval (nao
exibicao), o crf pode subir ate o sinal vetorial reclamar. Spec
`specs/retrieval.toml`: floors visuais derrubados (-1e9), ladder [40..60],
unico floor = drift clip p10 >= 0.98.

O que o gate mediu (amostra estratificada de 48, buckets duros de proposito):
drift p10 0.932 @ crf40, 0.922 @ 45, 0.896 @ 50, 0.877 @ 55, 0.829 @ 60 —
NENHUM degrau passa o floor 0.98; fallback ruidoso para crf40. O drift
degrada muito mais rapido acima do crf35 do que a leitura otimista dos
numeros do v03 sugeria.

Mas drift e estabilidade (T1/T2), nao utilidade (T3). Mesma regua nos tres
full corpus (100 queries, seed 7, "artwork of the card {name}", clip):

| corpus                  | bytes    | drift p10 | txt@1 | txt@5 |
|-------------------------|---------:|----------:|------:|------:|
| archive (lossless)      | 3.606 GB |    0.9974 | 0.050 | 0.130 |
| neardup (crf35-classe)  | 1.374 GB |    0.9706 | 0.070 | 0.140 |
| retrieval-only (crf40)  | 0.935 GB |    0.9618 | 0.080 | 0.120 |

identity@1 = 1.000 nos tres. Em n=100 as diferencas de txt@k sao ruido:
**nenhuma degradacao detectavel de utilidade a crf40, com -31% de bytes vs
o still e -74% vs a fonte (4.22x)**. O floor de drift 0.98 e conservador
demais como proxy de utilidade; um floor de utilidade (hit@k no proprio
gate ou no sweep) liberaria os degraus mais altos — crf50 custa drift 0.896
e ninguem mediu ainda o txt@1 dele. Visualmente o crf40 E pior (ssim2 p10
por bucket 40-56): este perfil nao serve imagem bonita, por contrato.

Correcao de medicao que esta secao exigiu: o bench casava hit por
`ordinal == offset_start`, que so vale em corpus de video single-shard sem
reordenacao — neardup (cluster) e archive (per-image) zeravam. Agora casa
por `chunk_id` (identidade N3, exposta em `UrnaFile.chunk_ids()`), e paths
`${SPELLBOOK_DATA}` dos manifests sanitizados sao expandidos por env var.
Candidato validado blob a blob; content_hash novo (cb8fdf8f...) porque o
rename mtgdataset mudou o chunker_version — rebuilds sob o nome novo nao
compartilham citacoes com os gemeos c993ceda (esperado, N3). URIs de midia
NAO entram nas secoes canonicas: os candidatos av1 e avif abaixo (sec. 14)
compartilham o MESMO cb8fdf8f entre si.

## 14. A resposta do crf50 e o avif full corpus (2026-09-03)

A pergunta aberta do §13 — crf50 custa utilidade? — respondida com dois
builds full corpus (specs `retrieval50.toml` crf fixo sem gate, e
`avif.toml` q48 speed 8), validados blob a blob, MESMO content_hash
cb8fdf8f entre os tres candidatos (av1 crf40, av1 crf50, avif q48):
citacoes estaveis atraves de re-encode E de troca de backend.

Regua identica nos cinco (100 queries, seed 7, clip, "artwork of the card
{name}"; identity@1 = 1.000 em todos):

| corpus                  | bytes    | vs fonte | drift p10 | txt@1 | txt@5 |
|-------------------------|---------:|---------:|----------:|------:|------:|
| archive (lossless)      | 3.606 GB |    1.10x |    0.9974 | 0.050 | 0.130 |
| neardup (crf35-classe)  | 1.374 GB |    2.89x |    0.9706 | 0.070 | 0.140 |
| avif q48                | 1.101 GB |    3.61x |    0.9719 | 0.090 | 0.120 |
| retrieval av1 crf40     | 0.935 GB |    4.22x |    0.9618 | 0.080 | 0.120 |
| retrieval av1 crf50     | 0.508 GB |    7.82x |    0.9420 | 0.080 | 0.150 |

Duas conclusoes:

**crf50: 508 MB para 38.627 cartas pesquisaveis — e a utilidade NAO caiu.**
txt@1 0.080 = crf40 = dentro do ruido do lossless (n=100, regua fraca:
"nenhuma degradacao detectavel", nao prova de igualdade). O drift p10 0.942
teria sido VETADO por qualquer floor razoavel de drift — confirmando o §13:
drift mede estabilidade do sinal, nao utilidade da busca. Um gate
retrieval-only honesto precisa de floor de hit@k, nao de cosseno. Visual a
crf50 e RUIM de verdade (gate: ssim2 p10 por bucket 9-34) — este arquivo
serve busca, nunca exibicao. Ate onde vai? crf55/60 ficam como sweep futuro.

**avif q48 e o melhor "stills" da classe crf35.** Mesmo drift do neardup
(0.9719 vs 0.9706) com -20% de bytes (1.101 vs 1.374 GB), txt@1 igual ou
melhor, e acesso O(1) por imagem sem decode de video. A previsao da bateria
i-frame (-12.4% em qualidade casada) se materializou MAIOR no corpus cheio.
Candidato natural a substituir o backend do perfil "stills".

Nao medido aqui: wemm/jina sobre midia crf50 (a regua e so clip; modelos
que leem o texto impresso podem ser mais sensiveis ao codec — drift deles
a crf35 era 0.989/0.990). Registrado como parte do sweep.
