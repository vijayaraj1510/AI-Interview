import csv
import io
import uuid
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, flash
from werkzeug.utils import secure_filename
from config import Config
from utils.database import close_db, execute, init_db, query
from utils.auth import hash_password, verify_password
from utils.decorators import admin_required, login_required, student_required
from utils.validators import clean_int, required_fields, valid_answer
from services.question_service import active_published_prompts, available_question_count, random_questions, snapshot_attempt
from services.assessment_service import get_attempt_with_questions, submit_attempt
from services.analytics_service import admin_performance_data, performance_data, student_stats, admin_stats
from services.recommendation_service import refresh_recommendations
from services.ai_service import evaluate_spoken_answer, evaluate_hr_answer

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_db)

with app.app_context():
    init_db()


def spoken_practice_state():
    index = session.get("spoken_question_index")
    total = session.get("spoken_total_questions")
    questions = session.get("spoken_questions")
    if not isinstance(index, int) or not isinstance(questions, list) or total != len(questions) or not 0 <= index < total:
        return None
    return {
        "index": index,
        "total": total,
        "answers": session.get("spoken_answers", []),
        "scores": session.get("spoken_scores", []),
        "attempt_ids": session.get("spoken_attempt_ids", []),
        "questions": questions,
    }


def clear_spoken_practice():
    for key in ("spoken_question_index", "spoken_total_questions", "spoken_answers", "spoken_scores", "spoken_attempt_ids", "spoken_questions"):
        session.pop(key, None)


@app.context_processor
def inject_user():
    user = query("SELECT * FROM users WHERE id=?", (session.get("user_id"),), one=True) if session.get("user_id") else None
    return {"current_user": user}


def login_user(user):
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["name"] = user["name"]


def options_for(qtype):
    rows = query("SELECT DISTINCT category, topic FROM questions WHERE type=? AND status='published' AND is_active=1 ORDER BY category, topic", (qtype,))
    categories = sorted({r["category"] for r in rows})
    return categories, rows


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/service-worker.js")
def service_worker():
    response = app.send_static_file("service-worker.js")
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.form
        missing = required_fields(data, ["name", "email", "password", "confirm_password", "college", "degree", "department"])
        if missing or data["password"] != data["confirm_password"]:
            flash("Please complete all fields and confirm your password correctly.", "danger")
            return render_template("auth/register.html")
        try:
            user_id = execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'student')",
                (data["name"], data["email"].lower(), hash_password(data["password"])),
            )
            execute(
                "INSERT INTO profiles (user_id, college, degree, department) VALUES (?, ?, ?, ?)",
                (user_id, data["college"], data["degree"], data["department"]),
            )
            user = query("SELECT * FROM users WHERE id=?", (user_id,), one=True)
            login_user(user)
            flash("Welcome to InterviewAI.", "success")
            return redirect(url_for("profile_setup"))
        except Exception:
            flash("That email is already registered.", "danger")
    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = query("SELECT * FROM users WHERE email=? AND is_active=1", (request.form["email"].lower(),), one=True)
        if user and verify_password(user["password_hash"], request.form["password"]):
            login_user(user)
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))


