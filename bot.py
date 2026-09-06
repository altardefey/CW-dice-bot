import os
import logging
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import fichas as fichas_mod
from usuarios import ligar_ficha, obter_usuario, registrar_usuario
from v5_dice import (
    HUNGER_MAX,
    HUNGER_MIN,
    formatar_remorso,
    formatar_rouse,
    formatar_vontade,
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
    "Bot de dados de Vampire: The Masquerade 5a Edicao.\n\n"
    "Primeiro ligue sua ficha:\n"
    "/ficha <nome>\n\n"
    "/roll <parada> <fome>  - rolagem normal\n"
    "/roll remorso  - teste de remorso (altera a ficha)\n"
    "/roll check  - rouse check (altera a ficha)\n"
    "/macula  - adiciona 1 macula de Humanidade\n"
    "/vontade  - adiciona 1 mancha de Forca de Vontade\n"
    "/remover vontade  - apaga as manchas de Forca de Vontade"
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
            "Voce ainda nao tem uma ficha ligada.\n"
            "Use /ficha <nome>\n\n" + _lista_fichas_txt()
        )
    caminho = fichas_mod.resolver_ficha(str(ref))
    if caminho is None:
        caminho = fichas_mod.FICHAS_DIR / f"{ref}.json"
        if not caminho.exists():
            return (
                "A ficha ligada nao foi encontrada.\n"
                "Use /ficha <nome>\n\n" + _lista_fichas_txt()
            )
    return fichas_mod.carregar(caminho), caminho


async def _responder(update: Update, texto: str) -> None:
    if update.message is not None:
        await update.message.reply_text(texto)


async def registrar_uso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    registrar_usuario(update.effective_user)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, AJUDA)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def cmd_ficha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    args = context.args or []
    if not args:
        await _responder(
            update,
            "Uso: /ficha <nome>\nExemplo: /ficha aurik\n\n" + _lista_fichas_txt(),
        )
        return
    referencia = " ".join(args)
    caminho = fichas_mod.resolver_ficha(referencia)
    if caminho is None:
        await _responder(
            update,
            "Ficha nao encontrada.\n\n" + _lista_fichas_txt(),
        )
        return
    dados = fichas_mod.carregar(caminho)
    ligar_ficha(user.id, caminho.stem, user)
    nome = dados.get("nome") or caminho.stem
    await _responder(update, f"Ficha ligada: {nome} ({caminho.stem}.json)")


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
    status["maculas"] = int(status.get("maculas") or 0) + 1
    fichas_mod.salvar(caminho, dados)
    nome = dados.get("nome") or caminho.stem
    await _responder(
        update,
        f"┈─┼ ㅤMacula: {nome}\n"
        f"▏ᅟᅟ   • Maculas de Humanidade: {status['maculas']}",
    )


async def cmd_vontade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    carregado = _carregar_ficha_do_usuario(user.id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    maximo = int(status.get("forca_de_vontade") or 0)
    manchas = int(status.get("manchas_vontade") or 0)
    if maximo <= 0:
        await _responder(update, "Esta ficha nao tem Forca de Vontade definida.")
        return
    if manchas >= maximo:
        await _responder(
            update,
            formatar_vontade(
                str(dados.get("nome") or caminho.stem),
                manchas,
                maximo,
                "Forca de Vontade ja esta cheia de manchas.",
            ),
        )
        return
    manchas += 1
    status["manchas_vontade"] = manchas
    fichas_mod.salvar(caminho, dados)
    await _responder(
        update,
        formatar_vontade(
            str(dados.get("nome") or caminho.stem),
            manchas,
            maximo,
            "Mancha adicionada.",
        ),
    )


async def cmd_remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.lower() for a in (context.args or [])]
    if args != ["vontade"]:
        await _responder(update, "Uso: /remover vontade")
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
    maximo = int(status.get("forca_de_vontade") or 0)
    status["manchas_vontade"] = 0
    fichas_mod.salvar(caminho, dados)
    await _responder(
        update,
        formatar_vontade(
            str(dados.get("nome") or caminho.stem),
            0,
            maximo,
            "Manchas de Forca de Vontade apagadas.",
        ),
    )


async def roll_remorso(update: Update, user_id: int) -> None:
    carregado = _carregar_ficha_do_usuario(user_id)
    if isinstance(carregado, str):
        await _responder(update, carregado)
        return
    dados, caminho = carregado
    status = fichas_mod.garantir_status(dados)
    humanidade = int(status.get("humanidade") or 0)
    maculas = int(status.get("maculas") or 0)
    nome = str(dados.get("nome") or caminho.stem)

    if maculas < 1:
        await _responder(
            update,
            f"{nome} nao tem maculas. Use /macula antes do teste de remorso.",
        )
        return

    pool = max(1, 10 - humanidade - maculas)
    dice, successes = roll_simple(pool)
    manteve = successes >= 1
    if not manteve:
        status["humanidade"] = max(0, humanidade - 1)
    status["maculas"] = 0
    fichas_mod.salvar(caminho, dados)

    await _responder(
        update,
        formatar_remorso(
            nome=nome,
            pool=pool,
            dice=dice,
            successes=successes,
            humanidade_antes=humanidade,
            humanidade_depois=int(status["humanidade"]),
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

    if len(args) != 2:
        await update.message.reply_text(
            "Uso:\n"
            "/roll <parada> <fome>\n"
            "/roll remorso\n"
            "/roll check"
        )
        return

    try:
        pool = int(args[0])
        hunger = int(args[1])
    except ValueError:
        await update.message.reply_text(
            "Os dois argumentos precisam ser numeros inteiros.\n"
            "Exemplo: /roll 6 2"
        )
        return

    if pool < 1:
        await update.message.reply_text("A parada de dados precisa ser pelo menos 1.")
        return
    if pool > 50:
        await update.message.reply_text("Parada maxima permitida: 50 dados.")
        return
    if hunger < HUNGER_MIN or hunger > HUNGER_MAX:
        await update.message.reply_text(
            f"O nivel de Fome deve estar entre {HUNGER_MIN} e {HUNGER_MAX}."
        )
        return

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
    app.add_handler(CommandHandler("vontade", cmd_vontade))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("remover_vontade", cmd_remover_vontade))
    app.add_handler(CommandHandler("roll", roll))

    logger.info("Bot iniciado. Aguardando comandos.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
