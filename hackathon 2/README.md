# InterviewAI

InterviewAI is a full-stack AI-powered interview preparation and assessment platform built for college students and freshers by Team Neural Nexus.

## Features

- Student registration, login, profile setup, dashboard, performance, and history
- Admin/question setter login and separate admin dashboard
- SQLite question bank with create, edit, publish, unpublish, soft delete, search, filters, bulk actions, and CSV import
- Aptitude and technical assessments from published database questions only
- Historical question snapshots so old results do not change after edits
- Timed tests with navigation, auto-submit, result review, explanations, and score calculation
- Spoken English practice with continuous browser speech recognition
- AI HR interview with dynamic questions, typed or voice answers, and scoring
- Personalized recommendations and Chart.js analytics
- Friendly handling when `OPENAI_API_KEY` is not configured

## Tech Stack

Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Font Awesome, Chart.js  
Backend: Python, Flask, Jinja2  
Database: SQLite  
Authentication: Flask sessions and Werkzeug password hashing  
AI: OpenAI-compatible API through `python-dotenv`

## Folder Structure

```text
InterviewAI/
  app.py
  config.py
  requirements.txt
  .env.example
  database/
  services/
  utils/
  templates/
  static/
  exports/
```

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env`, then add your API key if you want AI evaluation:

```text
SECRET_KEY=your_secret_key
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
```

The app works without an API key for normal assessments. AI pages show a friendly unavailable message until the key is configured.

## Database Setup

```powershell
python database/seed.py
```

This creates `database/interviewai.db`, demo users, settings, 10 aptitude questions, and 15 technical questions.

## Run Project

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Demo Logins

Student:

```text
demo@interviewai.com
Demo@123
```

Admin:

```text
admin@interviewai.com
Admin@123
```

## How to Add Questions

Login at `/admin/login`, open Question Bank, then Create Question. Published and active questions become available to students. Draft or soft-deleted questions are hidden from student assessments.

## CSV Import

Upload a `.csv` from the Question Bank page with these columns:

```text
type,category,topic,difficulty,question,option_a,option_b,option_c,option_d,correct_answer,explanation,marks,time_limit
```

## Voice Feature

Spoken English and HR interview voice input use the browser Web Speech API. Chrome and Edge provide the best support. Spoken English recognition runs continuously until the user clicks Stop.

## Security

- Passwords are hashed with Werkzeug
- Sessions enforce role-based access
- SQL queries use parameterized statements
- `.env` is ignored by git
- Student assessments only use published and active database questions
- Assessment results read from snapshots, not live editable questions

## Future Enhancements

- Export analytics reports
- Add richer admin audit logs
- Add email notifications
- Add proctored interview mode
- Add advanced topic recommendation models
