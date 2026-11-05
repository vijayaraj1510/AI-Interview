from datetime import date

from utils.database import query


def student_stats(user_id):
    attempts = query("SELECT * FROM assessment_attempts WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    spoken = query("SELECT * FROM spoken_attempts WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    hrs = query("SELECT * FROM hr_interviews WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    scores = [row["percentage"] for row in attempts] + [row["score"] for row in spoken] + [row["overall_score"] or 0 for row in hrs]
    by_type = {name: 0 for name in ("aptitude", "technical", "spoken", "hr")}
    for name in ("aptitude", "technical"):
        values = [row["percentage"] for row in attempts if row["assessment_type"] == name]
        by_type[name] = round(sum(values) / len(values), 1) if values else 0
    for name, rows, field in (("spoken", spoken, "score"), ("hr", hrs, "overall_score")):
        values = [(row[field] or 0) for row in rows]
        by_type[name] = round(sum(values) / len(values), 1) if values else 0
    return {
        "attempts": attempts,
        "spoken": spoken,
        "hrs": hrs,
        "average": round(sum(scores) / len(scores), 1) if scores else 0,
        "highest": round(max(scores), 1) if scores else 0,
        "total": len(scores),
        "by_type": by_type,
    }


def performance_data(user_id):
    stats = student_stats(user_id)
    trend_rows = list(reversed(stats["attempts"][:6]))
    return {
        "total_assessments": stats["total"],
        "average_score": stats["average"],
        "highest_score": stats["highest"],
        "aptitude_score": stats["by_type"]["aptitude"],
        "technical_score": stats["by_type"]["technical"],
        "spoken_score": stats["by_type"]["spoken"],
        "hr_score": stats["by_type"]["hr"],
        "trend": [{"label": row["created_at"][:10], "score": row["percentage"] or 0} for row in trend_rows],
        "module_scores": [
            {"label": "Aptitude", "score": stats["by_type"]["aptitude"]},
            {"label": "Technical", "score": stats["by_type"]["technical"]},
            {"label": "Spoken", "score": stats["by_type"]["spoken"]},
            {"label": "HR", "score": stats["by_type"]["hr"]},
        ],
    }


def admin_stats():
    def one(sql, params=()):
        row = query(sql, params, one=True)
        return row[0] if row else 0

    return {
        "students": one("SELECT COUNT(*) FROM users WHERE role='student'"),
        "questions": one("SELECT COUNT(*) FROM questions WHERE is_active=1"),
        "published": one("SELECT COUNT(*) FROM questions WHERE status='published' AND is_active=1"),
        "draft": one("SELECT COUNT(*) FROM questions WHERE status='draft' AND is_active=1"),
        "assessments": one("SELECT COUNT(*) FROM assessment_attempts"),
        "avg_score": round(one("SELECT COALESCE(AVG(percentage), 0) FROM assessment_attempts"), 1),
    }


def _valid_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _completed_performance_records(filters):
    assessment_type = filters.get("assessment_type", "all")
    student_id = filters.get("student_id")
    department = filters.get("department")
    start_date = _valid_date(filters.get("start_date"))
    end_date = _valid_date(filters.get("end_date"))
    records = []

    if assessment_type in ("all", "aptitude", "technical"):
        where = ["u.role='student'", "a.assessment_type IN ('aptitude', 'technical')", "a.total_questions > 0", "(SELECT COUNT(*) FROM assessment_answers answer WHERE answer.attempt_id=a.id) >= a.total_questions"]
        params = []
        if assessment_type in ("aptitude", "technical"):
            where.append("a.assessment_type=?")
            params.append(assessment_type)
        if student_id:
            where.append("u.id=?")
            params.append(student_id)
        if department:
            where.append("COALESCE(p.department, '')=?")
            params.append(department)
        if start_date:
            where.append("date(a.created_at)>=?")
            params.append(start_date)
        if end_date:
            where.append("date(a.created_at)<=?")
            params.append(end_date)
        rows = query(
            f"""SELECT u.id user_id, u.name, u.email, COALESCE(p.department, '') department,
                       a.assessment_type module, COALESCE(a.percentage, 0) score, a.created_at
                FROM assessment_attempts a
                JOIN users u ON u.id=a.user_id
                LEFT JOIN profiles p ON p.user_id=u.id
                WHERE {' AND '.join(where)}""",
            params,
        )
        records.extend(dict(row) for row in rows)

    if assessment_type in ("all", "spoken"):
        where = ["u.role='student'", "TRIM(COALESCE(s.transcript, '')) <> ''"]
        params = []
        if student_id:
            where.append("u.id=?")
            params.append(student_id)
        if department:
            where.append("COALESCE(p.department, '')=?")
            params.append(department)
        if start_date:
            where.append("date(s.created_at)>=?")
            params.append(start_date)
        if end_date:
            where.append("date(s.created_at)<=?")
            params.append(end_date)
        rows = query(
            f"""SELECT u.id user_id, u.name, u.email, COALESCE(p.department, '') department,
                       'spoken' module, COALESCE(s.score, 0) score, s.created_at
                FROM spoken_attempts s
                JOIN users u ON u.id=s.user_id
                LEFT JOIN profiles p ON p.user_id=u.id
                WHERE {' AND '.join(where)}""",
            params,
        )
        records.extend(dict(row) for row in rows)

    if assessment_type in ("all", "hr"):
        where = ["u.role='student'", "h.total_questions > 0", "h.completed_questions >= h.total_questions"]
        params = []
        if student_id:
            where.append("u.id=?")
            params.append(student_id)
        if department:
            where.append("COALESCE(p.department, '')=?")
            params.append(department)
        if start_date:
            where.append("date(h.created_at)>=?")
            params.append(start_date)
        if end_date:
            where.append("date(h.created_at)<=?")
            params.append(end_date)
        rows = query(
            f"""SELECT u.id user_id, u.name, u.email, COALESCE(p.department, '') department,
                       'hr' module, COALESCE(h.overall_score, 0) score, h.created_at
                FROM hr_interviews h
                JOIN users u ON u.id=h.user_id
                LEFT JOIN profiles p ON p.user_id=u.id
                WHERE {' AND '.join(where)}""",
            params,
        )
        records.extend(dict(row) for row in rows)
    return records


def admin_performance_data(filters):
    records = _completed_performance_records(filters)
    records.sort(key=lambda row: row["created_at"])
    students = query("SELECT id, name FROM users WHERE role='student' AND is_active=1 ORDER BY name")
    departments = query("SELECT DISTINCT department FROM profiles WHERE TRIM(COALESCE(department, '')) <> '' ORDER BY department")
    modules = ("aptitude", "technical", "spoken", "hr")
    scores = [float(row["score"] or 0) for row in records]
    by_module = {module: [] for module in modules}
    by_student = {}
    by_day = {}
    for record in records:
        score = float(record["score"] or 0)
        by_module[record["module"]].append(score)
        student = by_student.setdefault(record["user_id"], {
            "name": record["name"], "email": record["email"], "department": record["department"], "scores": [], "last_assessment": record["created_at"],
        })
        student["scores"].append(score)
        student["last_assessment"] = max(student["last_assessment"], record["created_at"])
        day = record["created_at"][:10]
        by_day.setdefault(day, []).append(score)
    student_rows = [
        {
            "name": value["name"], "email": value["email"], "department": value["department"] or "-",
            "total": len(value["scores"]), "average": round(sum(value["scores"]) / len(value["scores"]), 1),
            "highest": round(max(value["scores"]), 1), "last_assessment": value["last_assessment"],
        }
        for value in by_student.values()
    ]
    search = (filters.get("search") or "").strip().lower()
    if search:
        student_rows = [row for row in student_rows if search in row["name"].lower() or search in row["email"].lower()]
    sort = filters.get("sort", "average")
    reverse = filters.get("direction", "desc") != "asc"
    if sort not in {"name", "total", "average", "highest", "last_assessment"}:
        sort = "average"
    student_rows.sort(key=lambda row: row[sort], reverse=reverse)
    try:
        page = max(int(filters.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    page_size = 10
    total_pages = max((len(student_rows) + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    return {
        "summary": {
            "students": len(by_student), "assessments": len(records),
            "average": round(sum(scores) / len(scores), 1) if scores else 0,
            "highest": round(max(scores), 1) if scores else 0,
        },
        "trend": [{"label": day, "score": round(sum(values) / len(values), 1)} for day, values in sorted(by_day.items())[-14:]],
        "module_scores": [{"label": {"aptitude": "Aptitude", "technical": "Technical", "spoken": "Spoken English", "hr": "HR Interview"}[module], "score": round(sum(values) / len(values), 1) if values else 0} for module, values in by_module.items()],
        "top_students": [{"label": row["name"], "score": row["average"]} for row in sorted(student_rows, key=lambda row: row["average"], reverse=True)[:8]],
        "students": student_rows[start:start + page_size],
        "filters": {"students": students, "departments": departments, "page": page, "total_pages": total_pages, "total_rows": len(student_rows)},
        "has_data": bool(records),
    }
