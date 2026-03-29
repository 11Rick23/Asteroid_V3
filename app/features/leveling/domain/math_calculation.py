def calculation_shard(
    prestige: int, grade: int, shard: int, added_or_removed_shard: int
) -> tuple[int, int, int, int, int]:
    shard += added_or_removed_shard

    grade_up_amount = 0
    prestige_amount = 0

    if added_or_removed_shard < 0:
        grade_up_amount -= grade
        prestige_amount -= prestige

        shard += prestige * 268375
        shard += (2 * grade**3 + 27 * grade**2 + 91 * grade) * 5 // 6

        if shard < 0:
            shard = 0

        grade = 0
        prestige = 0

    while True:
        xp_to_level_up = 5 * (grade**2) + (50 * grade) + 100 - shard
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
    if grade + added_or_removed_grade > 50:
        raise ValueError(
            "追加するグレード数が多すぎます、"
            "grade + added_gradeの合計値は50以下である必要がありますが、"
            f"{grade + added_or_removed_grade}になっています"
        )

    next_grade_required_shard = 0
    for i in range(added_or_removed_grade):
        next_grade_required_shard += 5 * ((grade + i) ** 2) + (50 * (grade + i)) + 100

    prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
        prestige, grade, shard, next_grade_required_shard
    )
    return prestige, grade, shard, grade_up_amount, prestige_amount, next_grade_required_shard


def calculation_prestige(
    prestige: int, grade: int, shard: int, added_or_removed_prestige: int
) -> tuple[int, int, int, int, int, int]:
    next_prestige_required_shard = 268375 * added_or_removed_prestige
    prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
        prestige, grade, shard, next_prestige_required_shard
    )
    return prestige, grade, shard, grade_up_amount, prestige_amount, next_prestige_required_shard


def next_grade_progress(grade: int, shard: int) -> tuple[int, str]:
    progress = (shard / (5 * (grade**2 + 10 * grade + 20))) * 100

    progress_bar = "["
    for i in range(1, 10):
        progress_bar += "■" if progress >= 10 * i else "□"
    progress_bar += "]"
    return int(progress), progress_bar


def total_shard_amount(prestige: int, grade: int, shard: int) -> int:
    total = 0
    total += prestige * 268375
    total += (2 * grade**3 + 27 * grade**2 + 91 * grade) * 5 // 6
    total += shard
    return total
