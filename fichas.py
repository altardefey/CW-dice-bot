import json
import threading
from html import escape
from pathlib import Path

from v5_dice import HUNGER_MAX

FICHAS_DIR = Path(__file__).resolve().parent / "fichas"
_lock = threading.Lock()

ATRIBUTO_NOMES = {
    "forca": "Forca",
    "destreza": "Destreza",
    "vigor": "Vigor",
    "carisma": "Carisma",
    "manipulacao": "Manipulacao",
    "autocontrole": "Autocontrole",
    "inteligencia": "Inteligencia",
    "raciocinio": "Raciocinio",
    "determinacao": "Determinacao",
}

HABILIDADE_NOMES = {
    "armas_brancas": "Armas brancas",
    "armas_de_fogo": "Armas de fogo",
    "atletismo": "Atletismo",
    "briga": "Briga",
    "conducao": "Conducao",
    "furtividade": "Furtividade",
    "ladroagem": "Ladroagem",
    "oficios": "Oficios",
    "sobrevivencia": "Sobrevivencia",
    "empatia_com_animais": "Empatia com animais",
    "etiqueta": "Etiqueta",
    "intimidacao": "Intimidacao",
    "lideranca": "Lideranca",
    "manha": "Manha",
    "performance": "Performance",
    "persuasao": "Persuasao",
    "sagacidade": "Sagacidade",
    "subterfugio": "Subterfugio",
    "ciencia": "Ciencia",
    "erudicao": "Erudicao",
    "financas": "Financas",
    "investigacao": "Investigacao",
    "medicina": "Medicina",
    "ocultismo": "Ocultismo",
    "percepcao": "Percepcao",
    "politica": "Politica",
    "tecnologia": "Tecnologia",
}


def _norm(texto: str) -> str:
    return "".join(ch for ch in texto.lower() if ch.isalnum())


def _trilha_dano(valor, total_padrao: int = 0) -> dict:
    if isinstance(valor, dict):
        return {
            "total": int(valor.get("total") or total_padrao),
            "dano_superficial": int(valor.get("dano_superficial") or 0),
            "dano_agravado": int(valor.get("dano_agravado") or 0),
        }
    return {
        "total": int(valor or total_padrao),
        "dano_superficial": 0,
        "dano_agravado": 0,
    }


def _humanidade(valor) -> dict:
    if isinstance(valor, dict):
        return {
            "total": int(valor.get("total") or 0),
            "manchas": int(valor.get("manchas") or valor.get("maculas") or 0),
        }
    return {"total": int(valor or 0), "manchas": 0}


def garantir_status(ficha: dict) -> dict:
    status = ficha.setdefault("status", {})
    status["vida"] = _trilha_dano(status.get("vida"))
    status["forca_de_vontade"] = _trilha_dano(status.get("forca_de_vontade"))
    status["humanidade"] = _humanidade(status.get("humanidade"))
    status["fome"] = int(status.get("fome") or 0)
    status.pop("maculas", None)
    status.pop("manchas_vontade", None)
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
        primeiros_nomes = {
            _norm(caminho.stem.split("_")[0]),
            _norm(nome.split()[0]) if nome.split() else "",
        }
        primeiros_nomes.discard("")
        if alvo in primeiros_nomes:
            return caminho
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


def barras_trilha(trilha: dict) -> str:
    total = max(0, int(trilha.get("total") or 0))
    agrav = min(total, int(trilha.get("dano_agravado") or 0))
    superf = min(total - agrav, int(trilha.get("dano_superficial") or 0))
    caixas: list[str] = []
    for i in range(total):
        if i < agrav:
            caixas.append("X")
        elif i < agrav + superf:
            caixas.append("/")
        else:
            caixas.append("-")
    if not caixas:
        return "(sem trilha)"
    return "[" + "][".join(caixas) + "]"


def aplicar_dano(trilha: dict, tipo: str, quantidade: int = 1) -> dict:
    total = max(0, int(trilha.get("total") or 0))
    agrav = min(total, int(trilha.get("dano_agravado") or 0))
    superf = min(total - agrav, int(trilha.get("dano_superficial") or 0))
    tipo_norm = tipo.lower()

    for _ in range(max(0, quantidade)):
        livres = total - superf - agrav
        if tipo_norm.startswith("super"):
            if livres > 0:
                superf += 1
            elif agrav < total:
                if superf > 0:
                    superf -= 1
                agrav += 1
        else:
            if agrav >= total:
                break
            if livres > 0:
                agrav += 1
            elif superf > 0:
                superf -= 1
                agrav += 1

    trilha["total"] = total
    trilha["dano_superficial"] = superf
    trilha["dano_agravado"] = agrav
    return trilha


def formatar_ficha(dados: dict) -> str:
    garantir_status(dados)
    status = dados["status"]
    nome = str(dados.get("nome") or "Sem nome").upper()
    cla = dados.get("cla")
    cla_txt = str(cla or "sem cla").upper()
    return "\n".join(
        [
            f"┈─┼ <b>{escape(nome)}</b>",
            f"┈─┼ <b>{escape(cla_txt)}</b>",
            "",
                "   ── ٠ 𝗩𝗜𝗗𝗔:",
                f"      {formatar_trilha(status['vida'])}",
                "   ── ٠ 𝗙𝗢𝗥𝗖̧𝗔 𝗗𝗘 𝗩𝗢𝗡𝗧𝗔𝗗𝗘:",
                f"      {formatar_trilha(status['forca_de_vontade'])}",
                "   ── ٠ 𝗙𝗢𝗠𝗘:",
                f"      {formatar_fome(status['fome'])}",
                f"   ── ٠ 𝗛𝗨𝗠𝗔𝗡𝗜𝗗𝗔𝗗𝗘: {status['humanidade']['total']}",
        ]
    )


def formatar_trilha(trilha: dict) -> str:
    total = max(0, int(trilha.get("total") or 0))
    superficial = min(total, max(0, int(trilha.get("dano_superficial") or 0)))
    agravado = min(total - superficial, max(0, int(trilha.get("dano_agravado") or 0)))
    vazio = total - superficial - agravado
    return " ".join(["◩"] * superficial + ["■"] * agravado + ["□"] * vazio)


def formatar_fome(fome: int) -> str:
    fome_atual = max(0, min(HUNGER_MAX, int(fome or 0)))
    return " ".join(["■"] * fome_atual + ["□"] * (HUNGER_MAX - fome_atual))


def formatar_dano(nome: str, titulo: str, trilha: dict, acao: str) -> str:
    return "\n".join(
        [
            f"┈─┼ ㅤ{titulo}: {nome}",
            f"▏ᅟᅟ   • {acao}",
            f"▏ᅟ       • {barras_trilha(trilha)}",
            f"▏ᅟ       • Superficial: {trilha.get('dano_superficial', 0)} | "
            f"Agravado: {trilha.get('dano_agravado', 0)} / {trilha.get('total', 0)}",
        ]
    )
