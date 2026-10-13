"""
Relatório mensal de produção comercial.

  python -m relatorio                    # último mês com dados; salva Excel, prévia HTML e .eml em saida/
  python -m relatorio --mes 2026-08      # mês específico
  python -m relatorio --enviar           # envia por SMTP (variáveis SMTP_* no ambiente)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

from .email import enviar, montar_html, montar_mensagem
from .excel import gerar_excel
from .indicadores import brl, calcular, carregar, pct

RAIZ = Path(__file__).resolve().parents[1]
log = logging.getLogger("relatorio")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera e distribui o relatório mensal de produção comercial.")
    ap.add_argument("--mes", help="mês de referência no formato AAAA-MM (padrão: último mês com dados)")
    ap.add_argument("--config", default=str(RAIZ / "config.yaml"))
    ap.add_argument("--enviar", action="store_true", help="envia o e-mail por SMTP em vez de só salvar o arquivo .eml")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    t0 = time.perf_counter()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    pm, ger = carregar(RAIZ / cfg["dados"]["producao_x_meta"], RAIZ / cfg["dados"]["gerentes"])
    log.info("dados carregados: %d linhas de produção × meta, %d de gerentes", len(pm), len(ger))

    r = calcular(pm, ger, args.mes, **cfg["alertas"])
    log.info("referência: %s · produção %s · %s da meta · %d agências em alerta",
             r.mes_extenso, brl(r.no_mes.producao), pct(r.no_mes.atingimento), len(r.alertas))

    saida = RAIZ / cfg["saida"]
    excel = gerar_excel(r, saida / f"producao_comercial_{r.mes:%Y_%m}.xlsx")
    log.info("excel gerado: %s", excel.relative_to(RAIZ))

    msg = montar_mensagem(r, cfg["email"], excel)
    (saida / f"email_{r.mes:%Y_%m}.html").write_text(montar_html(r, msg["Subject"], excel.name), encoding="utf-8")
    if args.enviar:
        enviar(msg)
        log.info("e-mail enviado para %s", msg["To"])
    else:
        (saida / f"email_{r.mes:%Y_%m}.eml").write_bytes(bytes(msg))
        log.info("e-mail salvo em saida/ (use --enviar para disparar por SMTP)")
    log.info("concluído em %.1fs", time.perf_counter() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
