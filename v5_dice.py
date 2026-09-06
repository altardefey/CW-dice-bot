import random
from dataclasses import dataclass

SUCCESS_MIN = 6
HUNGER_MIN = 0
HUNGER_MAX = 5

OUTCOME_MESSY = "messy"
OUTCOME_BESTIAL = "bestial"

TEXTO_CRITICO_BAGUNCADO = "𝗖𝗥𝗜𝗧𝗜𝗖𝗢 𝗕𝗔𝗚𝗨𝗡𝗖̧𝗔𝗗𝗢."
TEXTO_FALHA_BESTIAL = "𝗙𝗔𝗟𝗛𝗔 𝗕𝗘𝗦𝗧𝗜𝗔𝗟."


@dataclass
class RollResult:
    pool: int
    hunger: int
    normal_dice: list[int]
    hunger_dice: list[int]
    successes: int
    tens: int
    hunger_tens: int
    hunger_ones: int
    outcome: str | None

    def format_message(self) -> str:
        normal_txt = (
            ", ".join(str(d) for d in self.normal_dice)
            if self.normal_dice
            else "(nenhum)"
        )
        hunger_txt = (
            ", ".join(str(d) for d in self.hunger_dice)
            if self.hunger_dice
            else "(nenhum)"
        )
        linhas = [
            f"┈─┼ ㅤPᥲrᥲdᥲ: {self.pool} dᥲdos | Fomᥱ: {self.hunger}",
            f"▏ᅟᅟ   • Dᥲdos ᥒormᥲιs: {normal_txt}",
            f"▏ᅟ       • Dᥲdos dᥱ Fomᥱ: {hunger_txt}",
            f"▏ᅟ       • Sᥙᥴᥱssos: {self.successes}",
        ]
        if self.outcome == OUTCOME_MESSY:
            linhas.append("")
            linhas.append("✷ ᅟRᥱsᥙᥣtᥲdo:")
            linhas.append(TEXTO_CRITICO_BAGUNCADO)
        elif self.outcome == OUTCOME_BESTIAL:
            linhas.append("")
            linhas.append("✷ ᅟRᥱsᥙᥣtᥲdo:")
            linhas.append(TEXTO_FALHA_BESTIAL)
        return "\n".join(linhas)


def _count_successes(dice: list[int]) -> tuple[int, int]:
    tens = sum(1 for d in dice if d == 10)
    base = sum(1 for d in dice if d >= SUCCESS_MIN)
    pairs = tens // 2
    successes = base + (pairs * 2)
    return successes, tens


def roll_simple(pool: int) -> tuple[list[int], int]:
    dice = [random.randint(1, 10) for _ in range(max(0, pool))]
    successes, _ = _count_successes(dice)
    return dice, successes


def roll_rouse() -> tuple[int, bool]:
    dado = random.randint(1, 10)
    return dado, dado >= SUCCESS_MIN


def formatar_remorso(
    nome: str,
    pool: int,
    dice: list[int],
    successes: int,
    humanidade_antes: int,
    humanidade_depois: int,
    maculas_antes: int,
    manteve: bool,
) -> str:
    dados_txt = ", ".join(str(d) for d in dice) if dice else "(nenhum)"
    if manteve:
        resultado = "Humanidade mantida. Maculas apagadas."
    else:
        resultado = "Humanidade -1. Maculas apagadas."
    return "\n".join(
        [
            f"┈─┼ ㅤRᥱmorso: {nome}",
            f"▏ᅟᅟ   • Pᥲrᥲdᥲ: {pool} dᥲdos (10 - {humanidade_antes} Hum. - {maculas_antes} maculas)",
            f"▏ᅟ       • Dᥲdos: {dados_txt}",
            f"▏ᅟ       • Sᥙᥴᥱssos: {successes}",
            f"▏ᅟ       • Hᥙmᥲᥒιdᥲdᥱ: {humanidade_depois}",
            "",
            "✷ ᅟRᥱsᥙᥣtᥲdo:",
            resultado,
        ]
    )


def formatar_rouse(
    nome: str,
    dado: int,
    fome_antes: int,
    fome_depois: int,
    passou: bool,
) -> str:
    if passou:
        resultado = "Rouse check bem-sucedido. Fome inalterada."
    elif fome_antes >= HUNGER_MAX:
        resultado = "Rouse check falhou. Fome ja estava em 5. Risco de Frenesi de Fome."
    else:
        resultado = f"Rouse check falhou. Fome {fome_antes} -> {fome_depois}."
    return "\n".join(
        [
            f"┈─┼ ㅤRoᥙsᥱ Chᥱck: {nome}",
            f"▏ᅟᅟ   • Dᥲdo: {dado}",
            f"▏ᅟ       • Fomᥱ: {fome_depois}",
            "",
            "✷ ᅟRᥱsᥙᥣtᥲdo:",
            resultado,
        ]
    )


def formatar_vontade(nome: str, manchas: int, maximo: int, acao: str) -> str:
    return "\n".join(
        [
            f"┈─┼ ㅤForca de Vontade: {nome}",
            f"▏ᅟᅟ   • {acao}",
            f"▏ᅟ       • Manchas: {manchas} / {maximo}",
        ]
    )


def roll_pool(pool: int, hunger: int) -> RollResult:
    hunger_dice_count = min(hunger, pool)
    normal_dice_count = pool - hunger_dice_count

    normal_dice = [random.randint(1, 10) for _ in range(normal_dice_count)]
    hunger_dice = [random.randint(1, 10) for _ in range(hunger_dice_count)]
    all_dice = normal_dice + hunger_dice

    successes, tens = _count_successes(all_dice)
    hunger_tens = sum(1 for d in hunger_dice if d == 10)
    hunger_ones = sum(1 for d in hunger_dice if d == 1)
    is_critical = tens >= 2

    if is_critical and hunger_tens > 0:
        outcome = OUTCOME_MESSY
    elif successes == 0 and hunger_ones > 0:
        outcome = OUTCOME_BESTIAL
    else:
        outcome = None

    return RollResult(
        pool=pool,
        hunger=hunger,
        normal_dice=normal_dice,
        hunger_dice=hunger_dice,
        successes=successes,
        tens=tens,
        hunger_tens=hunger_tens,
        hunger_ones=hunger_ones,
        outcome=outcome,
    )
