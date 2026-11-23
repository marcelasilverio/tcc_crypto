"""Build the monograph report from one checksum-verified descriptive execution."""

import argparse
import csv
import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from tcc_crypto.paths import ROOT, DescriptivePaths
from tcc_crypto.results import NULL_TOKEN, file_sha256, write_json

FIGURES = {
    "workflow": "Das velas brutas às amostras da análise",
    "coverage": "Cobertura por par e número de ativos observados por dia",
    "return_intervals": "Mediana, intervalo interquartil e caudas dos retornos",
    "volatility_semester": "Volatilidade diária por ativo e semestre",
    "activity_isovolume": "Quantidade de negócios e valor médio por negócio",
    "correlation_pairwise_pearson": "Pearson nas datas coincidentes de cada dupla",
    "correlation_pairwise_spearman": "Spearman nas datas coincidentes de cada dupla",
    "correlation_pairwise_n": "Quantidade de retornos coincidentes por dupla",
    "correlation_common_pearson": "Pearson nas datas comuns aos 40 ativos",
    "correlation_common_spearman": "Spearman nas datas comuns aos 40 ativos",
    "luna_segments": "Trajetórias de LUNAUSDT antes e depois da lacuna",
    "prices": "Abertura e fechamento por ativo",
    "return_distributions": "Distribuições empíricas dos retornos por ativo",
    "volatility_rolling": "Volatilidade móvel por ativo",
    "volume": "Volume em USDT por ativo",
    "activity_semester": "Medianas diárias de atividade por semestre",
    "correlation_common_n": "Número de retornos por dupla na amostra dos 40 ativos",
}


def number(value, places=0):
    if value in (None, "", NULL_TOKEN):
        return "—"
    numeric = float(value)
    return (
        f"{numeric:,.{places}f}".replace(",", "\x00")
        .replace(".", ",")
        .replace("\x00", ".")
    )


def day(value):
    if value in (None, "", NULL_TOKEN):
        return "—"
    return date.fromisoformat(value[:10]).strftime("%d/%m/%Y")


class Evidence:
    def __init__(self, paths):
        self.paths = paths
        self.manifest = json.loads(paths.manifest.read_text())
        if self.manifest["run_id"] != paths.run_id:
            raise ValueError("The requested execution does not match the manifest.")

    def checked(self, name, path):
        record = self.manifest["artifacts"][name]
        if (
            path.relative_to(self.paths.root).as_posix() != record["path"]
            or file_sha256(path) != record["sha256"]
        ):
            raise ValueError(f"Evidence does not match the manifest: {name}")
        return path

    def table(self, name):
        path = self.checked(f"table:{name}", self.paths.table(name))
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def figure(self, name):
        return self.checked(f"figure:{name}", self.paths.figure(name))


