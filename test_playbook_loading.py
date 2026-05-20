from playbooks import load_playbook, list_available_playbooks

print("Available playbooks:", list_available_playbooks())

pb = load_playbook("newsletter-best-practices")
print(f"\nTitle: {pb.title}")
print(f"Tags: {pb.tags}")
print(f"\nBody preview:\n{pb.body_markdown[:300]}...")
