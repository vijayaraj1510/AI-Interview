ALLOWED_ANSWERS = {"A", "B", "C", "D"}


def required_fields(data, fields):
    return [field for field in fields if not (data.get(field) or "").strip()]


def valid_answer(answer):
    return (answer or "").upper() in ALLOWED_ANSWERS


def clean_int(value, default=0, minimum=0, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number
