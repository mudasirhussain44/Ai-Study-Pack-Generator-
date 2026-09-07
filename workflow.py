import json
import re
import time
from typing import Any, Callable, Dict, Optional

import requests

from prompts import (
    PLANNING_PROMPT,
    CONTENT_PROMPT,
    REVIEW_PROMPT,
    REFINEMENT_PROMPT,
)

DEFAULT_MODEL = "gemini-2.5-flash"


class WorkflowError(Exception):
    """Controlled error for a failed workflow stage."""


def parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    raise WorkflowError("AI returned invalid JSON.")


def gemini_generate(
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 8000,
    retries: int = 2,
) -> str:
    if not api_key:
        raise WorkflowError("Gemini API key is missing.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    last_error = "Gemini request failed."

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=120)

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"Temporary Gemini error (HTTP {response.status_code})."
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue

            if not response.ok:
                try:
                    message = response.json().get("error", {}).get(
                        "message", response.text
                    )
                except Exception:
                    message = response.text
                raise WorkflowError(
                    f"Gemini API error ({response.status_code}): {message}"
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise WorkflowError("Gemini returned no candidates.")

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(
                p.get("text", "")
                for p in parts
                if isinstance(p, dict) and p.get("text")
            ).strip()

            if not text:
                raise WorkflowError("Gemini returned an empty response.")

            return text

        except requests.Timeout:
            last_error = "Gemini request timed out."
        except requests.RequestException as exc:
            last_error = f"Network error: {exc}"

        if attempt < retries:
            time.sleep(2 ** attempt)

    raise WorkflowError(last_error)


def run_json_stage(
    stage_name: str,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> Dict[str, Any]:
    try:
        raw = gemini_generate(
            api_key, model, prompt, temperature, max_tokens
        )
        return parse_json(raw)
    except Exception as exc:
        raise WorkflowError(f"{stage_name} failed: {exc}") from exc


def planning_agent(api_key, model, user_context):
    prompt = PLANNING_PROMPT.format(
        user_context=json.dumps(user_context, ensure_ascii=False, indent=2)
    )
    return run_json_stage("Planning", api_key, model, prompt, 0.2, 4500)


def content_agent(api_key, model, user_context, plan):
    prompt = CONTENT_PROMPT.format(
        user_context=json.dumps(user_context, ensure_ascii=False, indent=2),
        plan=json.dumps(plan, ensure_ascii=False, indent=2),
    )
    return run_json_stage(
        "Content Generation", api_key, model, prompt, 0.4, 10000
    )


def review_agent(api_key, model, user_context, plan, draft):
    prompt = REVIEW_PROMPT.format(
        user_context=json.dumps(user_context, ensure_ascii=False, indent=2),
        plan=json.dumps(plan, ensure_ascii=False, indent=2),
        draft=json.dumps(draft, ensure_ascii=False, indent=2),
    )
    return run_json_stage(
        "Assignment Review", api_key, model, prompt, 0.15, 8000
    )


def refinement_agent(api_key, model, user_context, plan, draft, review):
    prompt = REFINEMENT_PROMPT.format(
        user_context=json.dumps(user_context, ensure_ascii=False, indent=2),
        plan=json.dumps(plan, ensure_ascii=False, indent=2),
        draft=json.dumps(draft, ensure_ascii=False, indent=2),
        review=json.dumps(review, ensure_ascii=False, indent=2),
    )
    return run_json_stage(
        "Refinement", api_key, model, prompt, 0.25, 10000
    )


def run_study_workflow(
    api_key: str,
    model: str,
    user_context: Dict[str, Any],
    on_stage: Optional[Callable[[str, int], None]] = None,
) -> Dict[str, Any]:
    """Run Planning -> Generation -> Review -> Refinement."""

    result = {
        "plan": None,
        "draft": None,
        "review": None,
        "final": None,
        "errors": [],
    }

    def notify(stage, progress):
        if on_stage:
            on_stage(stage, progress)

    notify("Planning", 10)
    try:
        result["plan"] = planning_agent(api_key, model, user_context)
    except Exception as exc:
        result["errors"].append({"stage": "Planning", "error": str(exc)})
        raise

    notify("Content Generation", 35)
    try:
        result["draft"] = content_agent(
            api_key, model, user_context, result["plan"]
        )
    except Exception as exc:
        result["errors"].append(
            {"stage": "Content Generation", "error": str(exc)}
        )
        raise

    notify("Assignment Review", 65)
    try:
        result["review"] = review_agent(
            api_key, model, user_context,
            result["plan"], result["draft"]
        )
    except Exception as exc:
        result["errors"].append(
            {"stage": "Assignment Review", "error": str(exc)}
        )
        raise

    notify("Refinement", 85)
    try:
        result["final"] = refinement_agent(
            api_key, model, user_context,
            result["plan"], result["draft"], result["review"]
        )
    except Exception as exc:
        result["errors"].append(
            {"stage": "Refinement", "error": str(exc)}
        )
        raise

    notify("Complete", 100)
    return result
