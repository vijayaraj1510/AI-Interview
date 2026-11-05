from utils.database import query, execute


def is_correct_response(question, answer):
    """Accept an MCQ letter or the complete option text for typed technical answers."""
    normalized = " ".join(str(answer or "").strip().casefold().split())
    correct_letter = question["correct_answer_snapshot"].casefold()
    correct_option = question[f"option_{correct_letter}_snapshot"]
    normalized_option = " ".join(str(correct_option or "").strip().casefold().split())
    return normalized in {correct_letter, normalized_option}


def get_attempt_with_questions(attempt_id, user_id=None):
    params = [attempt_id]
    owner = ""
    if user_id:
        owner = " AND user_id=?"
        params.append(user_id)
    attempt = query(f"SELECT * FROM assessment_attempts WHERE id=?{owner}", params, one=True)
    questions = query("SELECT * FROM assessment_questions WHERE attempt_id=? ORDER BY question_order", (attempt_id,))
    answers = {a["assessment_question_id"]: a for a in query("SELECT * FROM assessment_answers WHERE attempt_id=?", (attempt_id,))}
    return attempt, questions, answers


def submit_attempt(attempt_id, selected, time_taken):
    attempt, questions, _ = get_attempt_with_questions(attempt_id)
    if query("SELECT id FROM assessment_answers WHERE attempt_id=? LIMIT 1", (attempt_id,), one=True):
        return attempt_id
    correct = wrong = unanswered = obtained = 0
    total_marks = sum(int(q["marks"]) for q in questions)
    for q in questions:
        answer = selected.get(str(q["id"])) or selected.get(q["id"]) or ""
        is_correct = bool(answer and is_correct_response(q, answer))
        if not answer:
            unanswered += 1
        elif is_correct:
            correct += 1
            obtained += int(q["marks"])
        else:
            wrong += 1
        execute(
            "INSERT INTO assessment_answers (attempt_id, assessment_question_id, selected_answer, is_correct) VALUES (?, ?, ?, ?)",
            (attempt_id, q["id"], answer, 1 if is_correct else 0),
        )
    percentage = round((obtained / total_marks * 100) if total_marks else 0, 2)
    execute(
        """UPDATE assessment_attempts SET correct_answers=?, wrong_answers=?, unanswered=?, percentage=?,
           obtained_marks=?, total_marks=?, time_taken=? WHERE id=?""",
        (correct, wrong, unanswered, percentage, obtained, total_marks, int(time_taken or 0), attempt_id),
    )
    return attempt_id
