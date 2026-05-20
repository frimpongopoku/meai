from dotenv import load_dotenv

load_dotenv()

from newsletter_context import gather_newsletter_context
from prompt_builder import build_system_prompt, build_user_prompt

ctx = gather_newsletter_context(
    site_id=22,
    community_name="Sustainable Medfield",
    theme="winter heating and energy savings",
)

print("=" * 80)
print("SYSTEM PROMPT")
print("=" * 80)
print(build_system_prompt())
print()
print("=" * 80)
print("USER PROMPT")
print("=" * 80)
print(build_user_prompt(ctx))
