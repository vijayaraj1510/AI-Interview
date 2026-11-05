import sqlite3
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.database import migrate_question_types

DB = ROOT / "database" / "interviewai.db"
SCHEMA = ROOT / "database" / "schema.sql"


def ensure_schema(cur):
    cur.executescript(SCHEMA.read_text(encoding="utf-8"))


def upsert_user(cur, name, email, password, role, college="", degree="", department=""):
    password_hash = generate_password_hash(password)
    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        cur.execute(
            """UPDATE users
               SET name=?, password_hash=?, role=?, is_active=1
               WHERE id=?""",
            (name, password_hash, role, user_id),
        )
    else:
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, 1)",
            (name, email, password_hash, role),
        )
        user_id = cur.lastrowid

    cur.execute("SELECT id FROM profiles WHERE user_id=?", (user_id,))
    if cur.fetchone():
        cur.execute(
            """UPDATE profiles
               SET college=COALESCE(NULLIF(?, ''), college),
                   degree=COALESCE(NULLIF(?, ''), degree),
                   department=COALESCE(NULLIF(?, ''), department),
                   updated_at=CURRENT_TIMESTAMP
               WHERE user_id=?""",
            (college, degree, department, user_id),
        )
    else:
        cur.execute(
            """INSERT INTO profiles
               (user_id, college, degree, department, skills, bio)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                college,
                degree,
                department,
                "Python, SQL, Communication",
                "InterviewAI demo profile",
            ),
        )
    return user_id


def upsert_question(cur, qtype, category, topic, difficulty, question, a, b, c, d, correct, explanation):
    cur.execute("SELECT id FROM questions WHERE question=?", (question,))
    if cur.fetchone():
        return
    values = (
        qtype,
        category,
        topic,
        difficulty,
        question,
        a,
        b,
        c,
        d,
        correct,
        explanation,
        1,
        60,
        "published",
        1,
    )
    cur.execute(
        """INSERT INTO questions
           (type, category, topic, difficulty, question, option_a, option_b,
            option_c, option_d, correct_answer, explanation, marks, time_limit,
            status, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        values,
    )


def seed_questions(cur):
    aptitude = [
        ("Quantitative Aptitude", "Percentage", "easy", "What is 25% of 240?", "40", "50", "60", "80", "C", "25% means one fourth. 240 / 4 = 60."),
        ("Quantitative Aptitude", "Profit and Loss", "medium", "An item bought for 500 is sold for 650. What is the profit percentage?", "20%", "25%", "30%", "35%", "C", "Profit is 150. 150/500 x 100 = 30%."),
        ("Quantitative Aptitude", "Ratio", "easy", "If A:B = 2:3 and B:C = 6:7, what is A:C?", "4:7", "2:7", "3:7", "7:4", "A", "Make B common: A:B = 4:6 and B:C = 6:7."),
        ("Quantitative Aptitude", "Averages", "easy", "Average of 10, 20, 30, 40 is?", "20", "25", "30", "35", "B", "Sum is 100 and count is 4, so average is 25."),
        ("Quantitative Aptitude", "Number System", "medium", "Which number is divisible by 9?", "1234", "2345", "3456", "4567", "C", "Digits of 3456 sum to 18, divisible by 9."),
        ("Logical Reasoning", "Series", "medium", "Find the next term: 2, 6, 12, 20, 30, ?", "36", "40", "42", "44", "C", "Differences are 4, 6, 8, 10, so next difference is 12."),
        ("Logical Reasoning", "Coding-Decoding", "medium", "If CAT is coded as DBU, DOG is coded as?", "EPH", "EPI", "FQH", "CNG", "A", "Each letter moves one step forward."),
        ("Logical Reasoning", "Blood Relations", "easy", "A is B's brother and C is B's mother. How is C related to A?", "Sister", "Mother", "Aunt", "Daughter", "B", "C is mother of B and A is B's sibling."),
        ("Logical Reasoning", "Direction Sense", "easy", "A person walks north, turns right, then right again. Which direction is he facing?", "North", "South", "East", "West", "B", "North -> East -> South."),
        ("Verbal Ability", "Synonyms", "easy", "Choose the closest synonym of 'Rapid'.", "Slow", "Quick", "Weak", "Late", "B", "Rapid means quick or fast."),
    ]
    technical = [
        ("Python", "Python", "medium", "What is the difference between a list and a tuple in Python?", "Lists are immutable, tuples are mutable", "Lists are mutable, tuples are immutable", "Both are immutable", "Tuples cannot store mixed data", "B", "Lists can be changed after creation; tuples cannot."),
        ("Python", "OOP", "easy", "Which keyword defines a class in Python?", "def", "class", "object", "struct", "B", "Python uses the class keyword."),
        ("Programming Fundamentals", "Functions", "easy", "What does len([1,2,3]) return?", "2", "3", "4", "Error", "B", "The list has three elements."),
        ("Database", "SQL", "easy", "Which SQL command retrieves rows?", "GET", "SELECT", "PULL", "OPEN", "B", "SELECT retrieves data from tables."),
        ("Database", "DBMS", "medium", "What does ACID stand for in databases?", "Atomicity Consistency Isolation Durability", "Access Control Internal Data", "Auto Commit Indexed Data", "Atomic Class Interface Design", "A", "ACID defines reliable transaction properties."),
        ("DSA", "DSA", "easy", "Which data structure uses FIFO?", "Stack", "Queue", "Tree", "Graph", "B", "Queue follows first in, first out."),
        ("DSA", "Algorithms", "medium", "Binary search requires data to be:", "Random", "Sorted", "Encrypted", "Duplicated", "B", "Binary search repeatedly halves a sorted collection."),
        ("Python", "OOP", "medium", "What is polymorphism in object-oriented programming?", "One method name with different behavior", "Only one object in a program", "Deleting inherited methods", "A database backup method", "A", "Polymorphism lets related objects respond through the same interface in different ways."),
        ("Programming Fundamentals", "Recursion", "medium", "What is a base case in a recursive function?", "The first function call", "The condition that stops recursive calls", "A global variable", "A syntax error", "B", "A base case prevents recursion from continuing indefinitely."),
        ("AI/ML", "AI/ML", "medium", "Which task is supervised learning?", "Clustering unlabeled data", "Predicting labels from labeled examples", "Compressing files", "Sorting arrays", "B", "Supervised learning trains on labeled data."),
    ]
    hr = [
        ("General HR", "Introduction", "easy", "Tell me about yourself and explain why you are interested in this role.", "Give a concise professional introduction", "Discuss only personal hobbies", "Read your resume word for word", "Avoid mentioning the role", "A", "Look for a clear introduction, relevant skills, and a connection to the role."),
        ("Behavioral", "Teamwork", "medium", "Describe a time you worked with a team to solve a difficult problem.", "Use a specific example and your contribution", "Say teamwork is always easy", "Describe a problem with no outcome", "Avoid explaining your role", "A", "Evaluate collaboration, ownership, communication, and the measurable result."),
        ("Situational", "Problem Solving", "medium", "How would you handle a deadline when a key task is delayed?", "Prioritize, communicate risk, and propose a recovery plan", "Hide the delay", "Wait without informing anyone", "Blame a colleague", "A", "Strong answers show planning, transparent communication, and accountability."),
        ("Career", "Motivation", "easy", "Where do you see yourself in the next three years?", "Connect growth goals with learning and contribution", "Promise to leave immediately", "Avoid discussing growth", "Give an unrelated answer", "A", "Assess realistic goals, commitment to learning, and alignment with the role."),
        ("Projects", "Project Experience", "medium", "Explain a project you are proud of, including the problem, your role, and the outcome.", "Describe problem, actions, tools, and result", "List technologies only", "Claim all work was done by others", "Skip the outcome", "A", "Look for ownership, technical clarity, challenges, and impact."),
    ]
    spoken = [
        ("Spoken English", "Introduction", "easy", "Please introduce yourself in one minute using clear and complete sentences.", "Clear structure and confident delivery", "Single-word answers", "No introduction", "Unrelated content", "A", "Evaluate fluency, grammar, pronunciation, confidence, and relevant detail."),
        ("Spoken English", "Daily Communication", "easy", "Describe your typical day and the activities you enjoy most.", "Use a logical sequence and details", "Repeat one word", "Avoid complete sentences", "Change to an unrelated topic", "A", "Listen for sentence structure, vocabulary, and a natural pace."),
        ("Spoken English", "Opinion", "medium", "Do you think remote work improves productivity? Explain your opinion with one example.", "State a view and support it with an example", "Answer only yes or no", "Avoid giving reasons", "Use unrelated facts", "A", "Evaluate clarity of opinion, supporting reasons, vocabulary, and coherence."),
        ("Spoken English", "Problem Solving", "medium", "Describe how you would politely ask a teammate for help when you are blocked.", "Use respectful and specific language", "Demand help without context", "Remain silent", "Blame the teammate", "A", "Look for professional tone, clarity, and practical communication."),
        ("Spoken English", "Career", "medium", "Describe a skill you want to improve and how you plan to improve it.", "Give a goal and practical learning plan", "Say skills cannot improve", "Provide no plan", "Discuss an unrelated topic", "A", "Evaluate future tense, organization, vocabulary, and confidence."),
    ]
    for qtype, rows in [("aptitude", aptitude), ("technical", technical), ("hr", hr), ("spoken", spoken)]:
        for row in rows:
            upsert_question(cur, qtype, *row)


def seed_settings(cur):
    defaults = {
        "default_question_count": "10",
        "default_test_time": "10",
        "random_questions": "on",
        "negative_marking": "off",
    }
    for key, value in defaults.items():
        cur.execute(
            """INSERT INTO settings (setting_key, setting_value)
               VALUES (?, ?)
               ON CONFLICT(setting_key) DO NOTHING""",
            (key, value),
        )


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        ensure_schema(cur)
        migrate_question_types(con)
        upsert_user(cur, "Admin", "admin@interviewai.com", "Admin@123", "admin")
        upsert_user(
            cur,
            "Demo Student",
            "demo@interviewai.com",
            "Demo@123",
            "student",
            "Neural Nexus College",
            "B.Tech",
            "CSE",
        )
        seed_questions(cur)
        seed_settings(cur)
        con.commit()
    finally:
        con.close()
    print(f"Database initialized at {DB}")


if __name__ == "__main__":
    main()
