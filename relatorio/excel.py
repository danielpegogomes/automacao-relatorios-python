"""Gera o relatório gerencial em Excel, formatado e com gráfico nativo."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .indicadores import Relatorio

AZUL, AZUL_ESCURO, CINZA, TINTA = "#2A78D6", "#104281", "#F1F1EE", "#0B0B0B"


def gerar_excel(r: Relatorio, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="xlsxwriter") as xw:
        wb = xw.book
        f = {
            "titulo": wb.add_format({"bold": True, "font_size": 16, "font_color": TINTA}),
            "sub": wb.add_format({"font_size": 10, "font_color": "#6F6D68"}),
            "rot": wb.add_format({"font_size": 9, "font_color": "#52514E", "bold": True}),
            "kpi": wb.add_format({"bold": True, "font_size": 18, "num_format": 'R$ #,##0,,," mi"'}),
            "kpi_pct": wb.add_format({"bold": True, "font_size": 18, "num_format": "0.0%"}),
            "kpi_num": wb.add_format({"bold": True, "font_size": 18, "num_format": "#,##0"}),
            "cab": wb.add_format({"bold": True, "font_color": "white", "bg_color": AZUL_ESCURO, "border": 0, "valign": "vcenter", "text_wrap": True}),
            "txt": wb.add_format({"valign": "vcenter"}),
            "brl": wb.add_format({"num_format": 'R$ #,##0', "valign": "vcenter"}),
            "pct": wb.add_format({"num_format": "0.0%", "valign": "vcenter"}),
            "var": wb.add_format({"num_format": '+0.0%;[Red]-0.0%;0.0%', "valign": "vcenter"}),
            "num": wb.add_format({"num_format": "#,##0", "valign": "vcenter"}),
            "nota": wb.add_format({"italic": True, "font_size": 9, "font_color": "#6F6D68"}),
        }

        # ---------------- Resumo ----------------
        ws = wb.add_worksheet("Resumo")
        ws.hide_gridlines(2)
        ws.set_column("A:A", 2)
        ws.set_column("B:G", 22)
        ws.write("B2", "Relatório de Produção Comercial", f["titulo"])
        ws.write("B3", f"Banco Horizonte · Superintendência Comercial PF/PJ · {r.mes_extenso}", f["sub"])
        kpis = [
            ("Produção no mês", r.no_mes.producao, "kpi"), ("Meta do mês", r.no_mes.meta, "kpi"),
            ("Atingimento no mês", r.no_mes.atingimento, "kpi_pct"), ("Produção no ano", r.no_ano.producao, "kpi"),
            ("Atingimento no ano", r.no_ano.atingimento, "kpi_pct"), ("Contratos no mês", r.no_mes.contratos, "kpi_num"),
        ]
        for i, (rotulo, valor, fmt) in enumerate(kpis):
            col = 1 + i % 3 * 2
            lin = 5 + (i // 3) * 3
            ws.write(lin, col, rotulo, f["rot"])
            ws.write(lin + 1, col, valor, f[fmt])
        ws.write("B12", "Destaques", f["rot"])
        for i, d in enumerate(r.destaques):
            ws.write(12 + i, 1, f"• {d}")

        ev = r.evolucao.assign(mes=r.evolucao.mes.dt.strftime("%m/%Y"))
        lin0 = 20
        ws.write(lin0 - 1, 1, "Últimos 12 meses", f["rot"])
        for j, cab in enumerate(["Mês", "Produção", "Meta", "Atingimento"]):
            ws.write(lin0, 1 + j, cab, f["cab"])
        for i, row in enumerate(ev.itertuples()):
            ws.write(lin0 + 1 + i, 1, row.mes, f["txt"])
            ws.write(lin0 + 1 + i, 2, row.producao, f["brl"])
            ws.write(lin0 + 1 + i, 3, row.meta, f["brl"])
            ws.write(lin0 + 1 + i, 4, row.atingimento, f["pct"])
        n = len(ev)
        graf = wb.add_chart({"type": "column"})
        graf.add_series({"name": "Produção", "categories": ["Resumo", lin0 + 1, 1, lin0 + n, 1], "values": ["Resumo", lin0 + 1, 2, lin0 + n, 2],
                         "fill": {"color": AZUL}, "gap": 120})
        linha = wb.add_chart({"type": "line"})
        linha.add_series({"name": "Meta", "categories": ["Resumo", lin0 + 1, 1, lin0 + n, 1], "values": ["Resumo", lin0 + 1, 3, lin0 + n, 3],
                          "line": {"color": "#52514E", "width": 2}, "marker": {"type": "circle", "size": 5, "fill": {"color": "#52514E"}, "border": {"color": "white"}}})
        graf.combine(linha)
        graf.set_title({"name": "Produção × meta", "name_font": {"size": 11, "bold": True}})
        graf.set_y_axis({"num_format": 'R$ #,##0,,," mi"', "major_gridlines": {"visible": True, "line": {"color": "#E1E0D9"}}, "line": {"none": True}})
        graf.set_x_axis({"line": {"color": "#C3C2B7"}})
        graf.set_legend({"position": "top"})
        graf.set_chartarea({"border": {"none": True}})
        graf.set_size({"width": 640, "height": 300})
        ws.insert_chart(lin0, 6, graf)

        # ---------------- Abas de detalhe ----------------
        def aba(nome: str, df: pd.DataFrame, colunas: list[tuple[str, str, str, int]], cond_ating: str | None = None, nota: str | None = None):
            s = wb.add_worksheet(nome)
            s.freeze_panes(1, 1)
            for j, (titulo, campo, fmt, larg) in enumerate(colunas):
                s.write(0, j, titulo, f["cab"])
                s.set_column(j, j, larg)
                for i, v in enumerate(df[campo]):
                    if pd.isna(v):
                        s.write_blank(i + 1, j, None, f[fmt])
                    else:
                        s.write(i + 1, j, v, f[fmt])
            s.set_row(0, 30)
            s.autofilter(0, 0, len(df), len(colunas) - 1)
            if cond_ating:
                j = [c[1] for c in colunas].index(cond_ating)
                rng = (1, j, len(df), j)
                s.conditional_format(*rng, {"type": "icon_set", "icon_style": "3_traffic_lights",
                                            "icons": [{"criteria": ">=", "type": "number", "value": 1},
                                                      {"criteria": ">=", "type": "number", "value": 0.9}]})
            if nota:
                s.write(len(df) + 2, 0, nota, f["nota"])
            return s

        reg = aba("Regionais", r.regionais, [
            ("Regional", "regional", "txt", 24), ("Produção no mês", "producao", "brl", 16), ("Meta no mês", "meta", "brl", 16),
            ("Atingimento no mês", "atingimento", "pct", 14), ("Var. a/a no mês", "variacao_aa", "var", 13),
            ("Produção no ano", "producao_ano", "brl", 17), ("Atingimento no ano", "atingimento_ano", "pct", 14),
            ("% digital no mês", "pct_digital", "pct", 13)], cond_ating="atingimento_ano")
        reg.conditional_format(1, 1, len(r.regionais), 1, {"type": "data_bar", "bar_color": AZUL, "bar_solid": True})

        aba("Produtos", r.produtos, [
            ("Produto", "produto", "txt", 26), ("Segmento", "segmento", "txt", 10), ("Produção", "producao", "brl", 16),
            ("Meta", "meta", "brl", 16), ("Atingimento", "atingimento", "pct", 13), ("Var. a/a", "variacao_aa", "var", 11),
            ("Contratos", "contratos", "num", 11)], cond_ating="atingimento")

        aba("Agências", r.agencias, [
            ("Agência", "agencia", "txt", 26), ("Regional", "regional", "txt", 20), ("Produção no mês", "producao", "brl", 16),
            ("Meta no mês", "meta", "brl", 16), ("Atingimento no mês", "atingimento", "pct", 14), ("Var. a/a", "variacao_aa", "var", 11),
            ("Atingimento no ano", "atingimento_ano", "pct", 14), ("Contratos", "contratos", "num", 11)], cond_ating="atingimento_ano")

        aba("Alertas", r.alertas, [
            ("Agência", "agencia", "txt", 26), ("Regional", "regional", "txt", 20), ("Atingimento no ano", "atingimento_ano", "pct", 14),
            ("Var. a/a no mês", "variacao_aa", "var", 13), ("Produção no mês", "producao", "brl", 16), ("Motivo", "motivo", "txt", 60)],
            cond_ating="atingimento_ano", nota="Critérios em config.yaml (alertas.atingimento_minimo e alertas.queda_maxima_aa).")

        aba("Gerentes", r.gerentes, [
            ("Gerente", "gerente", "txt", 24), ("Agência", "agencia", "txt", 24), ("Regional", "regional", "txt", 20),
            ("Produção no mês", "producao", "brl", 16), ("Contratos", "contratos", "num", 11)])
    return destino
