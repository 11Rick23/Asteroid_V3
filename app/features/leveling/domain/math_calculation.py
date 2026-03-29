PRESTIGE_REQUIRED_SHARD = 268375


def shard_for_next_grade(grade: int) -> int:
    return 5 * grade**2 + 50 * grade + 100


def cumulative_grade_shard(grade: int) -> int:
    return (2 * grade**3 + 27 * grade**2 + 91 * grade) * 5 // 6


def calculation_shard(
    prestige: int, grade: int, shard: int, added_or_removed_shard: int
) -> tuple[int, int, int, int, int]:
    shard += added_or_removed_shard

    grade_up_amount = 0
    prestige_amount = 0

    if added_or_removed_shard < 0:
        grade_up_amount -= grade
        prestige_amount -= prestige

        shard += prestige * PRESTIGE_REQUIRED_SHARD
        shard += cumulative_grade_shard(grade)

        if shard < 0:
            shard = 0

        grade = 0
        prestige = 0

    while True:
        xp_to_level_up = shard_for_next_grade(grade) - shard
        if xp_to_level_up <= 0:
            grade_up_amount += 1
            grade += 1
            shard = abs(xp_to_level_up)

            if grade >= 50:
                prestige_amount += 1
                prestige += 1
                grade -= 50
        else:
            break

    return prestige, grade, shard, grade_up_amount, prestige_amount


def calculation_grade(
    prestige: int, grade: int, shard: int, added_or_removed_grade: int
) -> tuple[int, int, int, int, int, int]:
    target_grade = grade + added_or_removed_grade
    if not 0 <= target_grade < 50:
        raise ValueError(
            "追加または削除後のグレードが不正です、"
            "grade + added_gradeの合計値は0以上49以下である必要がありますが、"
            f"{target_grade}になっています"
        )

    added_or_removed_shard = cumulative_grade_shard(target_grade) - cumulative_grade_shard(grade)

    prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
        prestige, grade, shard, added_or_removed_shard
    )
    return prestige, grade, shard, grade_up_amount, prestige_amount, abs(added_or_removed_shard)


def calculation_prestige(
    prestige: int, grade: int, shard: int, added_or_removed_prestige: int
) -> tuple[int, int, int, int, int, int]:
    next_prestige_required_shard = PRESTIGE_REQUIRED_SHARD * added_or_removed_prestige
    prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
        prestige, grade, shard, next_prestige_required_shard
    )
    return prestige, grade, shard, grade_up_amount, prestige_amount, abs(next_prestige_required_shard)


def next_grade_progress(grade: int, shard: int) -> tuple[int, str]:
    progress = (shard / shard_for_next_grade(grade)) * 100

    progress_bar = "["
    for i in range(1, 10):
        progress_bar += "■" if progress >= 10 * i else "□"
    progress_bar += "]"
    return int(progress), progress_bar


def total_shard_amount(prestige: int, grade: int, shard: int) -> int:
    total = 0
    total += prestige * PRESTIGE_REQUIRED_SHARD
    total += cumulative_grade_shard(grade)
    total += shard
    return total
