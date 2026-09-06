import json
import threading
from pathlib import Path

from telegram import User

USUARIOS_PATH = Path(__file__).resolve().parent / "usuarios.json"
_lock = threading.Lock()


def _carregar() -> dict:
    if not USUARIOS_PATH.exists():
        return {}
    try:
        with USUARIOS_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _salvar(data: dict) -> None:
    with USUARIOS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def nome_telegram(user: User) -> str:
    partes = [user.first_name or "", user.last_name or ""]
    nome = " ".join(p for p in partes if p).strip()
    if nome:
        return nome
    if user.username:
        return user.username
    return str(user.id)


def registrar_usuario(user: User | None) -> dict | None:
    if user is None or user.is_bot:
        return None

    chave = str(user.id)
    with _lock:
        data = _carregar()
        atual = data.get(chave, {})
        registro = {
            "id": user.id,
            "nome": nome_telegram(user),
            "username": user.username,
            "ficha": atual.get("ficha"),
        }
        data[chave] = registro
        _salvar(data)
    return registro


def obter_usuario(user_id: int) -> dict | None:
    with _lock:
        return _carregar().get(str(user_id))


def ligar_ficha(user_id: int, ficha: str, user: User | None = None) -> dict:
    with _lock:
        data = _carregar()
        chave = str(user_id)
        atual = data.get(chave, {})
        registro = {
            "id": user_id,
            "nome": nome_telegram(user) if user is not None else atual.get("nome", str(user_id)),
            "username": user.username if user is not None else atual.get("username"),
            "ficha": ficha,
        }
        data[chave] = registro
        _salvar(data)
    return registro
