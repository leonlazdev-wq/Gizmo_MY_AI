"""Smart Context System — automatically gathers and injects relevant context into chat prompts."""

from __future__ import annotations

import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from modules.logging_colors import logger

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
_SMART_CONTEXT_SETTINGS_FILE = os.path.join("user_data", "smart_context_settings.json")
_FLASHCARDS_DIR = os.path.join("user_data", "flashcards")
_QUIZ_RESULTS_DIR = os.path.join("user_data", "quiz_results")
_ASSIGNMENTS_FILE = os.path.join("user_data", "assignments.json")
_GAMIFICATION_FILE = os.path.join("user_data", "gamification.json")
_STUDY_PLANS_DIR = os.path.join("user_data", "study_plans")
_MEMORY_PATH = Path("user_data/memory.json")

# ---------------------------------------------------------------------------
# Keyword intent groups for relevance detection
# ---------------------------------------------------------------------------
ACADEMIC_KEYWORDS = [
    'study', 'exam', 'test', 'quiz', 'homework', 'assignment',
    'essay', 'class', 'course', 'grade', 'lecture', 'review',
    'flashcard', 'learn', 'practice', 'prepare', 'deadline', 'school',
    'subject', 'chapter', 'topic', 'research', 'notes',
]

SCHEDULE_KEYWORDS = [
    'today', 'tomorrow', 'this week', 'schedule', 'plan',
    'due', 'deadline', 'calendar', 'when', 'upcoming', 'soon',
    'next week', 'tonight', 'morning', 'evening',
]

PROGRESS_KEYWORDS = [
    'progress', 'score', 'streak', 'xp', 'level', 'badge',
    'how am i doing', 'performance', 'improvement', 'achievement',
    'rank', 'points', 'reward', 'stats',
]

GENERAL_KEYWORDS = [
    'help', 'what should i', 'recommend', 'suggest', 'advice',
    'what do i', 'should i', 'where do i', 'how do i start',
    'focus', 'prioritize',
]

