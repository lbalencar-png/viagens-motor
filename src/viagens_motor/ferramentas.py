"""Fachada única usada pela linha de comando e pelo servidor MCP."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import calendario, cambio, clima, custos, google, lugares, ordem, rotas, transporte
from .cache import Cache
from .config import Config, carregar
from .http import Cliente
from .resultado import FonteErro, falha, ok

_TF = None


def _fuso(lat: float, lon: float) -> str:
    global _TF
    if _TF is None:
        from timezonefinder import TimezoneFinder

        _TF = TimezoneFinder()
    return _TF.timezone_at(lat=lat, lng=lon) or "UTC"


def _data(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as e:
        raise ValueError(f"data inválida: {texto} (use AAAA-MM-DD)") from e


def _juntar_avisos(*avisos: str | None) -> str | None:
    lista = [a for a in avisos if a]
    return "; ".join(lista) or None


def _aviso_distantes(coords, modo: str) -> str | None:
    """Pontos muito longe do primeiro costumam ser o lugar errado (homônimo em outra cidade)."""
    limite = 300 if modo == "carro" else 50
    primeiro = coords[0]
    ruins = []
    for c in coords[1:]:
        d = lugares.km_entre(primeiro[:2], c[:2])
        if d > limite:
            ruins.append(f"{c[2]} ficou a {round(d)} km de {primeiro[2]}; confira o nome")
    return "; ".join(ruins) or None


def _protegido(fn):
    @wraps(fn)
    def envolto(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FonteErro as e:
            return falha(e.fonte, str(e))
        except ValueError as e:
            return falha("viagens-motor", str(e))
        except (KeyError, TypeError, IndexError, AttributeError) as e:
            return falha("viagens-motor", f"resposta inesperada: {type(e).__name__}: {e}")

    return envolto


class Motor:
    def __init__(self, cfg: Config, cli: Cliente, hoje: Callable[[], date] = date.today):
        self.cfg, self.cli, self._hoje = cfg, cli, hoje

    def _coord(self, ponto: str, perto_de=None):
        """(lat, lon, nome, aviso); o aviso só existe quando o escolhido não é o primeiro do Photon."""
        return lugares.localizar(self.cli, ponto, perto_de=perto_de)

    def _coords_com_vies(self, pontos: list[str]):
        """O primeiro ponto sem viés; os demais, o candidato mais próximo do primeiro."""
        primeiro = self._coord(pontos[0])
        return [primeiro, *(self._coord(p, perto_de=primeiro[:2]) for p in pontos[1:])]

    @_protegido
    def lugar(self, texto: str, perto_de: str | None = None) -> dict:
        perto = self._coord(perto_de)[:2] if perto_de else None
        cands, fonte = lugares.buscar(self.cli, texto, perto_de=perto)
        return ok(fonte, {"candidatos": cands})

    @_protegido
    def rota(self, origem: str, destino: str, modo: str = "pe", quando: str | None = None) -> dict:
        la, lo, nome_a, aviso_a = self._coord(origem)
        # A pé e de bicicleta o destino é o homônimo mais próximo da origem; de carro e de
        # transporte, o primeiro do Photon (entre cidades, o mais próximo costuma ser um bairro).
        perto = (la, lo) if modo in ("pe", "bicicleta") else None
        lb, lob, nome_b, aviso_b = self._coord(destino, perto_de=perto)
        aviso_perto = None
        if modo in ("carro", "transporte") and lugares.km_entre((la, lo), (lb, lob)) < 2:
            aviso_perto = f"{nome_a} e {nome_b} ficaram a menos de 2 km um do outro (provável homônimo); confira o nome"
        aviso_nomes = _juntar_avisos(aviso_a, aviso_b, aviso_perto)
        base = {"origem": nome_a, "destino": nome_b, "modo": modo}
        if modo != "transporte":
            try:
                dados, fonte = rotas.rota(self.cli, (la, lo), (lb, lob), modo)
                return ok(fonte, {**base, **dados}, aviso_nomes)
            except FonteErro as e:
                return self._google(base, (la, lo), (lb, lob), modo, None, e, aviso_nomes)
        fuso = ZoneInfo(_fuso(la, lo))
        if quando:
            try:
                momento = datetime.fromisoformat(quando).replace(tzinfo=fuso)
            except ValueError as e:
                raise ValueError(f"quando inválido: {quando} (use AAAA-MM-DDTHH:MM)") from e
        else:
            momento = (datetime.now(fuso) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        try:
            dados, fonte, aviso = transporte.plano(self.cli, (la, lo), (lb, lob), momento, hoje=self._hoje())
            return ok(fonte, {**base, "quando": momento.isoformat(), **dados}, _juntar_avisos(aviso, aviso_nomes))
        except FonteErro as e:
            return self._google(base, (la, lo), (lb, lob), modo, momento, e, aviso_nomes)

    def _google(self, base, a, b, modo, momento, erro: FonteErro, aviso_nomes: str | None = None) -> dict:
        chave = self.cfg.google_chave()
        if not chave:
            return falha(erro.fonte, str(erro))
        dados, fonte = google.rota(self.cli, chave, a, b, modo, momento)
        aviso = f"{erro.fonte.split(' ')[0]} falhou ({erro}); usado o Google"
        return ok(fonte, {**base, **dados}, _juntar_avisos(aviso, aviso_nomes))

    @_protegido
    def distancias(self, pontos: list[str], modo: str = "pe") -> dict:
        coords = self._coords_com_vies(pontos)
        dados, fonte = rotas.matriz(self.cli, [c[:2] for c in coords], modo)
        minutos = [[None if v is None else round(v / 60) for v in linha] for linha in dados["duracoes_s"]]
        km = None
        if dados.get("distancias_m"):
            km = [[None if v is None else round(v / 1000, 1) for v in linha] for linha in dados["distancias_m"]]
        aviso = _juntar_avisos(*(c[3] for c in coords), _aviso_distantes(coords, modo))
        return ok(fonte, {"pontos": [c[2] for c in coords], "modo": modo, "minutos": minutos, "km": km}, aviso)

    @_protegido
    def ordenar_dia(self, partida: str, lugares_dia: list[str], voltar: bool = True, modo: str = "pe") -> dict:
        if not 1 <= len(lugares_dia) <= 10:
            raise ValueError("ordenar_dia aceita de 1 a 10 lugares")
        coords = self._coords_com_vies([partida, *lugares_dia])
        dados, fonte = rotas.matriz(self.cli, [c[:2] for c in coords], modo)
        m = dados["duracoes_s"]
        seq = ordem.ordenar(m, voltar)
        nomes = [c[2] for c in coords]
        pts = [0, *seq] + ([0] if voltar else [])
        pernas = []
        for k in range(len(pts) - 1):
            v = m[pts[k]][pts[k + 1]]
            pernas.append({"de": nomes[pts[k]], "para": nomes[pts[k + 1]], "minutos": None if v is None else round(v / 60)})
        t = ordem.total(m, seq, voltar)
        t_dado = ordem.total(m, list(range(1, len(coords))), voltar)
        inalcancavel = "há trecho inalcançável pela rota calculada" if t == float("inf") else None
        aviso = _juntar_avisos(inalcancavel, *(c[3] for c in coords), _aviso_distantes(coords, modo))
        return ok(fonte, {
            "ordem": [nomes[i] for i in seq], "pernas": pernas,
            "total_min": None if inalcancavel else round(t / 60),
            "total_ordem_dada_min": None if t_dado == float("inf") else round(t_dado / 60),
            "obs": "não considera horário de abertura",
        }, aviso)

    @_protegido
    def clima(self, lugar: str, inicio: str, fim: str) -> dict:
        ini, f = _data(inicio), _data(fim)
        la, lo, nome = self._coord(lugar)[:3]
        dados, fonte = clima.clima(self.cli, la, lo, ini, f, hoje=self._hoje())
        return ok(fonte, {"lugar": nome, **dados})

    @_protegido
    def cambio(self, moeda: str, valor: float = 1.0, data: str | None = None, meio: str | None = None) -> dict:
        d = _data(data) if data else self._hoje()
        if meio:
            dados, fonte, aviso = cambio.converter(self.cli, self.cfg, moeda, valor, meio, d, hoje=self._hoje())
            return ok(fonte, dados, aviso)
        t, fonte, aviso = cambio.taxa_brl(self.cli, moeda, d, hoje=self._hoje())
        return ok(fonte, {**t, "valor": valor, "valor_brl": round(valor * t["taxa"], 2)}, aviso)

    @_protegido
    def calendario(self, pais: str, inicio: str, fim: str, regiao: str | None = None, lugar: str | None = None) -> dict:
        ini, f = _data(inicio), _data(fim)
        lista, fonte = calendario.feriados(self.cli, pais, ini, f, regiao)
        dados = {"pais": pais.upper(), "feriados": lista}
        aviso = None
        if lugar:
            la, lo = self._coord(lugar)[:2]
            fz = _fuso(la, lo)
            dados.update({"fuso": fz, "mudancas_horario": calendario.mudancas_horario(fz, ini, f)})
        else:
            aviso = "informe um lugar para ver o fuso e a mudança de horário"
        return ok(fonte, dados, aviso)

    @_protegido
    def custos(self, itens: list[dict], viajantes: int | None = None, data: str | None = None) -> dict:
        d = _data(data) if data else self._hoje()
        fontes: list[str] = []

        def cotar(item, valor):
            if item["moeda"].upper() == "BRL":
                return round(valor, 2), "BRL"
            dados, fonte, _ = cambio.converter(self.cli, self.cfg, item["moeda"], valor, item["meio"], d, hoje=self._hoje())
            if fonte not in fontes:
                fontes.append(fonte)
            return dados["valor_brl"], f"{dados['moeda']} {dados['taxa']} em {dados['data_taxa']} ({dados['meio']})"

        try:
            r = custos.somar(itens, cotar, viajantes)
        except ValueError as e:
            return falha("viagens-motor", str(e))
        return ok(", ".join(fontes) or "sem conversão", r)

    @_protegido
    def spread_da_fatura(self, cartao: str, data_compra: str, moeda: str, valor_moeda: float, valor_reais: float) -> dict:
        dados, fonte = cambio.spread_efetivo(self.cli, self.cfg, cartao, _data(data_compra), moeda, valor_moeda, valor_reais, hoje=self._hoje())
        aviso = dados["observacao"] + "; a atualização do motor-config.toml depende de confirmação"
        return ok(fonte, dados, aviso)


def pasta_dados() -> Path:
    return Path(os.environ.get("VIAGENS_MOTOR_DADOS") or Path.home() / ".local/share/viagens-motor")


def criar_motor() -> Motor:
    cfg = carregar()
    return Motor(cfg, Cliente(Cache(pasta_dados() / "cache.sqlite"), projeto_url=cfg.projeto_url))


def criar_motor_sem_memoria() -> Motor:
    """Motor sem cache, para o verificador: cada checagem consulta a fonte de verdade."""
    cfg = carregar()
    return Motor(cfg, Cliente(None, projeto_url=cfg.projeto_url))
