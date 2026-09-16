from database.articles import get_blog_article_by_id
from social.copywriter import generate_social_post

ARTICLE_ID = 'https://www.smartcartlab.com/?p=375'
TOPIC = "Il ruolo dell'operatore umano nel controllo di agenti IA sui social media."

article_row = get_blog_article_by_id(ARTICLE_ID)

if article_row is None:
    raise RuntimeError(f"Article {ARTICLE_ID} not found.")

article = dict(article_row)

for platform in ("mastodon", "facebook"):
    print(f"\n{'=' * 20} {platform.upper()} {'=' * 20}\n")

    post = generate_social_post(
        article_title=article["title"],
        article_content=article["content"],
        article_link=article["link"],
        topic=TOPIC,
        platform=platform,
        language=article.get("lang") or "it",
    )

    print(post["content"])
    print(f"\nCharacters: {len(post['content'])}")