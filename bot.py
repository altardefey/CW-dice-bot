import os
import logging
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import fichas as fichas_mod
from usuarios import ligar_ficha, obter_usuario, registrar_usuario
from v5_dice import (
    HUNGER_MAX,
    formatar_remorso,
    formatar_rouse,
    roll_pool,
    roll_rouse,
    roll_simple,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

AJUDA = (
    "Bot de dados de Vampire: The Masquerade 5a Edição pro melhor RPG de VTM (Crimson Waltz).\n\n"
    "/ficha  - Mostra a ficha ligada ao seu ID\n"
    "/ficha ligar <nome>  - Liga uma ficha ao seu ID\n"
    "/roll <parada>\n"
    "/roll remorso\n"
    "/roll check - Faz um rouse check.\n"
    "/macula - Mostra sua humanidade e manchas.\n"
    "/vida superficial - Adiciona dano superficial na vida.\n"
    "/vida agravado - Adiciona dano agravado na vida.\n"
    "/vontade superficial - Adiciona dano superficial na força de vontade.\n"
    "/vontade agravado - Adiciona dano agravado na força de vontade.\n"
    "/remover vontade - Remove todo o dano da força de vontade.\n"
)


def _lista_fichas_txt() -> str:
    nomes = fichas_mod.nomes_disponiveis()
    if not nomes:
        return "Nenhuma ficha encontrada na pasta fichas."
    return "Fichas disponiveis:\n" + "\n".join(f"- {n}" for n in nomes)


def _carregar_ficha_do_usuario(user_id: int) -> tuple[dict, Path] | str:
    registro = obter_usuario(user_id)
    ref = (registro or {}).get("ficha")
    if not ref:
        return (
            "Você ainda não tem uma ficha ligada.\n"
            "Use /ficha ligar <nome>\n\n" + _lista_fichas_txt()
        )
    caminho = fichas_mod.resolver_ficha(str(ref))
    if caminho is None:
        caminho = fichas_mod.FICHAS_DIR / f"{ref}.json"
        if not caminho.exists():
            return (
                "A ficha ligada nao foi encontrada.\n"
                "Use /ficha ligar <nome>\n\n" + _lista_fichas_txt()
            )
    return fichas_mod.carregar(caminho), caminho


async def _responder(
    update: Update,
    texto: str,
    parse_mode: str | None = None,
) -> None:
    if update.message is not None:
        await update.message.reply_text(texto, parse_mode=parse_mode)


def _tipo_dano(args: list[str]) -> str | None:
    if not args:
        return None
    tipo = args[0].lower()
    if tipo in {"superficial", "superf", "s"}:
        return "superficial"
    if tipo in {"agravado", "agravada", "a"}:
        return "agravado"
    return None


async def registrar_uso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    registrar_usuario(update.effective_user)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, AJUDA)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def _ligar_ficha(update: Update, user, referencia: str) -> None:
    if not referencia.strip():
        await _responder(
            update,
            "Uso: /ficha ligar <nome>\nExemplo: /ficha ligar Janja",
        )
        return
    caminho = fichas_mod.resolver_ficha(referencia)
    if caminho is None:
        await _responder(update, "Ficha não encontrada.")
        return
    fichas_mod.carregar(caminho)
    ligar_ficha(user.id, caminho.stem, user)
    await _responder(update, "Ficha ligada.")


async def cmd_ficha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    args = context.args or []
    if args and args[0].lower() == "ligar":
        await _ligar_ficha(update, user, " ".join(args[1:]))
        return
    if args:
        await _ligar_ficha(update, user, " ".join(args))
        return

    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, _caminho = carregado
    await _responder(
        update,
        fichas_mod.formatar_ficha(dados),
        parse_mode=ParseMode.HTML,
    )


async def cmd_macula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    status["humanidade"]["manchas"] = int(status["humanidade"].get("manchas") or 0) + 1
    fichas_mod.salvar(caminho, dados)
    nome = dados.get("nome") or caminho.stem
    hum = status["humanidade"]
    await _responder(
        update,
        f"┈─┼ ㅤMácula: {nome}\n"
        f"▏ᅟᅟ   • Humanidade: {hum['total']}\n"
        f"▏ᅟ       • Manchas: {hum['manchas']}",
    )


async def _aplicar_trilha(
    update: Update,
    chave: str,
    titulo: str,
    tipo: str | None,
    uso: str,
) -> None:
    user = update.effective_user
    if user is None:
        return
    if tipo is None:
        await _responder(update, uso)
        return
    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    trilha = status[chave]
    total = int(trilha.get("total") or 0)
    if total <= 0:
        await _responder(update, f"Esta ficha nao tem {titulo} definida.")
        return
    agrav_antes = int(trilha.get("dano_agravado") or 0)
    if tipo == "agravado" and agrav_antes >= total:
        await _responder(
            update,
            fichas_mod.formatar_dano(
                str(dados.get("nome") or caminho.stem),
                titulo,
                trilha,
                "Trilha já esta cheia de dano agravado. Vai morrer, zé.",
            ),
        )
        return
    fichas_mod.aplicar_dano(trilha, tipo, 1)
    fichas_mod.salvar(caminho, dados)
    await _responder(
        update,
        fichas_mod.formatar_dano(
            str(dados.get("nome") or caminho.stem),
            titulo,
            trilha,
            f"Dano {tipo} aplicado.",
        ),
    )


