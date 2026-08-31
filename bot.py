import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from v5_dice import HUNGER_MAX, HUNGER_MIN, roll_pool

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Bot de dados de Vampire: The Masquerade 5a Edicao.\n\n"
        "Use /roll <parada> <fome>\n"
        "Exemplo: /roll 6 2\n\n"
        "Sucesso: 6 a 10. Pares de 10 valem 4 sucessos. "
        "Dados de Fome substituem dados da parada ate o nivel de Fome."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    args = context.args or []
    if len(args) != 2:
        await update.message.reply_text(
            "Uso: /roll <parada> <fome>\nExemplo: /roll 6 2"
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
    if not TOKEN:
        raise SystemExit(
            "Defina TELEGRAM_BOT_TOKEN no arquivo .env ou no ambiente."
        )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("roll", roll))

    logger.info("Bot iniciado. Aguardando comandos.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
