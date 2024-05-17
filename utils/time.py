def sing(amount: int, unit: str, brief: bool) -> str:
    if brief:
        return f"{amount}{amount == 1 and f'{unit}' or f'{unit}'}"
    return f"{amount} {amount == 1 and f'{unit}' or f'{unit}s'}"


def deltaconv(seconds: int, *, brief: bool = False, short: bool = False) -> str:
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    dys, hrs = divmod(hrs, 24)

    timedict = {"day": dys, "hour": hrs, "minute": mins, "second": secs}
    if brief:
        timedict = {"d": dys, "h": hrs, "m": mins, "s": secs}

    cleaned = {k: v for k, v in timedict.items() if v != 0}

    if short:
        for unit, amount in cleaned.items():
            if amount:
                return sing(int(amount), unit, brief)

    return " ".join(sing(int(amount), unit, brief) for unit, amount in cleaned.items())
