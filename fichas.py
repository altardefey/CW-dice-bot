import json
import threading
from pathlib import Path

FICHAS_DIR = Path(__file__).resolve().parent / "fichas"
_lock = threading.Lock()


def _norm(texto: str) -> str:
    return "".join(ch for ch in texto.lower() if ch.isalnum())


def garantir_status(ficha: dict) -> dict:
    status = ficha.setdefault("status", {})
    status.setdefault("vida", 0)
    status.setdefault("forca_de_vontade", 0)
    status.setdefault("humanidade", 0)
    status.setdefault("fome", 0)
    status.setdefault("maculas", 0)
    status.setdefault("manchas_vontade", 0)
    return status


def listar_arquivos() -> list[Path]:
    if not FICHAS_DIR.is_dir():
        return []
    return sorted(FICHAS_DIR.glob("*.json"))


def nomes_disponiveis() -> list[str]:
    nomes: list[str] = []
    for caminho in listar_arquivos():
        try:
            with caminho.open(encoding="utf-8") as f:
                dados = json.load(f)
            nome = dados.get("nome") or caminho.stem
        except (json.JSONDecodeError, OSError):
            nome = caminho.stem
        nomes.append(f"{caminho.stem} ({nome})")
    return nomes


def resolver_ficha(referencia: str) -> Path | None:
    alvo = _norm(referencia)
    if not alvo:
        return None

    candidatos: list[tuple[int, Path]] = []
    for caminho in listar_arquivos():
        try:
            with caminho.open(encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, OSError):
            dados = {}
        nome = str(dados.get("nome") or "")
        chaves = [_norm(caminho.stem), _norm(nome)]
        if alvo in chaves:
            return caminho
        for chave in chaves:
            if alvo in chave or chave in alvo:
                candidatos.append((abs(len(chave) - len(alvo)), caminho))

    if len(candidatos) == 1:
        return candidatos[0][1]
    if candidatos:
        candidatos.sort()
        if candidatos[0][0] == 0:
            return candidatos[0][1]
    return None


def carregar(caminho: Path) -> dict:
    with caminho.open(encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict):
        raise ValueError("Ficha invalida.")
    garantir_status(dados)
    return dados


def salvar(caminho: Path, dados: dict) -> None:
    garantir_status(dados)
    with _lock:
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
            f.write("\n")
