# social/topics.py
# Generates editorial topics from blog article content.

from __future__ import annotations

from integrations.ollama import generate_text

CONTENT_LIMIT = 2500

LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
}


def _get_language_instruction(language: str) -> str:
    """Return the output-language instruction for the supplied language code."""
    try:
        language_name = LANGUAGE_NAMES[language.lower()]
    except KeyError as error:
        raise ValueError(f"Unsupported language: {language}") from error

    return f"Write the generated topic strictly in {language_name}."


def generate_article_topic(
    *,
    article_title: str,
    article_content: str,
    existing_topics: list[str],
    language: str,
) -> str | None:
    """Generate one distinct editorial topic from an article."""
    language_rule = _get_language_instruction(language)
    if not article_content or not article_content.strip():
        raise ValueError("Article content is required for topic generation.")

    cleaned_content = article_content.strip()[:CONTENT_LIMIT]


    existing_topics_text = "\n".join(
        f"- {topic}" for topic in existing_topics
    )

    if not existing_topics_text:
        existing_topics_text = "None."

    system_prompt = f"""
You identify distinct editorial topics from blog articles.

A topic is one specific subject, idea, lesson, observation, or point of view
that can be developed independently into social media content.

Identify one new topic only if the article contains a meaningful subject or
argument that is substantially different from the existing topics.

A new topic must:
- be clearly supported by the supplied article;
- focus on one specific idea rather than summarize the whole article;
- contain enough context to be useful later without rereading the article;
- introduce a substantially different subject or argument from the existing topics;
- not be a rewording, narrower version, broader version, or direct variation
  of an existing topic;
- not contain hashtags, calls to action, or social-media-specific wording.

Do not invent a new topic just to satisfy the request.

If no substantially different topic remains in the article, return exactly:
NO_NEW_TOPIC

{language_rule}

Return exclusively the topic text or NO_NEW_TOPIC.
Do not include labels, Markdown, quotation marks, or explanations.
""".strip()

    user_prompt = f"""
Article title:
{article_title}

Article content:
{cleaned_content}

Existing topics:
{existing_topics_text}

Generate one new distinct topic.
""".strip()

    generated_topic = generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
        timeout=180,
    )

    if not generated_topic:
        raise RuntimeError("Ollama did not generate an article topic.")

    generated_topic = generated_topic.strip('"').strip("'").strip()

    if generated_topic == "NO_NEW_TOPIC":
        return None

    return generated_topic