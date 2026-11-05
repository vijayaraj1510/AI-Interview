from utils.database import query, execute


def random_questions(qtype, category, topic, difficulty, limit):
    return query(
        """SELECT * FROM questions
           WHERE type=? AND category LIKE ? AND topic LIKE ? AND difficulty LIKE ?
           AND status='published' AND is_active=1
           ORDER BY RANDOM() LIMIT ?""",
        (qtype, category or "%", topic or "%", difficulty or "%", limit),
    )


def available_question_count(qtype, category="%", topic="%", difficulty="%"):
    row = query(
        """SELECT COUNT(*) AS total FROM questions
           WHERE type=? AND category LIKE ? AND topic LIKE ? AND difficulty LIKE ?
           AND status='published' AND is_active=1""",
        (qtype, category or "%", topic or "%", difficulty or "%"),
        one=True,
    )
    return row["total"] if row else 0


def active_published_prompts(qtype, category=None):
    """Return prompt-bank rows that students may use in a newly started session."""
    params = [qtype]
    sql = """SELECT * FROM questions
             WHERE type=? AND status='published' AND is_active=1"""
    if category:
        sql += " AND category=?"
        params.append(category)
    return query(f"{sql} ORDER BY RANDOM()", params)


def snapshot_attempt(user_id, qtype, category, topic, difficulty, questions):
    total_marks = sum(int(q["marks"]) for q in questions)
    attempt_id = execute(
        """INSERT INTO assessment_attempts
           (user_id, assessment_type, category, topic, difficulty, total_questions, total_marks)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, qtype, category, topic, difficulty, len(questions), total_marks),
    )
    for index, q in enumerate(questions, start=1):
        execute(
            """INSERT INTO assessment_questions
               (attempt_id, question_id, question_text_snapshot, option_a_snapshot, option_b_snapshot,
                option_c_snapshot, option_d_snapshot, correct_answer_snapshot, explanation_snapshot, marks, question_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt_id, q["id"], q["question"], q["option_a"], q["option_b"], q["option_c"],
                q["option_d"], q["correct_answer"], q["explanation"], q["marks"], index,
            ),
        )
    return attempt_id
