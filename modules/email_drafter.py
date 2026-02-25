"""AI Email/Message Drafter backend for Gizmo."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

TEMPLATES: Dict[str, str] = {
    "Email to Professor (Question)": (
        "Write a {tone} email from a student named {recipient_label} to Professor {recipient} "
        "for {subject}. The purpose is: {purpose}. "
        "The email should open with a respectful greeting, clearly state the question or request, "
        "and close professionally."
    ),
    "Request Extension": (
        "Write a {tone} email from a student to Professor {recipient} "
        "for {subject}. The purpose is: {purpose}. "
        "The student is requesting an extension on an assignment. "
        "Be polite, provide a brief reason, and ask for a specific extension timeframe."
    ),
    "Study Group Message": (
        "Write a {tone} message to classmates for {subject}. "
        "The purpose is: {purpose}. "
        "Invite them to join a study group, mention the topic, and suggest a time/place."
    ),
    "Assignment Submission": (
        "Write a {tone} email to Professor {recipient} for {subject}. "
        "The purpose is: {purpose}. "
        "The student is submitting a completed assignment. Keep it brief and professional."
    ),
    "Thank You Email": (
        "Write a {tone} thank-you email to {recipient} regarding {subject}. "
        "The purpose is: {purpose}. "
        "Express genuine gratitude and be specific about what you are thankful for."
    ),
    "Absence Notification": (
        "Write a {tone} email to Professor {recipient} for {subject}. "
        "The purpose is: {purpose}. "
        "Notify the professor about an upcoming or recent absence and ask about missed material."
    ),
}

TONES = ["formal", "casual", "apologetic", "professional"]


def _call_ai(prompt: str, max_tokens: int = 512) -> Tuple[Optional[str], Optional[str]]:
    """Call the AI model with the given prompt. Returns (output, error)."""
    try:
        from modules import shared
        if shared.model is None:
            return None, "❌ No AI model loaded. Please load a model first."
        state = shared.settings.copy()
        state['max_new_tokens'] = max_tokens
        from modules.text_generation import generate_reply
        output = ""
        for chunk in generate_reply(prompt, state, stopping_strings=[], is_chat=False):
            if isinstance(chunk, str):
                output = chunk
            elif isinstance(chunk, (list, tuple)) and len(chunk) > 0:
                output = chunk[0] if isinstance(chunk[0], str) else str(chunk[0])
        return output.strip(), None
    except Exception as exc:
        return None, f"❌ AI error: {exc}"


def get_memory_autofill() -> Dict[str, str]:
    """Read chat_memory and return autofill values for name, class, professor."""
    result = {"name": "", "subject": "", "professor": ""}
    try:
        from modules.chat_memory import _load_memories
        memories = _load_memories()
        for m in memories:
            fact = m.get("fact", "")
            category = m.get("category", "")
            fact_lower = fact.lower()
            if category in ("personal", "academic") or not result["name"]:
                if "my name is" in fact_lower:
                    result["name"] = fact.split("is", 1)[-1].strip().rstrip(".")
                elif "name:" in fact_lower:
                    result["name"] = fact.split(":", 1)[-1].strip()
            if category == "academic" or "professor" in fact_lower or "prof." in fact_lower:
                if "professor" in fact_lower or "prof." in fact_lower:
                    # Try to extract professor name
                    for keyword in ["professor is", "professor:", "prof.", "prof "]:
                        if keyword in fact_lower:
                            idx = fact_lower.index(keyword) + len(keyword)
                            result["professor"] = fact[idx:].strip().rstrip(".").split()[0:2]
                            result["professor"] = " ".join(result["professor"])
                            break
            if "class" in fact_lower or "course" in fact_lower or "subject" in fact_lower:
                for keyword in ["class is", "course is", "subject is", "class:", "course:", "subject:"]:
                    if keyword in fact_lower:
                        result["subject"] = fact.split(":", 1)[-1].strip() if ":" in keyword else fact.split("is", 1)[-1].strip().rstrip(".")
                        break
    except Exception:
        pass
    return result


def generate_email(
    recipient: str,
    subject: str,
    purpose: str,
    tone: str,
    template_name: str,
    sender_name: str = "",
) -> Tuple[str, Optional[str]]:
    """Generate an email/message using the selected template and AI."""
    if not purpose.strip():
        return "", "❌ Please describe the purpose/context of the email."

    tone = tone or "formal"
    template_name = template_name or list(TEMPLATES.keys())[0]

    template = TEMPLATES.get(template_name, list(TEMPLATES.values())[0])
    recipient_label = sender_name if sender_name.strip() else "the student"

    prompt = template.format(
        tone=tone,
        recipient=recipient.strip() or "the Professor",
        recipient_label=recipient_label,
        subject=subject.strip() or "the course",
        purpose=purpose.strip(),
    )

    if sender_name.strip():
        prompt += f"\n\nSign the email as: {sender_name.strip()}"

    output, error = _call_ai(prompt)
    if error:
        return "", error
    return output or "", None
