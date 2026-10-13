"""Cálculo dos indicadores do relatório a partir dos marts."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


@dataclass
class Resumo:
    producao: float
    meta: float
    contratos: int
    digital: float
    producao_ano_anterior: float | None = None
    contratos_ano_anterior: int | None = None

    @property
    def atingimento(self) -> float:
        return self.producao / self.meta if self.meta else 0.0

    @property
    def ticket(self) -> float:
        return self.producao / self.contratos if self.contratos else 0.0

    @property
    def pct_digital(self) -> float:
        return self.digital / self.producao if self.producao else 0.0

    @property
    def variacao_aa(self) -> float | None:
        return self.producao / self.producao_ano_anterior - 1 if self.producao_ano_anterior else None


@dataclass
class Relatorio:
    mes: pd.Timestamp
    mes_extenso: str
    no_mes: Resumo
    no_ano: Resumo
    regionais: pd.DataFrame
    produtos: pd.DataFrame
    agencias: pd.DataFrame
    alertas: pd.DataFrame
    gerentes: pd.DataFrame
    evolucao: pd.DataFrame
    destaques: list[str] = field(default_factory=list)


def carregar(caminho_pm: str, caminho_gerentes: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pm = pd.read_parquet(caminho_pm)
    pm.columns = [c.lower() for c in pm.columns]
    pm["mes"] = pd.to_datetime(pm.mes)
    ger = pd.read_parquet(caminho_gerentes)
    ger.columns = [c.lower() for c in ger.columns]
    ger["mes"] = pd.to_datetime(ger.mes)
    return pm, ger


def _resumo(df: pd.DataFrame, anterior: pd.DataFrame | None) -> Resumo:
    return Resumo(
        producao=float(df.producao.sum()), meta=float(df.meta.sum()), contratos=int(df.contratos.sum()),
        digital=float(df.producao_digital.sum()),
        producao_ano_anterior=float(anterior.producao.sum()) if anterior is not None and len(anterior) else None,
        contratos_ano_anterior=int(anterior.contratos.sum()) if anterior is not None and len(anterior) else None,
    )


def _por(df: pd.DataFrame, chave: list[str], anterior: pd.DataFrame | None = None) -> pd.DataFrame:
    t = df.groupby(chave, as_index=False)[["producao", "meta", "contratos", "producao_digital"]].sum()
    t["atingimento"] = t.producao / t.meta.where(t.meta > 0)
    t["pct_digital"] = t.producao_digital / t.producao.where(t.producao > 0)
    if anterior is not None:
        a = anterior.groupby(chave, as_index=False).producao.sum().rename(columns={"producao": "producao_aa"})
        t = t.merge(a, on=chave, how="left")
        t["variacao_aa"] = t.producao / t.producao_aa.where(t.producao_aa > 0) - 1
    return t


def calcular(pm: pd.DataFrame, ger: pd.DataFrame, mes: str | None, atingimento_minimo: float, queda_maxima_aa: float) -> Relatorio:
    ref = pd.Timestamp(mes + "-01") if mes else pm.loc[pm.producao > 0, "mes"].max()
    if ref not in set(pm.mes):
        raise ValueError(f"Não há dados para {ref:%m/%Y} na base.")
    ref_aa = ref - pd.DateOffset(years=1)

    mes_df, mes_aa = pm[pm.mes == ref], pm[pm.mes == ref_aa]
    ano_df = pm[(pm.mes.dt.year == ref.year) & (pm.mes <= ref)]
    ano_aa = pm[(pm.mes.dt.year == ref.year - 1) & (pm.mes <= ref_aa)]

    regionais = _por(mes_df, ["regional"], mes_aa).merge(
        _por(ano_df, ["regional"])[["regional", "producao", "meta", "atingimento"]].rename(
            columns={"producao": "producao_ano", "meta": "meta_ano", "atingimento": "atingimento_ano"}), on="regional")
    regionais = regionais.sort_values("atingimento_ano", ascending=False).reset_index(drop=True)

    produtos = _por(mes_df, ["produto", "segmento"], mes_aa).sort_values("producao", ascending=False).reset_index(drop=True)

    agencias = _por(mes_df, ["agencia", "regional"], mes_aa).merge(
        _por(ano_df, ["agencia"])[["agencia", "atingimento"]].rename(columns={"atingimento": "atingimento_ano"}), on="agencia")
    agencias = agencias.sort_values("producao", ascending=False).reset_index(drop=True)

    def motivo(a) -> str:
        partes = []
        if a.atingimento_ano < atingimento_minimo:
            partes.append(f"{pct(a.atingimento_ano)} da meta no ano (mínimo {pct(atingimento_minimo, 0)})")
        if pd.notna(a.variacao_aa) and a.variacao_aa < queda_maxima_aa:
            partes.append(f"queda de {pct(-a.variacao_aa)} contra {ref_aa:%m/%Y}")
        return " e ".join(partes)

    alertas = agencias.assign(motivo=agencias.apply(motivo, axis=1))
    alertas = alertas[alertas.motivo != ""].sort_values("atingimento_ano").reset_index(drop=True)

    g = ger[(ger.mes == ref) & (ger.gerente_id != -1)].groupby(["gerente", "agencia", "regional"], as_index=False)[["producao", "contratos"]].sum()
    gerentes = g.sort_values("producao", ascending=False).head(10).reset_index(drop=True)

    inicio = ref - pd.DateOffset(months=12)
    evolucao = (pm[(pm.mes > inicio) & (pm.mes <= ref)].groupby("mes", as_index=False)[["producao", "meta", "producao_digital"]].sum())
    evolucao["atingimento"] = evolucao.producao / evolucao.meta

    rel = Relatorio(
        mes=ref, mes_extenso=f"{MESES[ref.month - 1]} de {ref.year}",
        no_mes=_resumo(mes_df, mes_aa), no_ano=_resumo(ano_df, ano_aa),
        regionais=regionais, produtos=produtos, agencias=agencias, alertas=alertas, gerentes=gerentes, evolucao=evolucao,
    )
    rel.destaques = destaques(rel)
    return rel


def brl(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:,.2f} bi"
    elif a >= 1e6:
        s = f"{v / 1e6:,.1f} mi"
    elif a >= 1e3:
        s = f"{v / 1e3:,.1f} mil"
    else:
        s = f"{v:,.0f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float | None, casas: int = 1) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v * 100:.{casas}f}%".replace(".", ",")


def sinal(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return ("+" if v >= 0 else "−") + pct(abs(v))


def destaques(r: Relatorio) -> list[str]:
    m, a = r.no_mes, r.no_ano
    linhas = [
        f"A produção de {r.mes_extenso} foi de {brl(m.producao)}, {pct(m.atingimento)} da meta"
        + (f" e {sinal(m.variacao_aa)} contra o mesmo mês do ano anterior." if m.variacao_aa is not None else "."),
        f"No acumulado do ano, a produção soma {brl(a.producao)} ({pct(a.atingimento)} da meta).",
    ]
    if len(r.regionais) > 1:
        top, fim = r.regionais.iloc[0], r.regionais.iloc[-1]
        linhas.append(f"Melhor regional no ano: {top.regional} ({pct(top.atingimento_ano)}). "
                      f"Menor: {fim.regional} ({pct(fim.atingimento_ano)}).")
    linhas.append(f"Canais digitais responderam por {pct(m.pct_digital)} da produção do mês.")
    if len(r.alertas):
        linhas.append(f"{len(r.alertas)} agência(s) em alerta: lista completa na aba Alertas do Excel.")
    return linhas
