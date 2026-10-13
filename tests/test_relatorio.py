import pandas as pd
import pytest

from relatorio.indicadores import brl, calcular, pct
from relatorio.excel import gerar_excel


def base():
    linhas = []
    for mes in ("2025-08-01", "2026-07-01", "2026-08-01"):
        for ag, reg, prod, meta in (("Centro", "BH", 120, 100), ("Norte", "Norte de Minas", 70, 100)):
            fator = 1.0 if mes.startswith("2026") else 0.8
            if mes == "2026-08-01" and ag == "Norte":
                prod = 40  # queda forte no mês
            linhas.append({"mes": pd.Timestamp(mes), "agencia": ag, "regional": reg, "produto": "Consignado INSS", "segmento": "PF",
                           "producao": prod * fator, "meta": meta, "contratos": 10, "producao_digital": prod * fator * 0.7})
    pm = pd.DataFrame(linhas)
    ger = pd.DataFrame([{"mes": pd.Timestamp("2026-08-01"), "gerente_id": 1, "gerente": "Ana", "agencia": "Centro", "regional": "BH",
                         "producao": 120.0, "contratos": 10}])
    return pm, ger


def test_usa_ultimo_mes_quando_nao_informado():
    r = calcular(*base(), mes=None, atingimento_minimo=0.9, queda_maxima_aa=-0.05)
    assert r.mes == pd.Timestamp("2026-08-01")
    assert r.mes_extenso == "agosto de 2026"


def test_indicadores_do_mes_e_do_ano():
    r = calcular(*base(), mes="2026-08", atingimento_minimo=0.9, queda_maxima_aa=-0.05)
    assert r.no_mes.producao == 160 and r.no_mes.meta == 200
    assert r.no_mes.atingimento == pytest.approx(0.8)
    assert r.no_ano.producao == 160 + 190            # julho + agosto de 2026
    assert r.no_mes.variacao_aa == pytest.approx(160 / 152 - 1)


def test_alerta_por_atingimento_e_por_queda():
    r = calcular(*base(), mes="2026-08", atingimento_minimo=0.9, queda_maxima_aa=-0.05)
    assert list(r.alertas.agencia) == ["Norte"]
    motivo = r.alertas.motivo.iloc[0]
    assert "da meta no ano" in motivo and "queda" in motivo


def test_mes_inexistente_gera_erro_claro():
    with pytest.raises(ValueError, match="Não há dados"):
        calcular(*base(), mes="2020-01", atingimento_minimo=0.9, queda_maxima_aa=-0.05)


def test_formatacao_brasileira():
    assert brl(2_254_000_000) == "R$ 2,25 bi"
    assert brl(270_100_000) == "R$ 270,1 mi"
    assert pct(0.975) == "97,5%"


def test_excel_tem_todas_as_abas(tmp_path):
    import openpyxl
    r = calcular(*base(), mes="2026-08", atingimento_minimo=0.9, queda_maxima_aa=-0.05)
    arq = gerar_excel(r, tmp_path / "rel.xlsx")
    assert openpyxl.load_workbook(arq).sheetnames == ["Resumo", "Regionais", "Produtos", "Agências", "Alertas", "Gerentes"]