# Approximate characters per token (rough estimate used for budget enforcement)
_CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def load_smart_context_settings() -> Dict:
    """Load smart context settings from file, returning defaults if missing."""
    defaults = {
        'enable_smart_context': True,
        'smart_context_sources': {
            'academic_profile': True,
            'deadlines': True,
            'flashcard_status': True,
            'quiz_scores': True,
            'study_planner': True,
            'calendar': True,
            'classroom': True,
            'documents': True,
            'gamification': True,
        },
        'smart_context_max_tokens': 1500,
    }
    if not os.path.isfile(_SMART_CONTEXT_SETTINGS_FILE):
        return defaults
    try:
        with open(_SMART_CONTEXT_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        merged = defaults.copy()
        merged.update(saved)
        if 'smart_context_sources' in saved:
            merged['smart_context_sources'] = {**defaults['smart_context_sources'], **saved['smart_context_sources']}
        return merged
    except Exception:
        return defaults


def save_smart_context_settings(settings: Dict) -> None:
    """Persist smart context settings to disk."""
    os.makedirs("user_data", exist_ok=True)
    with open(_SMART_CONTEXT_SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Data collection helpers (each returns empty gracefully if source missing)
# ---------------------------------------------------------------------------

def _get_academic_profile() -> List[str]:
    """Extract academic facts from chat memory."""
    try:
        if not _MEMORY_PATH.exists():
            return []
        memories = json.loads(_MEMORY_PATH.read_text(encoding='utf-8'))
        return [
            m['fact'] for m in memories
            if m.get('category', '') in ('academic', 'personal', 'work')
        ]
    except Exception:
        return []


def _get_flashcard_status() -> List[Dict]:
    """Get all flashcard decks with review status (based on file modification time)."""
    if not os.path.isdir(_FLASHCARDS_DIR):
        return []
    decks = []
    try:
        for fname in os.listdir(_FLASHCARDS_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(_FLASHCARDS_DIR, fname)
            try:
                mtime = os.path.getmtime(fpath)
                last_modified = datetime.fromtimestamp(mtime)
                days_ago = (datetime.now() - last_modified).days
                with open(fpath, 'r', encoding='utf-8') as f:
                    cards = json.load(f)
                card_count = len(cards) if isinstance(cards, list) else 0
                deck_name = fname[:-5]  # strip .json
                decks.append({
                    'name': deck_name,
                    'card_count': card_count,
                    'days_since_review': days_ago,
                    'needs_review': days_ago >= 3,
                })
            except Exception:
                continue
    except Exception:
        pass
    return decks


def _get_quiz_performance() -> Dict:
    """Get quiz performance summary — average per topic, weak topics (<70%)."""
    if not os.path.isdir(_QUIZ_RESULTS_DIR):
        return {}
    topic_scores: Dict[str, List[float]] = {}
    try:
        for fname in os.listdir(_QUIZ_RESULTS_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(_QUIZ_RESULTS_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                topic = result.get('topic', 'Unknown')
                pct = result.get('percentage', 0)
                topic_scores.setdefault(topic, []).append(pct)
            except Exception:
                continue
    except Exception:
        pass

    if not topic_scores:
        return {}

    topic_averages = {
        t: round(sum(scores) / len(scores), 1)
        for t, scores in topic_scores.items()
    }
    weak_topics = {t: avg for t, avg in topic_averages.items() if avg < 70}
    return {
        'topic_averages': topic_averages,
        'weak_topics': weak_topics,
    }


def _get_upcoming_deadlines(days_ahead: int = 7) -> List[Dict]:
    """Get upcoming deadlines from assignments tracker, sorted by due date."""
    if not os.path.isfile(_ASSIGNMENTS_FILE):
        return []
    try:
        with open(_ASSIGNMENTS_FILE, 'r', encoding='utf-8') as f:
            assignments = json.load(f)
        if not isinstance(assignments, list):
            return []

        today = date.today()
        cutoff = today + timedelta(days=days_ahead)
        upcoming = []
        for a in assignments:
            due_str = a.get('due_date', '') or a.get('deadline', '')
            if not due_str:
                continue
            status = a.get('status', '').lower()
            if status == 'completed':
                continue
            try:
                due_date = datetime.fromisoformat(due_str[:10]).date()
            except Exception:
                continue
            if today <= due_date <= cutoff:
                days_left = (due_date - today).days
                upcoming.append({
                    'name': a.get('name', a.get('title', 'Assignment')),
                    'due_date': due_str[:10],
                    'days_left': days_left,
                    'course': a.get('course', a.get('subject', '')),
                    'priority': a.get('priority', 'medium'),
                })
        upcoming.sort(key=lambda x: x['days_left'])
        return upcoming
    except Exception:
        return []


def _get_study_plan_today() -> List[Dict]:
    """Get today's scheduled study sessions from study planner."""
    if not os.path.isdir(_STUDY_PLANS_DIR):
        return []
    today_str = date.today().isoformat()
    sessions = []
    try:
        for fname in os.listdir(_STUDY_PLANS_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(_STUDY_PLANS_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    plan = json.load(f)
                schedule = plan.get('schedule', [])
                for item in schedule:
                    item_date = item.get('date', '')
                    if item_date.startswith(today_str):
                        subject = item.get('subject', '')
                        if not subject and plan.get('subjects'):
                            subject = plan['subjects'][0].get('subject', 'Study')
                        sessions.append({
                            'subject': subject or 'Study',
                            'time': item.get('time', ''),
                            'duration': item.get('duration_hours', item.get('duration', '')),
                            'completed': item.get('completed', False),
                        })
            except Exception:
                continue
    except Exception:
        pass
    return sessions


def _get_gamification_status() -> Dict:
    """Get XP, streak, level, and recent badges."""
    if not os.path.isfile(_GAMIFICATION_FILE):
        return {}
    try:
        with open(_GAMIFICATION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        xp = data.get('xp', 0)
        streak = data.get('streak', {}).get('current', 0)
        badges = data.get('badges', {})
        recent_badges = [
            b.get('name', bid) if isinstance(b, dict) else bid
            for bid, b in badges.items()
        ][-3:]

        try:
            from modules.gamification import get_level_info
            level_info = get_level_info(xp)
            level_name = level_info.get('level_name', 'Beginner')
        except Exception:
            level_name = 'Beginner'

        return {
            'xp': xp,
            'level_name': level_name,
            'streak': streak,
            'recent_badges': recent_badges,
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def gather_all_context() -> Dict:
    """Gather context from every feature module. Returns a dict of context sections."""
    settings = load_smart_context_settings()
    sources = settings.get('smart_context_sources', {})

    context: Dict = {}

    if sources.get('academic_profile', True):
        profile = _get_academic_profile()
        if profile:
            context['academic_profile'] = profile

    if sources.get('deadlines', True):
        deadlines = _get_upcoming_deadlines()
        if deadlines:
            context['deadlines'] = deadlines

    if sources.get('flashcard_status', True):
        decks = _get_flashcard_status()
        if decks:
            context['flashcards'] = decks

    if sources.get('quiz_scores', True):
        quiz = _get_quiz_performance()
        if quiz:
            context['quiz'] = quiz

    if sources.get('study_planner', True):
        sessions = _get_study_plan_today()
        if sessions:
            context['study_plan_today'] = sessions

    if sources.get('gamification', True):
        gami = _get_gamification_status()
        if gami:
            context['gamification'] = gami

    return context


# ---------------------------------------------------------------------------
# Relevance ranking
# ---------------------------------------------------------------------------

def _detect_subjects(user_message: str, context: Dict) -> List[str]:
    """Find subject names from context that appear (fuzzy) in the user message."""
    msg_lower = user_message.lower()
    subjects = set()

    for deck in context.get('flashcards', []):
        deck_name = deck['name'].lower()
        if deck_name in msg_lower or msg_lower in deck_name:
            subjects.add(deck['name'])
        for word in deck_name.split():
            if len(word) >= 3 and word in msg_lower:
                subjects.add(deck['name'])

    quiz = context.get('quiz', {})
    for topic in quiz.get('topic_averages', {}):
        topic_lower = topic.lower()
        if topic_lower in msg_lower:
            subjects.add(topic)
        for word in topic_lower.split():
            if len(word) >= 3 and word in msg_lower:
                subjects.add(topic)

    return list(subjects)


def get_relevant_context(user_message: str, max_tokens: Optional[int] = None) -> str:
    """
    Analyze the user's message and return ONLY the relevant context string.
    Returns an empty string if smart context is disabled or nothing is relevant.
    """
    settings = load_smart_context_settings()

    if not settings.get('enable_smart_context', True):
        return ''

    if max_tokens is None:
        max_tokens = settings.get('smart_context_max_tokens', 1500)

    context = gather_all_context()
    if not context:
        return ''

    msg_lower = user_message.lower()

    is_academic = any(kw in msg_lower for kw in ACADEMIC_KEYWORDS)
    is_schedule = any(kw in msg_lower for kw in SCHEDULE_KEYWORDS)
    is_progress = any(kw in msg_lower for kw in PROGRESS_KEYWORDS)
    is_general = any(kw in msg_lower for kw in GENERAL_KEYWORDS)
    detected_subjects = _detect_subjects(user_message, context)

    selected: Dict = {}

    # Always include basic academic profile (capped at 3 items)
    if 'academic_profile' in context:
        selected['academic_profile'] = context['academic_profile'][:3]

    # Urgent deadlines (<2 days) always shown
    if 'deadlines' in context:
        urgent = [d for d in context['deadlines'] if d['days_left'] <= 1]
        if urgent:
            selected['deadlines'] = urgent

    if is_schedule or is_academic or is_general:
        if 'deadlines' in context:
            selected['deadlines'] = context['deadlines']
        if 'study_plan_today' in context:
            selected['study_plan_today'] = context['study_plan_today']

    if is_academic or is_general or detected_subjects:
        if 'quiz' in context:
            selected['quiz'] = context['quiz']
        if 'flashcards' in context:
            if detected_subjects:
                subject_lower = [s.lower() for s in detected_subjects]
                related = [d for d in context['flashcards'] if any(s in d['name'].lower() for s in subject_lower)]
                other = [d for d in context['flashcards'] if d not in related]
                selected['flashcards'] = related + other
            else:
                selected['flashcards'] = context['flashcards']

    if is_progress or is_general:
        if 'gamification' in context:
            selected['gamification'] = context['gamification']

    return build_context_block(selected, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Context block builder
# ---------------------------------------------------------------------------

def build_context_block(relevant_context: Dict, max_tokens: int = 1500) -> str:
    """
    Build a well-formatted context block to prepend to the system prompt.
    Respects max_tokens budget (approximate).
    """
    if not relevant_context:
        return ''

    lines: List[str] = ['[Smart Context — Gizmo knows this about you]', '']
    budget_chars = max_tokens * _CHARS_PER_TOKEN

    def _add_section(section_lines: List[str]) -> bool:
        nonlocal budget_chars
        block = '\n'.join(section_lines) + '\n'
        if budget_chars - len(block) < 0:
            return False
        lines.extend(section_lines)
        lines.append('')
        budget_chars -= len(block)
        return True

    if 'academic_profile' in relevant_context:
        section = ['📚 Academic Profile:']
        for fact in relevant_context['academic_profile']:
            section.append(f'- {fact}')
        _add_section(section)

    if 'deadlines' in relevant_context:
        section = ['⏰ Upcoming Deadlines:']
        for d in relevant_context['deadlines']:
            days = d['days_left']
            if days == 0:
                timing = 'due TODAY'
            elif days == 1:
                timing = 'due tomorrow'
            else:
                timing = f'due in {days} days ({d["due_date"]})'
            course_str = f' [{d["course"]}]' if d.get('course') else ''
            section.append(f'- {d["name"]}{course_str}: {timing}')
        _add_section(section)

    if 'flashcards' in relevant_context:
        needs_review = [d for d in relevant_context['flashcards'] if d['needs_review']]
        if needs_review:
            section = ['🃏 Flashcard Decks Needing Review:']
            for d in needs_review[:5]:
                section.append(
                    f'- "{d["name"]}" ({d["card_count"]} cards, '
                    f'last reviewed {d["days_since_review"]} day(s) ago)'
                )
            _add_section(section)

    if 'quiz' in relevant_context:
        weak = relevant_context['quiz'].get('weak_topics', {})
        if weak:
            section = ['📊 Areas Needing Review (quiz scores <70%):']
            for topic, avg in list(weak.items())[:5]:
                section.append(f'- {topic}: {avg}% average score')
            _add_section(section)

    if 'study_plan_today' in relevant_context:
        section = ["📅 Today's Study Plan:"]
        for s in relevant_context['study_plan_today']:
            status = '✅' if s.get('completed') else '⏳'
            time_str = f' at {s["time"]}' if s.get('time') else ''
            dur_str = f' ({s["duration"]}h)' if s.get('duration') else ''
            section.append(f'{status} {s["subject"]}{time_str}{dur_str}')
        _add_section(section)

    if 'gamification' in relevant_context:
        g = relevant_context['gamification']
        section = ['🏅 Progress:']
        level_str = f'Level: {g.get("level_name", "?")} ({g.get("xp", 0)} XP)'
        streak_str = f'Streak: {g.get("streak", 0)} day(s)'
        section.append(f'- {level_str} | {streak_str}')
        if g.get('recent_badges'):
            section.append(f'- Recent badges: {", ".join(g["recent_badges"])}')
        _add_section(section)

    while lines and lines[-1] == '':
        lines.pop()

    if len(lines) <= 1:
        return ''

    return '\n'.join(lines)
