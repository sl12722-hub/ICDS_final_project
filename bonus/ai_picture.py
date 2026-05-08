"""Optional AI picture generation helpers."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests
from shared.ai_config import get_openai_api_key, get_openai_base_url, get_openai_model

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - tkinter optional in headless tests
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]

AIPIC_PREFIX = "/aipic:"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"
OUTPUT_DIR_NAME = "generated_images"
REQUEST_TIMEOUT = 60


class AIPictureError(Exception):
    """Raised when AI picture generation fails."""

def _build_image_prompt_with_llm(prompt: str) -> str:
    """Use the configured LLM to turn a user request into a concise image prompt."""

    system_prompt = (
        "You write production-ready prompts for text-to-image models. "
        "Return one concise visual prompt only. "
        "Do not add markdown, labels, explanations, or quotation marks."
    )
    payload = {
        "model": get_openai_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Rewrite this into a vivid image-generation prompt with subject, style, "
                    "lighting, composition, and quality hints when useful. "
                    f"User request: {prompt}"
                ),
            },
        ],
        "temperature": 0.4,
    }

    try:
        response = requests.post(
            f"{get_openai_base_url()}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {get_openai_api_key()}",
            },
            data=json.dumps(payload),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIPictureError(f"Prompt model request failed: {exc}") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIPictureError("Prompt model returned an unexpected response.") from exc

    if not content:
        raise AIPictureError("Prompt model returned an empty prompt.")
    return content


def parse_aipic_prompt(message: str) -> str | None:
    """Return prompt text for '/aipic: ...' messages, otherwise None."""
    stripped = message.strip()
    if not stripped.lower().startswith(AIPIC_PREFIX):
        return None
    prompt = stripped[len(AIPIC_PREFIX) :].strip()
    return prompt or None


def _slugify_filename(prompt: str) -> str:
    words = re.findall(r"[a-z0-9]+", prompt.lower())
    if not words:
        return "generated_image"
    if len(words) == 1:
        return words[0]
    return f"{words[0]}_{words[-1]}"[:80]


def _ensure_unique_path(folder: Path, stem: str) -> Path:
    candidate = folder / f"{stem}.png"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        new_candidate = folder / f"{stem}_{index}.png"
        if not new_candidate.exists():
            return new_candidate
    return folder / f"{stem}_{os.getpid()}.png"


def generate_image(prompt: str, output_root: Path | None = None) -> str:
    """
    Generate image using the configured LLM for prompt writing and Pollinations for rendering.

    Returns a relative path like 'generated_images/example.png'.
    """
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise AIPictureError("Empty image prompt.")

    rendered_prompt = _build_image_prompt_with_llm(cleaned_prompt)

    root = output_root if output_root is not None else Path.cwd()
    output_dir = root / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _ensure_unique_path(output_dir, _slugify_filename(cleaned_prompt))

    try:
        response = requests.get(
            f"{POLLINATIONS_URL}/{quote(rendered_prompt)}",
            params={"model": "flux", "width": 768, "height": 768},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIPictureError(f"Image API request failed: {exc}") from exc

    data = response.content
    if not data:
        raise AIPictureError("Image API returned empty data.")

    if Image is not None:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.save(output_path, format="PNG")
        except (OSError, ValueError) as exc:
            raise AIPictureError(f"Invalid image response: {exc}") from exc
    else:
        output_path.write_bytes(data)

    relative = output_path.relative_to(root)
    return str(relative).replace("\\", "/")


def try_aipic_reply(message: str, output_root: Path | None = None) -> str | None:
    """
    Process /aipic command and return user-facing result text.

    Returns None when the message is not an /aipic command.
    """
    prompt = parse_aipic_prompt(message)
    if prompt is None:
        return None
    try:
        saved_path = generate_image(prompt, output_root=output_root)
        return f"Generated image saved: {saved_path}"
    except Exception as exc:
        return f"[AI picture] {exc}"


def show_image_preview(image_path: str, master: tk.Misc | None = None) -> None:
    """Open a small Tk popup preview. No-op when UI/image libs are unavailable."""
    if tk is None or ttk is None or Image is None or ImageTk is None:
        return
    path = Path(image_path)
    if not path.is_file():
        return

    window = tk.Toplevel(master) if master is not None else tk.Tk()
    window.title("AI Picture Preview")
    try:
        image = Image.open(path)
        image.thumbnail((900, 900))
        photo = ImageTk.PhotoImage(image)
    except OSError:
        window.destroy()
        return

    label = ttk.Label(window, image=photo)
    label.image = photo
    label.pack(padx=8, pady=8)