async def cmd_vida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _aplicar_trilha(
        update,
        "vida",
        "Vida",
        _tipo_dano(context.args or []),
        "Uso: /vida superficial\nou /vida agravado",
    )


async def cmd_vontade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _aplicar_trilha(
        update,
        "forca_de_vontade",
        "Força de Vontade",
        _tipo_dano(context.args or []),
        "Uso: /vontade superficial\nou /vontade agravado",
    )


async def cmd_remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.lower() for a in (context.args or [])]
    if not args or args[0] != "vontade":
        await _responder(
            update,
            "Uso: /remover vontade\n"
            "Tambem: /remover vontade superficial\n"
            "ou /remover vontade agravado",
        )
        return
    await cmd_remover_vontade(update, context)


async def cmd_remover_vontade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    trilha = status["forca_de_vontade"]
    args = [a.lower() for a in (context.args or [])]
    if args and args[0] == "vontade":
        args = args[1:]
    tipo = _tipo_dano(args) if args else None

    if tipo == "superficial":
        trilha["dano_superficial"] = 0
        acao = "Dano superficial de Força de Vontade apagado."
    elif tipo == "agravado":
        trilha["dano_agravado"] = 0
        acao = "Dano agravado de Força de Vontade apagado."
    else:
        trilha["dano_superficial"] = 0
        trilha["dano_agravado"] = 0
        acao = "Dano de Força de Vontade apagado."

    fichas_mod.salvar(caminho, dados)
    await _responder(
        update,
        fichas_mod.formatar_dano(
            str(dados.get("nome") or caminho.stem),
            "Força de Vontade",
            trilha,
            acao,
        ),
    )


async def roll_remorso(update: Update, user_id: int) -> None:
    carregado = _carregar_ficha_do_usuario(user_id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    humanidade = int(status["humanidade"].get("total") or 0)
    maculas = int(status["humanidade"].get("manchas") or 0)
    nome = str(dados.get("nome") or caminho.stem)

    if maculas < 1:
        await _responder(
            update,
            f"{nome} não tem manchas de Humanidade. Use /macula antes do teste de remorso.",
        )
        return

    pool = max(1, 10 - humanidade - maculas)
    dice, successes = roll_simple(pool)
    manteve = successes >= 1
    if not manteve:
        status["humanidade"]["total"] = max(0, humanidade - 1)
    status["humanidade"]["manchas"] = 0
    fichas_mod.salvar(caminho, dados)

    await _responder(
        update,
        formatar_remorso(
            nome=nome,
            pool=pool,
            dice=dice,
            successes=successes,
            humanidade_antes=humanidade,
            humanidade_depois=int(status["humanidade"]["total"]),
            maculas_antes=maculas,
            manteve=manteve,
        ),
    )


async def roll_check(update: Update, user_id: int) -> None:
    carregado = _carregar_ficha_do_usuario(user_id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    fome_antes = int(status.get("fome") or 0)
    nome = str(dados.get("nome") or caminho.stem)
    dado, passou = roll_rouse()
    fome_depois = fome_antes
    if not passou:
        fome_depois = min(HUNGER_MAX, fome_antes + 1)
        status["fome"] = fome_depois
        fichas_mod.salvar(caminho, dados)

    await _responder(
        update,
        formatar_rouse(
            nome=nome,
            dado=dado,
            fome_antes=fome_antes,
            fome_depois=int(status.get("fome") or 0),
            passou=passou,
        ),
    )


async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    user = update.effective_user
    args = context.args or []
    if args and args[0].lower() == "remorso":
        if user is None:
            return
        await roll_remorso(update, user.id)
        return
    if args and args[0].lower() in {"check", "rouse"}:
        if user is None:
            return
        await roll_check(update, user.id)
        return

    if len(args) != 1:
        await update.message.reply_text(
            "Uso:\n"
            "/roll <parada>\n"
            "/roll remorso\n"
            "/roll check"
        )
        return

    try:
        pool = int(args[0])
    except ValueError:
        await update.message.reply_text(
            "A parada de dados precisa ser um numero inteiro.\n"
            "Exemplo: /roll 6"
        )
        return

    if pool < 1:
        await update.message.reply_text("A parada de dados precisa ser pelo menos 1.")
        return
    if pool > 50:
        await update.message.reply_text("Parada máxima permitida: 50 dados.")
        return
    if user is None:
        return

    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, _caminho = carregado
    hunger = int(fichas_mod.garantir_status(dados)["fome"] or 0)
    result = roll_pool(pool, hunger)
    await update.message.reply_text(result.format_message())


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if not TOKEN:
        raise SystemExit(
            "Defina TELEGRAM_BOT_TOKEN no arquivo .env ou no ambiente."
        )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, registrar_uso), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ficha", cmd_ficha))
    app.add_handler(CommandHandler("macula", cmd_macula))
    app.add_handler(CommandHandler("vida", cmd_vida))
    app.add_handler(CommandHandler("vontade", cmd_vontade))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("remover_vontade", cmd_remover_vontade))
    app.add_handler(CommandHandler("roll", roll))

    logger.info("Bot iniciado. Aguardando comandos.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
