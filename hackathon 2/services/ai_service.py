import json
import logging
import os

from openai import OpenAI


LOGGER = logging.getLogger(__name__)
HR_FALLBACK_QUESTIONS = [
    "Tell me about yourself and your career goals.",
    "Why do you want to join our company?",
    "What are your strengths and weaknesses?",
    "Tell me about a project you have worked on.",
    "Where do you see yourself in five years?",
    "How do you handle pressure and competing deadlines?",
    "Tell me about a difficult problem you solved.",
    "Why should we hire you?",
    "How do you contribute when working in a team?",
    "What professional skill would you most like to improve?",
]


def _client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        timeout=20.0,
    )


def _json_call(system_prompt, user_prompt, fallback):
    try:
        client = _client()
    except Exception as error:
        LOGGER.warning("AI client could not be created: %s", error)
        return fallback
    if client is None:
        return {
            **fallback,
            "unavailable": True,
            "message": "AI evaluation is currently unavailable. Please configure the AI API key.",
        }
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = (response.choices[0].message.content or "").strip()
        decoded = json.loads(content)
        return {**fallback, **decoded} if isinstance(decoded, dict) else fallback
    except Exception as error:
        LOGGER.warning("AI request failed: %s", error)
        return fallback


def evaluate_spoken_answer(question, transcript):
    fallback = {
        "score": 68,
        "fluency": 65,
        "grammar": 70,
        "confidence": 66,
        "pronunciation": 60,
        "strengths": ["Clear attempt and relevant response"],
        "weaknesses": ["Add more structure and concrete examples"],
        "feedback": "Your response was recorded successfully. Add a clear opening, details, and a confident closing.",
        "suggestions": ["Practice for 10 minutes daily", "Use short structured points"],
    }
    prompt = "Return JSON with score, fluency, grammar, confidence, pronunciation, strengths, weaknesses, feedback, and suggestions."
    return _json_call(prompt, f"Question: {question}\nTranscript: {transcript}", fallback)


def evaluate_hr_answer(question, answer):
    fallback = {
        "score": 70,
        "strengths": ["Relevant answer"],
        "weaknesses": ["Could include measurable impact"],
        "feedback": "Use the STAR structure and connect your answer to the role.",
        "suggestions": ["Add situation, task, action, and result"],
    }
    prompt = "Evaluate an HR interview answer. Return JSON with score, strengths, weaknesses, feedback, and suggestions."
    return _json_call(prompt, f"Question: {question}\nAnswer: {answer}", fallback)


def generate_hr_question(category="General HR", previous_questions=None):
    previous_questions = previous_questions or []
    fallback = next((question for question in HR_FALLBACK_QUESTIONS if question not in previous_questions), HR_FALLBACK_QUESTIONS[0])
    response = _json_call(
        "Generate one concise, professional HR interview question as JSON: {\"question\": \"...\"}.",
        f"Category: {category}\nAvoid these questions:\n" + "\n".join(previous_questions),
        {"question": fallback},
    )
    question = str(response.get("question", "")).strip()
    return question or fallback


def generate_recommendation(context):
    fallback = {
        "title": "Practice your weakest module today",
        "description": "Spend 20 minutes reviewing explanations from your latest assessment and retry related questions.",
        "priority": "high",
    }
    return _json_call("Return one personalized recommendation as JSON with title, description, priority.", json.dumps(context), fallback)