@app.route("/dashboard")
@student_required
def dashboard():
    stats = student_stats(session["user_id"])
    refresh_recommendations(session["user_id"])
    recs = query("SELECT * FROM recommendations WHERE user_id=? AND is_completed=0 ORDER BY created_at DESC LIMIT 4", (session["user_id"],))
    recent = query("SELECT * FROM assessment_attempts WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (session["user_id"],))
    return render_template("dashboard/dashboard.html", stats=stats, recs=recs, recent=recent)


@app.route("/profile/setup", methods=["GET", "POST"])
@student_required
def profile_setup():
    return profile(editing=True)


@app.route("/profile", methods=["GET", "POST"])
@student_required
def profile(editing=False):
    if request.method == "POST":
        data = request.form
        execute(
            """UPDATE profiles SET phone=?, college=?, degree=?, department=?, graduation_year=?,
               skills=?, bio=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?""",
            (data.get("phone"), data.get("college"), data.get("degree"), data.get("department"), data.get("graduation_year"), data.get("skills"), data.get("bio"), session["user_id"]),
        )
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    profile_row = query("SELECT * FROM profiles WHERE user_id=?", (session["user_id"],), one=True)
    return render_template("profile/profile.html", profile=profile_row, editing=editing)


@app.route("/spoken")
@student_required
def spoken():
    practice = spoken_practice_state()
    return render_template("spoken/index.html", practice=practice, questions=practice["questions"] if practice else [])


@app.route("/spoken/start", methods=["POST"])
@student_required
def spoken_start():
    clear_spoken_practice()
    session.pop("spoken_result_attempt_ids", None)
    questions = [row["question"] for row in active_published_prompts("spoken")]
    if not questions:
        return jsonify({"success": False, "message": "No active, published spoken English questions are available yet."}), 409
    session["spoken_question_index"] = 0
    session["spoken_total_questions"] = len(questions)
    session["spoken_questions"] = questions
    session["spoken_answers"] = []
    session["spoken_scores"] = []
    session["spoken_attempt_ids"] = []
    return jsonify({"success": True, "question": questions[0], "number": 1, "total": len(questions)})


@app.route("/spoken/question")
@student_required
def spoken_question():
    practice = spoken_practice_state()
    if not practice:
        return jsonify({"success": False, "message": "Start a new spoken English practice session to continue."}), 409
    return jsonify({
        "success": True,
        "question": practice["questions"][practice["index"]],
        "number": practice["index"] + 1,
        "total": practice["total"],
    })


@app.route("/spoken/answer", methods=["POST"])
@app.route("/spoken/evaluate", methods=["POST"])
@student_required
def spoken_evaluate():
    data = request.get_json() or request.form
    transcript = (data.get("transcript") or "").strip()
    practice = spoken_practice_state()
    if not practice:
        return jsonify({"success": False, "message": "Start a new spoken English practice session to submit an answer."}), 409
    question = practice["questions"][practice["index"]]
    result = evaluate_spoken_answer(question, transcript) if transcript else {
        "score": 0,
        "fluency": 0,
        "grammar": 0,
        "pronunciation": 0,
        "confidence": 0,
        "feedback": "This question was skipped. Practice a short response when you try again.",
        "strengths": [],
        "weaknesses": [],
        "suggestions": ["Try answering this question during your next practice session."],
    }
    attempt_id = execute(
        """INSERT INTO spoken_attempts
           (user_id, question, transcript, duration, score, fluency_score, grammar_score, pronunciation_score, confidence_score, feedback)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session["user_id"], question, transcript, clean_int(data.get("duration"), 0),
         result.get("score", 0), result.get("fluency", 0), result.get("grammar", 0), result.get("pronunciation", 0), result.get("confidence", 0), result.get("feedback", "")),
    )
    answers = practice["answers"] + [bool(transcript)]
    scores = practice["scores"] + [result.get("score", 0)]
    attempt_ids = practice["attempt_ids"] + [attempt_id]
    next_index = practice["index"] + 1
    session["spoken_answers"] = answers
    session["spoken_scores"] = scores
    session["spoken_attempt_ids"] = attempt_ids
    refresh_recommendations(session["user_id"])
    if next_index >= practice["total"]:
        clear_spoken_practice()
        session["spoken_result_attempt_ids"] = attempt_ids
        return jsonify({"success": True, **result, "done": True, "result_url": url_for("spoken_result")})
    session["spoken_question_index"] = next_index
    return jsonify({
        "success": True,
        **result,
        "done": False,
        "question": practice["questions"][next_index],
        "number": next_index + 1,
        "total": practice["total"],
    })


@app.route("/spoken/result")
@student_required
def spoken_result():
    attempt_ids = session.get("spoken_result_attempt_ids", [])
    if not attempt_ids or not all(isinstance(item, int) for item in attempt_ids):
        flash("Complete a spoken English practice session to view its result.", "warning")
        return redirect(url_for("spoken"))
    placeholders = ", ".join("?" for _ in attempt_ids)
    attempts = query(
        f"SELECT * FROM spoken_attempts WHERE user_id=? AND id IN ({placeholders}) ORDER BY id",
        [session["user_id"], *attempt_ids],
    )
    if len(attempts) != len(attempt_ids):
        session.pop("spoken_result_attempt_ids", None)
        flash("That spoken English result is no longer available.", "warning")
        return redirect(url_for("spoken"))
    total = len(attempts)
    answered = sum(bool(row["transcript"].strip()) for row in attempts)
    average = lambda field: round(sum((row[field] or 0) for row in attempts) / total, 1) if total else 0
    result = {
        "total": total,
        "answered": answered,
        "skipped": total - answered,
        "score": average("score"),
        "fluency": average("fluency_score"),
        "grammar": average("grammar_score"),
        "pronunciation": average("pronunciation_score"),
        "confidence": average("confidence_score"),
    }
    return render_template("spoken/result.html", attempts=attempts, result=result)


def assessment_home(qtype):
    categories, topics = options_for(qtype)
    return render_template(f"{qtype}/index.html", qtype=qtype, categories=categories, topics=topics)


@app.route("/aptitude")
@app.route("/aptitude/setup")
@student_required
def aptitude():
    return assessment_home("aptitude")


@app.route("/technical")
@app.route("/technical/setup")
@student_required
def technical():
    return assessment_home("technical")


@app.route("/<qtype>/start", methods=["POST"])
@student_required
def assessment_start(qtype):
    if qtype not in {"aptitude", "technical"}:
        return redirect(url_for("dashboard"))
    count = clean_int(request.form.get("count"), 10, 1, 50)
    category = request.form.get("category") or "%"
    topic = request.form.get("topic") or "%"
    difficulty = request.form.get("difficulty") or "%"
    available = available_question_count(qtype, category, topic, difficulty)
    if not available:
        flash("No active, published questions match this selection. Choose All Categories or adjust the filters.", "warning")
        return redirect(url_for(qtype))
    question_count = min(count, available)
    questions = random_questions(qtype, category, topic, difficulty, question_count)
    if question_count < count:
        flash(f"Only {question_count} active, published question(s) match this selection. Your assessment uses those available questions.", "info")
    attempt_id = snapshot_attempt(
        session["user_id"], qtype,
        None if category == "%" else category,
        None if topic == "%" else topic,
        None if difficulty == "%" else difficulty,
        questions,
    )
    return redirect(url_for("assessment_test", qtype=qtype, attempt_id=attempt_id, minutes=clean_int(request.form.get("time_limit"), 10, 1, 180)))


@app.route("/<qtype>/test/<int:attempt_id>")
@student_required
def assessment_test(qtype, attempt_id):
    attempt, questions, answers = get_attempt_with_questions(attempt_id, session["user_id"])
    if not attempt:
        flash("Assessment not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template(f"{qtype}/test.html", qtype=qtype, attempt=attempt, questions=questions, answers=answers, minutes=request.args.get("minutes", 10))


@app.route("/<qtype>/submit", methods=["POST"])
@student_required
def assessment_submit(qtype):
    attempt_id = clean_int(request.form.get("attempt_id"), 0)
    selected = {k.replace("answer_", ""): v for k, v in request.form.items() if k.startswith("answer_")}
    selected.update({
        k.replace("typed_answer_", ""): v.strip()
        for k, v in request.form.items()
        if k.startswith("typed_answer_") and v.strip()
    })
    submit_attempt(attempt_id, selected, request.form.get("time_taken", 0))
    refresh_recommendations(session["user_id"])
    return redirect(url_for("assessment_result", qtype=qtype, id=attempt_id))


@app.route("/<qtype>/result/<int:id>")
@student_required
def assessment_result(qtype, id):
    attempt, questions, answers = get_attempt_with_questions(id, session["user_id"])
    return render_template(f"{qtype}/result.html", qtype=qtype, attempt=attempt, questions=questions, answers=answers)


@app.route("/performance")
@student_required
def performance():
    return render_template("performance/performance.html", stats=student_stats(session["user_id"]))


@app.route("/api/performance")
@student_required
def performance_api():
    return jsonify(performance_data(session["user_id"]))


@app.route("/history")
@student_required
def history():
    return render_template("history/history.html", stats=student_stats(session["user_id"]))


@app.route("/hr-interview")
@student_required
def hr_interview():
    return render_template("hr/index.html")


@app.route("/hr-interview/start", methods=["POST"])
@student_required
def hr_start():
    category = request.form.get("category", "General HR")
    prompts = active_published_prompts("hr", category)
    if not prompts:
        prompts = active_published_prompts("hr")
    if not prompts:
        flash("No active, published HR questions are available yet.", "warning")
        return redirect(url_for("hr_interview"))

    total_questions = min(clean_int(request.form.get("total_questions"), 5, 1, 10), len(prompts))
    interview_id = execute(
        "INSERT INTO hr_interviews (user_id, session_id, total_questions) VALUES (?, ?, ?)",
        (session["user_id"], str(uuid.uuid4()), total_questions),
    )
    categories = session.get("hr_categories", {})
    categories[str(interview_id)] = category
    session["hr_categories"] = categories
    question_sets = session.get("hr_question_sets", {})
    question_sets[str(interview_id)] = [prompt["question"] for prompt in prompts[:total_questions]]
    session["hr_question_sets"] = question_sets
    return redirect(url_for("hr_session", interview_id=interview_id))


@app.route("/hr-interview/session/<int:interview_id>")
@student_required
def hr_session(interview_id):
    interview = query("SELECT * FROM hr_interviews WHERE id=? AND user_id=?", (interview_id, session["user_id"]), one=True)
    if not interview:
        flash("Interview session not found.", "danger")
        return redirect(url_for("hr_interview"))
    return render_template("hr/interview.html", interview=interview)


@app.route("/hr-interview/question", methods=["POST"])
@student_required
def hr_question():
    data = request.get_json() or {}
    interview_id = clean_int(data.get("interview_id"), 0)
    interview = query("SELECT * FROM hr_interviews WHERE id=? AND user_id=?", (interview_id, session["user_id"]), one=True)
    if not interview:
        return jsonify({"success": False, "message": "Interview session not found."}), 404
    current_questions = session.get("hr_current_questions", {})
    current_question = current_questions.get(str(interview_id))
    if current_question:
        return jsonify({"success": True, "question": current_question, "number": interview["completed_questions"] + 1})
    question_set = session.get("hr_question_sets", {}).get(str(interview_id), [])
    current_question = question_set[interview["completed_questions"]] if interview["completed_questions"] < len(question_set) else None
    if not current_question:
        return jsonify({"success": False, "message": "No question is available for this interview session."}), 409
    current_questions[str(interview_id)] = current_question
    session["hr_current_questions"] = current_questions
    return jsonify({"success": True, "question": current_question, "number": interview["completed_questions"] + 1})


@app.route("/hr-interview/answer", methods=["POST"])
@student_required
def hr_answer():
    data = request.get_json() or {}
    interview_id = clean_int(data.get("interview_id"), 0)
    interview = query("SELECT * FROM hr_interviews WHERE id=? AND user_id=?", (interview_id, session["user_id"]), one=True)
    current_question = session.get("hr_current_questions", {}).get(str(interview_id))
    answer = (data.get("answer") or "").strip()
    if not interview or not current_question:
        return jsonify({"success": False, "message": "This interview question is no longer available. Reload the session."}), 400
    if not answer:
        return jsonify({"success": False, "message": "Please provide an answer before submitting."}), 400
    result = evaluate_hr_answer(current_question, answer)
    execute(
        "INSERT INTO hr_answers (interview_id, question, answer, score, strengths, weaknesses, feedback) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (interview_id, current_question, answer, result.get("score", 0), ", ".join(result.get("strengths", [])), ", ".join(result.get("weaknesses", [])), result.get("feedback", "")),
    )
    answers = query("SELECT score FROM hr_answers WHERE interview_id=?", (interview_id,))
    avg = round(sum([a["score"] for a in answers]) / len(answers)) if answers else 0
    execute("UPDATE hr_interviews SET completed_questions=?, overall_score=?, feedback=? WHERE id=?", (len(answers), avg, result.get("feedback", ""), interview_id))
    current_questions = session.get("hr_current_questions", {})
    current_questions.pop(str(interview_id), None)
    session["hr_current_questions"] = current_questions
    refresh_recommendations(session["user_id"])
    return jsonify({"success": True, **result, "done": len(answers) >= interview["total_questions"], "result_url": url_for("hr_result", id=interview_id)})


@app.route("/hr-interview/result/<int:id>")
@student_required
def hr_result(id):
    interview = query("SELECT * FROM hr_interviews WHERE id=? AND user_id=?", (id, session["user_id"]), one=True)
    answers = query("SELECT * FROM hr_answers WHERE interview_id=?", (id,))
    return render_template("hr/result.html", interview=interview, answers=answers)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = query("SELECT * FROM users WHERE email=? AND role='admin' AND is_active=1", (request.form["email"].lower(),), one=True)
        if user and verify_password(user["password_hash"], request.form["password"]):
            login_user(user)
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    return logout()


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html", stats=admin_stats())


def question_filters(base_type=None):
    where, params = [], []
    if base_type:
        where.append("type=?")
        params.append(base_type)
    for field in ["type", "category", "topic", "difficulty", "status"]:
        value = request.args.get(field)
        if value and not (base_type and field == "type"):
            where.append(f"{field}=?")
            params.append(value)
    availability = request.args.get("availability")
    if availability in {"active", "inactive"}:
        where.append("is_active=?")
        params.append(1 if availability == "active" else 0)
    search = request.args.get("search")
    if search:
        where.append("question LIKE ?")
        params.append(f"%{search}%")
    return " AND ".join(where) if where else "1=1", params


@app.route("/admin/questions")
@app.route("/admin/questions/aptitude")
@app.route("/admin/questions/technical")
@admin_required
def admin_questions():
    base_type = "aptitude" if request.path.endswith("aptitude") else "technical" if request.path.endswith("technical") else None
    where, params = question_filters(base_type)
    questions = query(f"SELECT * FROM questions WHERE {where} ORDER BY created_at DESC", params)
    return render_template("admin/questions.html", questions=questions, base_type=base_type)


def save_question(question_id=None):
    data = request.form
    missing = required_fields(data, ["type", "category", "topic", "difficulty", "question", "option_a", "option_b", "option_c", "option_d", "correct_answer"])
    if missing or data.get("type") not in {"aptitude", "technical", "hr", "spoken"} or not valid_answer(data.get("correct_answer")):
        flash("Complete all required fields and choose A, B, C, or D.", "danger")
        return False
    status = "published" if request.form.get("action") == "publish" or data.get("status") == "published" else "draft"
    params = (data["type"], data["category"], data["topic"], data["difficulty"], data["question"], data["option_a"], data["option_b"], data["option_c"], data["option_d"], data["correct_answer"].upper(), data.get("explanation", ""), clean_int(data.get("marks"), 1, 1), clean_int(data.get("time_limit"), 60, 10), status)
    try:
        if question_id:
            execute(
                """UPDATE questions SET type=?, category=?, topic=?, difficulty=?, question=?, option_a=?, option_b=?,
                   option_c=?, option_d=?, correct_answer=?, explanation=?, marks=?, time_limit=?, status=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (*params, question_id),
            )
        else:
            execute(
                """INSERT INTO questions (type, category, topic, difficulty, question, option_a, option_b, option_c, option_d,
                   correct_answer, explanation, marks, time_limit, status, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                params,
            )
        return True
    except Exception:
        flash("A question with this text already exists.", "danger")
        return False


@app.route("/admin/questions/create", methods=["GET", "POST"])
@admin_required
def admin_question_create():
    if request.method == "POST" and save_question():
        flash("Question saved.", "success")
        return redirect(url_for("admin_questions"))
    return render_template("admin/question_form.html", question=None)


@app.route("/admin/questions/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def admin_question_edit(id):
    question = query("SELECT * FROM questions WHERE id=?", (id,), one=True)
    if request.method == "POST" and save_question(id):
        flash("Question updated.", "success")
        return redirect(url_for("admin_questions"))
    return render_template("admin/question_form.html", question=question)


@app.route("/admin/questions/<int:id>/status", methods=["POST"])
@admin_required
def admin_question_status(id):
    availability = request.form.get("availability")
    question = query("SELECT id FROM questions WHERE id=?", (id,), one=True)
    if not question or availability not in {"active", "inactive"}:
        flash("Unable to update that question status.", "danger")
        return redirect(request.referrer or url_for("admin_questions"))
    execute("UPDATE questions SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (availability == "active", id))
    flash(f"Question marked {availability}.", "success")
    return redirect(request.referrer or url_for("admin_questions"))


@app.route("/admin/questions/<action>/<int:id>", methods=["POST"])
@admin_required
def admin_question_action(action, id):
    if not query("SELECT id FROM questions WHERE id=?", (id,), one=True):
        flash("Question not found.", "danger")
        return redirect(url_for("admin_questions"))
    if action == "publish":
        execute("UPDATE questions SET status='published', is_active=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    elif action == "unpublish":
        execute("UPDATE questions SET status='draft', updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    elif action == "delete":
        execute("UPDATE questions SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    else:
        flash("Unsupported question action.", "danger")
        return redirect(request.referrer or url_for("admin_questions"))
    flash("Question updated.", "success")
    return redirect(request.referrer or url_for("admin_questions"))


@app.route("/admin/questions/bulk", methods=["POST"])
@admin_required
def admin_questions_bulk():
    ids = [clean_int(qid, 0) for qid in request.form.getlist("ids")]
    ids = [qid for qid in ids if qid]
    action = request.form.get("bulk_action")
    if action not in {"publish", "unpublish", "delete"}:
        flash("Unsupported bulk action.", "danger")
        return redirect(url_for("admin_questions"))
    for qid in ids:
        if action == "publish":
            execute("UPDATE questions SET status='published', is_active=1 WHERE id=?", (qid,))
        elif action == "unpublish":
            execute("UPDATE questions SET status='draft' WHERE id=?", (qid,))
        elif action == "delete":
            execute("UPDATE questions SET is_active=0 WHERE id=?", (qid,))
    flash(f"Bulk {action} completed.", "success")
    return redirect(url_for("admin_questions"))


@app.route("/admin/questions/import", methods=["POST"])
@admin_required
def admin_import():
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith(".csv"):
        flash("Upload a valid CSV file.", "danger")
        return redirect(url_for("admin_questions"))
    stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
    imported = failed = 0
    for row in csv.DictReader(stream):
        try:
            execute(
                """INSERT INTO questions (type, category, topic, difficulty, question, option_a, option_b, option_c, option_d,
                   correct_answer, explanation, marks, time_limit, status, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1)""",
                (row["type"], row["category"], row["topic"], row["difficulty"], row["question"], row["option_a"], row["option_b"], row["option_c"], row["option_d"], row["correct_answer"].upper(), row.get("explanation", ""), clean_int(row.get("marks"), 1, 1), clean_int(row.get("time_limit"), 60, 10)),
            )
            imported += 1
        except Exception:
            failed += 1
    flash(f"Import complete. Imported: {imported}. Failed: {failed}.", "info")
    return redirect(url_for("admin_questions"))


@app.route("/admin/students")
@admin_required
def admin_students():
    students = query("""SELECT u.*, p.college, p.department, COUNT(a.id) assessment_count, COALESCE(AVG(a.percentage),0) avg_score
                        FROM users u LEFT JOIN profiles p ON p.user_id=u.id LEFT JOIN assessment_attempts a ON a.user_id=u.id
                        WHERE u.role='student' GROUP BY u.id ORDER BY u.created_at DESC""")
    return render_template("admin/students.html", students=students)


@app.route("/admin/students/<int:id>")
@admin_required
def admin_student_detail(id):
    student = query("SELECT u.*, p.* FROM users u LEFT JOIN profiles p ON p.user_id=u.id WHERE u.id=?", (id,), one=True)
    return render_template("admin/student_detail.html", student=student, stats=student_stats(id))


@app.route("/admin/results")
@admin_required
def admin_results():
    results = query("""SELECT a.*, u.name student FROM assessment_attempts a JOIN users u ON u.id=a.user_id
                       ORDER BY a.created_at DESC""")
    return render_template("admin/results.html", results=results)


@app.route("/admin/analytics")
@admin_required
def admin_analytics():
    filters = {
        "assessment_type": request.args.get("assessment_type", "all"),
        "student_id": clean_int(request.args.get("student_id"), 0) or None,
        "department": request.args.get("department", "").strip(),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
        "search": request.args.get("search", "").strip(),
        "sort": request.args.get("sort", "average"),
        "direction": request.args.get("direction", "desc"),
        "page": request.args.get("page", "1"),
    }
    return render_template("admin/analytics.html", analytics=admin_performance_data(filters), active_filters=filters)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        for key in ["default_question_count", "default_test_time", "random_questions", "negative_marking"]:
            execute("INSERT OR REPLACE INTO settings (id, setting_key, setting_value) VALUES ((SELECT id FROM settings WHERE setting_key=?), ?, ?)", (key, key, request.form.get(key, "off")))
        flash("Settings saved.", "success")
    settings = {r["setting_key"]: r["setting_value"] for r in query("SELECT * FROM settings")}
    return render_template("admin/settings.html", settings=settings)


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, title="Page Not Found", message="The page you requested does not exist."), 404


@app.errorhandler(500)
def server_error(error):
    print(error)
    return render_template("error.html", code=500, title="Something went wrong", message="Please try again in a moment."), 500


if __name__ == "__main__":
    Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)
    app.run(debug=True)
