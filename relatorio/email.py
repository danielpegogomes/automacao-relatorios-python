"""Monta o e-mail executivo (HTML) com o Excel anexo e envia por SMTP ou salva em arquivo."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .indicadores import Relatorio, brl, pct, sinal

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
COR_STATUS = {"bom": "#0ca30c", "atencao": "#c98a00", "critico": "#d03b3b"}


def _status(a: float) -> tuple[str, str]:
    if a >= 1:
        return COR_STATUS["bom"], "✓"
    if a >= 0.9:
        return COR_STATUS["atencao"], "!"
    return COR_STATUS["critico"], "✕"


def montar_html(r: Relatorio, assunto: str, anexo: str) -> str:
    m, a = r.no_mes, r.no_ano
    var = m.variacao_aa
    kpis = [
        {"rotulo": "Produção no mês", "valor": brl(m.producao),
         "detalhe": f"{sinal(var)} vs. mesmo mês de {r.mes.year - 1}" if var is not None else "sem comparativo",
         "cor": "#006300" if (var or 0) >= 0 else "#b42f2f"},
        {"rotulo": "Atingimento no mês", "valor": pct(m.atingimento), "detalhe": f"meta de {brl(m.meta)}", "cor": _status(m.atingimento)[0]},
        {"rotulo": "Acumulado do ano", "valor": brl(a.producao), "detalhe": f"{pct(a.atingimento)} da meta", "cor": _status(a.atingimento)[0]},
    ]
    maximo = max(1.2, float(r.regionais.atingimento_ano.max()))
    regionais = []
    for g in r.regionais.itertuples():
        cor, icone = _status(g.atingimento_ano)
        regionais.append({"regional": g.regional, "atingimento": pct(g.atingimento_ano), "cor": cor, "icone": icone,
                          "largura": max(2, round(g.atingimento_ano / maximo * 100))})
    alertas = [{"agencia": x.agencia, "regional": x.regional, "atingimento": pct(x.atingimento_ano),
                "variacao": sinal(x.variacao_aa), "cor_var": "#b42f2f" if (x.variacao_aa or 0) < 0 else "#52514e"}
               for x in r.alertas.head(8).itertuples()]
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    return env.get_template("email.html.j2").render(
        r=r, assunto=assunto, kpis=kpis, regionais=regionais, alertas=alertas, total_alertas=len(r.alertas),
        anexo=anexo, gerado_em=datetime.now().strftime("%d/%m/%Y às %H:%M"))


def montar_mensagem(r: Relatorio, cfg: dict, excel: Path) -> EmailMessage:
    assunto = cfg["assunto"].format(mes_extenso=r.mes_extenso, atingimento=pct(r.no_mes.atingimento))
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = cfg["remetente"]
    msg["To"] = ", ".join(cfg["destinatarios"])
    if cfg.get("copia"):
        msg["Cc"] = ", ".join(cfg["copia"])
    msg.set_content("\n".join(r.destaques) + "\n\nO relatório completo está em anexo.")
    msg.add_alternative(montar_html(r, assunto, excel.name), subtype="html")
    msg.add_attachment(excel.read_bytes(), maintype="application",
                       subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=excel.name)
    return msg


def enviar(msg: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=30) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
