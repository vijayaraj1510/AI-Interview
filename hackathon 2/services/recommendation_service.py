from utils.database import query, execute
from services.ai_service import generate_recommendation


def refresh_recommendations(user_id):
    latest = query("SELECT assessment_type, topic, percentage FROM assessment_attempts WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (user_id,))
    weak = [dict(row) for row in latest if row["percentage"] < 75]
    if weak:
        rec = generate_recommendation({"weak_attempts": weak})
        execute(
            "INSERT INTO recommendations (user_id, title, description, priority) VALUES (?, ?, ?, ?)",
            (user_id, rec["title"], rec["description"], rec.get("priority", "medium")),
        )
    elif not query("SELECT id FROM recommendations WHERE user_id=? LIMIT 1", (user_id,), one=True):
        execute(
            "INSERT INTO recommendations (user_id, title, description, priority) VALUES (?, ?, ?, ?)",
            (user_id, "Complete your first assessment", "Take an aptitude or technical test to unlock personalized recommendations.", "medium"),
        )
