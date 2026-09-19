# social/image_prompts.py
# Generates image prompts from article topics through the local Ollama model.

from __future__ import annotations

import re

from integrations.ollama import generate_text

CONTENT_LIMIT = 2500


def _strip_html_tags(text: str | None) -> str:
    """Remove HTML tags, returning an empty string for missing content."""
    if not text:
        return ""

    return re.sub(r"<.*?>", "", text, flags=re.DOTALL).strip()


def generate_image_prompt(
    *,
    article_title: str,
    article_content: str,
    topic: str,
    language: str,
) -> str:
    """Generate one image prompt focused on an article topic."""
    cleaned_content = _strip_html_tags(article_content)[:CONTENT_LIMIT]

    if not cleaned_content:
        raise ValueError("Article content is required for image prompt generation.")

    if not topic.strip():
        raise ValueError("Topic is required for image prompt generation.")

    system_prompt = """
You are the visual director for SmartCartLab.

Create exactly one prompt for an AI image generation model.

The supplied topic defines the specific concept that the image must communicate.
The supplied article provides factual context for understanding that topic.

Translate the topic into a concrete visual scene rather than summarizing the
article.

The image should:
- communicate the topic clearly through visual elements;
- have one strong and recognizable main subject;
- use a coherent setting, composition, lighting, and atmosphere;
- be suitable as an editorial image accompanying a technical article;
- look intentional and visually interesting rather than like generic stock art.

Prefer concrete objects, environments, actions, and visual relationships over
abstract explanations.

Avoid generic technology imagery unless the topic specifically requires it.
Do not automatically use glowing brains, floating code, circuit boards,
holograms, robots, or generic futuristic interfaces.

Do not invent factual details that contradict the supplied article.

Do not include titles, captions, labels, logos, watermarks, UI text, or other
written text in the image unless text is essential to the topic.

Return the image-generation prompt in English, regardless of the article
language.

Return exclusively the final image prompt.
Do not return JSON.
Do not include Markdown, quotation marks, labels, explanations, or introductory
text.
""".strip()

    user_prompt = f"""
Article title:
{article_title}

Article language:
{language}

Topic:
{topic}

Article content:
{cleaned_content}

Create exactly one detailed image-generation prompt focused on the supplied
topic.
""".strip()

    generated_text = generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
        timeout=180,
    )

    if not generated_text:
        raise RuntimeError("Ollama did not generate an image prompt.")

    return generated_text.strip('"').strip("'")