def document_style():
    document = Document()
    document.core_properties.title = (
        "Comportamento diário de 40 criptomoedas na Binance Spot"
    )
    document.core_properties.subject = (
        "Análise estatística descritiva para a monografia"
    )
    document.core_properties.author = ""
    document.core_properties.language = "pt-BR"
    sec = document.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    sec.top_margin = sec.bottom_margin = Cm(1.9)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.footer_distance = Cm(0.95)
    style_sizes = {
        "Normal": 11,
        "Title": 29,
        "Subtitle": 12,
        "Heading 1": 20,
        "Heading 2": 14,
        "Caption": 9,
    }
    for name, size in style_sizes.items():
        style = document.styles[name]
        style.font.name = "Liberation Sans"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string("171E27")
        style.paragraph_format.space_after = Pt(7)
    document.styles["Normal"].paragraph_format.line_spacing = 1.20
    title = document.styles["Title"]
    title.font.color.rgb = RGBColor.from_string("000000")
    title_properties = title.element.get_or_add_pPr()
    border = title_properties.find(qn("w:pBdr"))
    if border is not None:
        title_properties.remove(border)
    document.styles["Caption"].font.italic = False
    document.styles["Caption"].paragraph_format.space_before = Pt(2)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("Velas diárias da Binance Spot   ·   ")
    run.font.size = Pt(9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    return document


def add_table(document, caption, headers, rows):
    document.add_paragraph(caption, style="Caption")
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Shading Accent 1"
    for cell, title in zip(table.rows[0].cells, headers):
        cell.text = title
    for values in rows:
        for cell, value in zip(table.add_row().cells, values):
            cell.text = str(value)
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for index, cell in enumerate(row.cells):
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            if index > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.size = Pt(9)


def overall(rows, field=None):
    return {
        row["symbol"]: row
        for row in rows
        if row["period"] == "overall" and (field is None or row["field"] == field)
    }


def build_document(evidence):
    (s,) = evidence.table("study_summary")
    coverage = evidence.table("coverage")
    movements = evidence.table("movement_statistics")
    returns = overall(movements, "return_pct")
    amplitudes = overall(movements, "amplitude_pct")
    sem = [
        row
        for row in movements
        if row["field"] == "return_pct"
        and row["period"] != "overall"
        and row["sample_sd"] != NULL_TOKEN
    ]
    activity_rows = evidence.table("trading_activity")
    activity = overall(activity_rows)
    btc_semesters = sorted(
        (
            row
            for row in activity_rows
            if row["symbol"] == "BTCUSDT"
            and row["period"] != "overall"
            and row["calendar_partial_semester"] == "False"
            and row["coverage_partial"] == "False"
        ),
        key=lambda row: row["period"],
    )
    daily = evidence.table("daily_metrics")
    volume_day = next(
        row
        for row in daily
        if row["symbol"] == s["highest_volume_symbol"]
        and row["date_utc"] == s["highest_volume_date_utc"]
    )
    correlations = [
        row
        for row in evidence.table("correlation_pairs")
        if row["sample"] == "pairwise"
        and row["low_support"] == "False"
        and row["pearson"] != NULL_TOKEN
    ]
    strongest = max(correlations, key=lambda row: float(row["pearson"]))
    lowest = min(correlations, key=lambda row: float(row["pearson"]))
    extrema = [
        row
        for row in evidence.table("extremes")
        if row["period"] == "overall" and row["field"] == "return_pct"
    ]
    largest_return = max(extrema, key=lambda row: float(row["value"]))
    smallest_return = min(extrema, key=lambda row: float(row["value"]))
    (luna,) = [
        row
        for row in evidence.table("candle_exceptions")
        if row["symbol"] == "LUNAUSDT" and row["status"] == "valid_shortened"
    ]
    sensitivity = {
        row["sample"]: row
        for row in evidence.table("shortened_candle_sensitivity")
        if row["symbol"] == "LUNAUSDT" and row["period"] == "overall"
    }
    segments = {row["segment"]: row for row in evidence.table("luna_segments")}
    settings = evidence.manifest["settings"]
    document = document_style()
    p = document.add_paragraph

    def chapter(title):
        document.add_page_break()
        document.add_heading(title, level=1)

    def figure(name, width=16.0):
        document.add_picture(str(evidence.figure(name)), width=Cm(width))
        document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        figure_id = list(FIGURES).index(name) + 1
        p(
            f"Figura {figure_id} · {FIGURES[name]}. Fonte dos dados: Binance Spot.",
            "Caption",
        )

    document.add_paragraph(
        "Comportamento diário de 40 criptomoedas na Binance Spot", "Title"
    )
    p("Análise estatística descritiva para a monografia", "Subtitle")
    p(f"{day(settings['start'])} a {day(settings['end'])} · Calendário UTC", "Subtitle")
    document.add_heading("Amostra e unidade de observação", level=2)
    p(
        "A unidade de observação foi a vela diária de um par da Binance Spot cotado em USDT. "
        "O universo reuniu os pares selecionados retrospectivamente por atividade acumulada "
        "e situação de negociação, com exclusão de bases classificadas como stablecoins. "
        "Para cada par, o calendário foi reconstruído pela data UTC de abertura de cada vela. "
        "Os valores vieram dos arquivos brutos da coleta diária, confrontados com os "
        "respectivos metadados antes da análise."
    )
    p(
        "A Figura 1 apresenta as duas amostras derivadas da auditoria. Preços, amplitude e "
        "atividade usam as velas válidas observadas. Os retornos usam dois fechamentos válidos "
        "em datas consecutivas e dentro do recorte. Essa regra determina também os insumos "
        "da volatilidade e da correlação. As lacunas foram preservadas em todas as etapas."
    )
    figure("workflow")

    chapter("Cobertura dos dados")
    p(
        f"O recorte compreendeu {number(s['calendar_days'])} dias por par e "
        f"{number(s['valid_candles'])} velas válidas no conjunto. O número de pares com vela "
        f"válida variou de {number(s['first_day_assets'])} no primeiro dia a "
        f"{number(s['last_day_assets'])} no último. "
        f"Houve {number(s['pre_first_days'])} combinações de par e dia anteriores à primeira "
        f"vela válida de cada série, {number(s['post_last_days'])} posteriores à última "
        f"e {number(s['internal_missing_days'])} dias ausentes dentro dos trechos observados. "
        f"Foram registradas {number(s['invalid_candles'])} velas inválidas e "
        f"{number(s['shortened_candles'])} vela válida de duração reduzida."
    )
    figure("coverage", 15.8)
    p(
        "A Figura 2 mostra que os históricos começam em momentos diferentes. A cobertura no "
        "trecho de cada par e a cobertura no calendário integral têm denominadores distintos. "
        "As fichas do apêndice apresentam ambas as taxas."
    )

    chapter("Preços e distribuição dos retornos")
    p(
        "Os níveis de abertura, máxima, mínima e fechamento foram descritos em USDT por unidade "
        "do ativo. O painel de abertura e fechamento (Figura 12) usa escala logarítmica para "
        "preservar a leitura de mudanças proporcionais em diferentes níveis de preço. Cada "
        "painel tem escala vertical própria. As estatísticas por semestre indicam se faltam "
        "dias nas bordas do recorte ou no histórico do ativo."
    )
    p(
        f"As sequências válidas produziram {number(s['return_count'])} retornos. A mediana "
        f"das medianas dos ativos foi de {number(s['median_asset_return_pct'], 2)}%. "
        f"As medianas dos percentis 5 e 95 por ativo foram, respectivamente, "
        f"{number(s['median_asset_p05_pct'], 2)}% e {number(s['median_asset_p95_pct'], 2)}%. "
        "A Figura 3 mostra essas faixas separadamente por ativo. As distribuições completas "
        "constam da Figura 13."
    )
    figure("return_intervals", 13.1)
    p(
        f"Os extremos entre fechamentos foram {number(smallest_return['value'], 2)}% "
        f"em {smallest_return['symbol']} em {day(smallest_return['date_utc'])} e "
        f"{number(largest_return['value'], 2)}% em {largest_return['symbol']} "
        f"em {day(largest_return['date_utc'])}. A tabela de extremos permite conferir "
        "as duas velas usadas em cada cálculo."
    )

    chapter("Volatilidade ao longo do tempo")
    vol_sorted = sorted(returns, key=lambda symbol: float(returns[symbol]["sample_sd"]))
    low, high = vol_sorted[0], vol_sorted[-1]
    peak = max(sem, key=lambda row: float(row["sample_sd"]))
    p(
        "A volatilidade diária foi medida pelo desvio-padrão amostral dos retornos, em "
        "pontos percentuais (p.p.). "
        f"No recorte disponível de cada ativo, a mediana das volatilidades foi de "
        f"{number(s['median_asset_volatility_pp'], 2)} p.p. Os extremos entre ativos foram "
        f"{number(returns[low]['sample_sd'], 2)} p.p. em {low} "
        f"({number(returns[low]['n'])} retornos) e "
        f"{number(returns[high]['sample_sd'], 2)} p.p. em {high} "
        f"({number(returns[high]['n'])} retornos). Essa comparação reúne históricos com "
        "durações e condições de mercado diferentes."
    )
    figure("volatility_semester", 13.5)
    p(
        f"O maior desvio-padrão semestral observado foi de {number(peak['sample_sd'], 2)} p.p. "
        f"em {peak['symbol']} ({peak['period'].replace('H', 'S')}, {number(peak['n'])} retornos). "
        f"Nesse semestre, seu maior retorno diário foi de {number(peak['max'], 2)}%. "
        "O desvio-padrão dá peso quadrático a desvios grandes, razão pela qual os percentis "
        "da Figura 3 complementam a comparação. "
        f"A Figura 14 complementa a agregação semestral com uma janela de "
        f"{settings['rolling_returns']} retornos consecutivos. A amplitude intradiária, "
        "calculada pela diferença entre máxima e mínima dividida pela abertura, descreve "
        "a oscilação dentro da vela."
    )

    chapter("Volume e atividade de negociação")
    p(
        "O volume em USDT combina a quantidade de negócios e o valor médio de cada negócio. "
        f"O maior volume observado em um par-dia foi de "
        f"{number(volume_day['quote_asset_volume'], 2)} USDT em {volume_day['symbol']}, em "
        f"{day(volume_day['date_utc'])}, distribuído por "
        f"{number(volume_day['number_of_trades'])} negócios. O valor médio nesse dia foi de "
        f"{number(volume_day['value_per_trade_usdt'], 2)} USDT por negócio."
    )
    figure("activity_isovolume")
    p(
        "As diagonais da Figura 5 indicam combinações que produzem o mesmo volume em USDT. "
        "Dois pares-dia podem ocupar a mesma diagonal com diferentes quantidades de negócios "
        "e diferentes valores médios. As tabelas semestrais incluem totais, medianas diárias "
        "e o valor médio por negócio ponderado pelo número de negócios. A Figura 15 mostra "
        "o volume em cada série, e a Figura 16 compara as medianas semestrais. O volume "
        "caracteriza a atividade registrada e, isoladamente, oferece informação limitada "
        "sobre profundidade, custos de execução e capacidade de realizar uma ordem."
    )
    if len(btc_semesters) >= 2:
        first, last = btc_semesters[0], btc_semesters[-1]
        volume_key = "volume_daily_median_usdt"
        trades_key = "trades_daily_median"
        value_key = "weighted_value_per_trade_usdt"
        if (
            float(last[volume_key]) > float(first[volume_key])
            and float(last[trades_key]) > float(first[trades_key])
            and float(last[value_key]) < float(first[value_key])
        ):
            p(
                "No BTCUSDT, entre o primeiro e o último semestre completos, aumentaram as "
                "medianas diárias de volume e de quantidade de negócios. O valor médio "
                "ponderado por negócio foi menor no último semestre."
            )
        add_table(
            document,
            "Atividade de BTCUSDT no primeiro e no último semestre completos",
            [
                "Semestre",
                "Velas",
                "Volume mediano (USDT/dia)",
                "Negócios medianos por dia",
                "Valor ponderado (USDT/negócio)",
            ],
            [
                (
                    row["period"].replace("H", "S"),
                    number(row["observed_candles"]),
                    number(row[volume_key]),
                    number(row[trades_key], 1),
                    number(row[value_key], 2),
                )
                for row in (first, last)
            ],
        )

    chapter("Dependência entre os ativos")
    p(
        f"As {number(s['pairs_count'])} duplas apresentaram de "
        f"{number(s['pairs_n_min'])} a {number(s['pairs_n_max'])} retornos em datas coincidentes. "
        f"A mediana dos coeficientes com suporte suficiente foi "
        f"{number(s['pairwise_pearson_median'], 2)} para Pearson e "
        f"{number(s['pairwise_spearman_median'], 2)} para Spearman. "
        "Pearson descreve o comovimento linear, enquanto Spearman compara a ordenação dos "
        "retornos. A Figura 8 informa o suporte diário de cada estimativa."
    )
    figure("correlation_pairwise_pearson", 14.2)
    p(
        f"Na amostra por dupla, os coeficientes de Pearson variaram de "
        f"{number(lowest['pearson'], 2)} ({lowest['symbol_a']} e {lowest['symbol_b']}, "
        f"{number(lowest['n'])} datas) a {number(strongest['pearson'], 2)} "
        f"({strongest['symbol_a']} e {strongest['symbol_b']}, {number(strongest['n'])} datas). "
        "Esses valores combinam a dependência observada e a composição temporal da amostra de cada dupla."
    )

    chapter("Comparação em datas comuns")
    p(
        f"A interseção dos retornos válidos dos 40 ativos reuniu {number(s['common_dates'])} "
        f"datas entre {day(s['common_first_utc'])} e {day(s['common_last_utc'])}. "
        f"Nas mesmas datas para todas as duplas, as medianas foram "
        f"{number(s['common_pearson_median'], 2)} para Pearson e "
        f"{number(s['common_spearman_median'], 2)} para Spearman. "
        f"A mediana da mudança absoluta em Pearson entre as duas formas de alinhamento foi "
        f"{number(s['median_abs_pearson_change'], 2)}. Usar uma janela comum melhora a "
        "comparabilidade temporal e concentra a análise nos anos em que o conjunto inteiro "
        "estava simultaneamente observado."
    )
    figure("correlation_common_pearson", 14.2)
    p(
        "O comovimento histórico ajuda a contextualizar o papel da covariância na diversificação. "
        "A seleção retrospectiva da amostra e o recorte de uma única bolsa limitam a abrangência "
        "da interpretação. O retorno entre fechamentos descreve o comportamento observado "
        "entre dias. O alvo do SVM usa a máxima em relação à abertura do dia seguinte."
    )

    chapter("Descontinuidade de LUNAUSDT")
    p(
        f"A vela de {day(luna['date_utc'])} teve duração de "
        f"{number(float(luna['duration_ms']) / 3_600_000, 2)} horas. O período sem velas "
        f"se estendeu de {day(s['luna_gap_start_utc'])} a {day(s['luna_gap_end_utc'])}. "
        "A primeira vela após a interrupção ficou sem retorno entre fechamentos. Os dois "
        "trechos foram apresentados individualmente para a leitura dos níveis de preço."
    )
    figure("luna_segments")
    add_table(
        document,
        "Tabela 1 · Fechamentos de LUNAUSDT por trecho",
        ["Trecho", "Primeiro dia", "Último dia", "Velas", "Mediana (USDT)"],
        [
            (
                label,
                day(row["start_utc"]),
                day(row["end_utc"]),
                number(row["n"]),
                number(row["median"], 5),
            )
            for key, label in [("before_gap", "Antes"), ("after_gap", "Depois")]
            for row in [segments[key]]
        ],
    )
    p(
        "A análise de sensibilidade excluiu a vela encurtada. Para LUNAUSDT no recorte integral, "
        f"a amplitude intradiária mediana passou de "
        f"{number(sensitivity['all_valid']['amplitude_median'], 3)}% para "
        f"{number(sensitivity['full_only']['amplitude_median'], 3)}%, e o valor médio "
        f"ponderado por negócio passou de "
        f"{number(sensitivity['all_valid']['weighted_value_per_trade_usdt'], 2)} para "
        f"{number(sensitivity['full_only']['weighted_value_per_trade_usdt'], 2)} USDT. "
        "A tabela de sensibilidade registra também a comparação no semestre afetado. "
        "A decisão de elegibilidade exclui LUNAUSDT da modelagem por descontinuidade econômica."
    )

    chapter("Apêndice A  Fórmulas e critérios")
    for title, paragraph in [
        (
            "Cobertura",
            "A cobertura no calendário é o número de velas válidas dividido pelo número de "
            "dias no recorte. A cobertura no trecho divide o mesmo numerador pelos dias entre "
            "a primeira e a última vela válidas, inclusive. A cobertura registra separadamente "
            "as bordas e as ausências internas. Os casos auditados conservam data e motivo.",
        ),
        (
            "Preços e amplitude",
            "Abertura, máxima, mínima e fechamento são expressos em USDT por unidade. "
            "A amplitude intradiária em porcentagem é 100 × (máxima − mínima) ÷ abertura. "
            "As tabelas incluem média, mediana, mínimo, máximo, amplitude, quartis, intervalo "
            "interquartil, variância e desvio-padrão amostrais, coeficiente de variação, "
            "assimetria amostral corrigida e excesso de curtose de Fisher. Os quantis usam "
            "interpolação linear. As estatísticas de volume incluem somas e participação de zeros.",
        ),
        (
            "Retorno e volatilidade",
            "O retorno diário em porcentagem é 100 × (fechamento atual ÷ fechamento anterior − 1). "
            "O desvio-padrão é a raiz quadrada da soma dos desvios quadráticos em relação à média "
            "dividida por n − 1. A unidade do desvio-padrão é ponto percentual na frequência diária. "
            f"A janela móvel exige {settings['rolling_returns']} retornos consecutivos e, "
            f"portanto, {settings['rolling_returns'] + 1} fechamentos válidos. "
            "As primeiras velas do recorte e as velas imediatamente após uma lacuna ficam sem retorno.",
        ),
        (
            "Atividade",
            "A unidade do volume cotado é USDT. O valor por negócio é o volume dividido pelo "
            "número de negócios. No período, a razão ponderada divide o volume total pela "
            "quantidade total. Uma quantidade nula deixa a razão ausente. Para cada semestre, "
            "o CSV informa os dias com vela, os zeros e os dias com razão definida.",
        ),
        (
            "Correlações",
            "As duas séries são alinhadas nas datas válidas para a comparação. Spearman usa "
            "postos médios nos empates, calculados dentro da amostra correspondente. "
            f"Menos de {settings['low_correlation_support']} datas recebem marcação de baixo suporte. "
            "As estimativas são indefinidas com menos de dois retornos ou se uma das séries "
            "for constante. Os resultados são descritivos e não incluem testes de hipótese.",
        ),
    ]:
        document.add_heading(title, level=2)
        p(paragraph)
    p(
        f"Identificador da execução  {evidence.paths.run_id}. O manifesto contém os hashes "
        "dos arquivos de entrada e saída, as configurações e a revisão do código.",
        "Caption",
    )

    for start in range(0, len(coverage), 10):
        chapter(
            f"Apêndice B  Fichas dos pares {start + 1} a {min(start + 10, len(coverage))}"
        )
        block = coverage[start : start + 10]
        add_table(
            document,
            "Cobertura e movimento no recorte",
            [
                "Par",
                "Primeiro dia",
                "Último dia",
                "Velas",
                "Cobertura recorte / trecho (%)",
                "Volat. (p.p.)",
                "Amplitude mediana (%)",
            ],
            [
                (
                    row["symbol"],
                    day(row["first_valid_utc"]),
                    day(row["last_valid_utc"]),
                    number(row["valid_days"]),
                    f"{number(row['coverage_calendar_pct'], 1)} / {number(row['coverage_span_pct'], 1)}",
                    number(returns[row["symbol"]]["sample_sd"], 2),
                    number(amplitudes[row["symbol"]]["median"], 2),
                )
                for row in block
            ],
        )
        add_table(
            document,
            "Retornos e atividade no recorte",
            [
                "Par",
                "Retornos",
                "P5 (%)",
                "P95 (%)",
                "Volume mediano (USDT/dia)",
                "Negócios medianos por dia",
                "Valor ponderado (USDT/negócio)",
            ],
            [
                (
                    symbol,
                    number(returns[symbol]["n"]),
                    number(returns[symbol]["tail_low"], 2),
                    number(returns[symbol]["tail_high"], 2),
                    number(activity[symbol]["volume_daily_median_usdt"]),
                    number(activity[symbol]["trades_daily_median"], 1),
                    number(activity[symbol]["weighted_value_per_trade_usdt"], 2),
                )
                for symbol in [row["symbol"] for row in block]
            ],
        )
        p(
            "As coberturas e estatísticas usam os denominadores descritos no Apêndice A.",
            "Caption",
        )

    for name, title in [
        (
            "correlation_pairwise_spearman",
            "Apêndice C  Correlação de Spearman por dupla",
        ),
        ("correlation_pairwise_n", "Apêndice C  Suporte das correlações por dupla"),
        ("correlation_common_spearman", "Apêndice C  Spearman em datas comuns"),
    ]:
        chapter(title)
        figure(name, 16.3)

    chapter("Apêndice D  Índice das evidências")
    add_table(
        document,
        "Figuras avulsas da execução",
        ["Figura", "Conteúdo", "Arquivo PNG"],
        [
            (str(i), title, name + ".png")
            for i, (name, title) in enumerate(FIGURES.items(), 1)
        ],
    )
    document.add_heading("Tabelas semestrais e auditoria em CSV", level=2)
    p(
        "As tabelas semestrais completas integram o apêndice eletrônico. "
        "Use price_volume_statistics.csv para OHLC e volume, movement_statistics.csv para "
        "retornos e amplitude, e trading_activity.csv para volume, negócios e valor médio. "
        "Cada uma apresenta os resultados por par e semestre e identifica o recorte parcial. "
        "Os registros de extremos e as datas coincidentes por dupla também acompanham a execução."
    )
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--soffice", default=shutil.which("soffice"))
    args = parser.parse_args()
    if not args.soffice:
        parser.error("Install LibreOffice or specify --soffice.")
    paths = DescriptivePaths(ROOT, args.run_id)
    docx, pdf = paths.report("docx"), paths.report("pdf")
    report_lock = paths.lock
    report_lock.mkdir()
    try:
        if docx.exists() or pdf.exists():
            raise FileExistsError("Reports already exist for this execution.")
        evidence = Evidence(paths)
        document = build_document(evidence)
        with TemporaryDirectory(dir=paths.output) as stage_name:
            stage = Path(stage_name)
            word = stage / docx.name
            document.save(word)
            subprocess.run(
                [
                    args.soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(stage),
                    str(word),
                ],
                check=True,
            )
            rendered = stage / pdf.name
            if not rendered.exists() or not rendered.stat().st_size:
                raise ValueError("LibreOffice did not produce the PDF.")
            report_manifest = {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "builder_sha256": file_sha256(Path(__file__)),
                "python_docx_version": version("python-docx"),
                "artifacts": {
                    target.suffix[1:]: {
                        "path": target.relative_to(paths.root).as_posix(),
                        "sha256": file_sha256(source),
                    }
                    for target, source in [(docx, word), (pdf, rendered)]
                },
            }
            word.rename(docx)
            try:
                rendered.rename(pdf)
                write_json(
                    paths.manifest, {**evidence.manifest, "report": report_manifest}
                )
            except BaseException:
                docx.unlink()
                pdf.unlink(missing_ok=True)
                raise
    finally:
        report_lock.rmdir()


if __name__ == "__main__":
    main()
