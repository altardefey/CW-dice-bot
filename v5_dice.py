import random
from dataclasses import dataclass

SUCCESS_MIN = 6
HUNGER_MIN = 0
HUNGER_MAX = 5


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
    outcome: str

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
        return (
            f"Parada: {self.pool} dados | Fome: {self.hunger}\n"
            f"Dados normais: {normal_txt}\n"
            f"Dados de Fome: {hunger_txt}\n"
            f"Sucessos: {self.successes}\n"
            f"Resultado: {self.outcome}"
        )


def _count_successes(dice: list[int]) -> tuple[int, int]:
    tens = sum(1 for d in dice if d == 10)
    base = sum(1 for d in dice if d >= SUCCESS_MIN)
    pairs = tens // 2
    # cada 10 ja conta 1; cada par adiciona +2, totalizando 4 por par.
    successes = base + (pairs * 2)
    return successes, tens


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

    if successes > 0:
        if is_critical and hunger_tens > 0:
            outcome = "Crítico Bagunçado"
        elif is_critical:
            outcome = "Crítico"
        else:
            outcome = "Sucesso"
    else:
        if hunger_ones > 0:
            outcome = "Falha Bestial"
        else:
            outcome = "Falha"

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
