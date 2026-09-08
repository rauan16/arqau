import requests
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:8000"

def login(email, password):
    resp = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    print(f"LOGIN {email}: {resp.status_code}")
    return resp.json().get("access_token")

def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print("=== USER ISOLATION TEST ===")

# Create User A
resp = requests.post(f"{BASE}/auth/register", json={"email": "user_a@test.com", "password": "passA", "name": "User A"})
print(f"REGISTER A: {resp.status_code} {resp.text[:200]}")
token_a = resp.json().get("access_token")
if not token_a:
    print("Trying login instead...")
    resp = requests.post(f"{BASE}/auth/login", json={"email": "user_a@test.com", "password": "passA"})
    print(f"LOGIN A: {resp.status_code} {resp.text[:200]}")
    token_a = resp.json().get("access_token")

# Create User B
resp = requests.post(f"{BASE}/auth/register", json={"email": "user_b@test.com", "password": "passB", "name": "User B"})
print(f"REGISTER B: {resp.status_code}")
token_b = resp.json().get("access_token")

# Verify tokens work
resp = requests.get(f"{BASE}/auth/me", headers=headers(token_a))
print(f"AUTH ME A: {resp.status_code}")

# User A: add data
requests.put(f"{BASE}/ewa/earned", json={"earned_amount_minor": 500000}, headers=headers(token_a))
requests.post(f"{BASE}/transactions", json={"type": "income", "amount_minor": 600000, "category": "Salary", "merchant": "Employer"}, headers=headers(token_a))
requests.post(f"{BASE}/transactions", json={"type": "expense", "amount_minor": 120000, "category": "Rent", "merchant": "Landlord"}, headers=headers(token_a))
requests.post(f"{BASE}/ewa/request", json={"amount_minor": 30000, "reason": "Emergency"}, headers=headers(token_a))
requests.post(f"{BASE}/budgets", json={"category": "Food", "limit_minor": 50000}, headers=headers(token_a))
requests.post(f"{BASE}/goals", json={"title": "Reserve", "target_minor": 100000}, headers=headers(token_a))

# User B: add different data
requests.put(f"{BASE}/ewa/earned", json={"earned_amount_minor": 300000}, headers=headers(token_b))
requests.post(f"{BASE}/transactions", json={"type": "income", "amount_minor": 400000, "category": "Salary", "merchant": "Employer B"}, headers=headers(token_b))
requests.post(f"{BASE}/ewa/request", json={"amount_minor": 10000, "reason": "Bills"}, headers=headers(token_b))
requests.post(f"{BASE}/budgets", json={"category": "Transport", "limit_minor": 20000}, headers=headers(token_b))
requests.post(f"{BASE}/goals", json={"title": "Travel", "target_minor": 50000}, headers=headers(token_b))

# Check isolation
tx_a = requests.get(f"{BASE}/transactions", headers=headers(token_a)).json()
tx_b = requests.get(f"{BASE}/transactions", headers=headers(token_b)).json()
print(f"User A transactions: {len(tx_a)} (expected 2)")
print(f"User B transactions: {len(tx_b)} (expected 1)")

req_a = requests.get(f"{BASE}/ewa/requests", headers=headers(token_a)).json()
req_b = requests.get(f"{BASE}/ewa/requests", headers=headers(token_b)).json()
print(f"User A requests: {len(req_a)} (expected 1)")
print(f"User B requests: {len(req_b)} (expected 1)")

bud_a = requests.get(f"{BASE}/budgets", headers=headers(token_a)).json()
bud_b = requests.get(f"{BASE}/budgets", headers=headers(token_b)).json()
print(f"User A budgets: {len(bud_a)} (expected 1)")
print(f"User B budgets: {len(bud_b)} (expected 1)")

goal_a = requests.get(f"{BASE}/goals", headers=headers(token_a)).json()
goal_b = requests.get(f"{BASE}/goals", headers=headers(token_b)).json()
print(f"User A goals: {len(goal_a)} (expected 1)")
print(f"User B goals: {len(goal_b)} (expected 1)")

# Verify isolation
merchants_a = [t["merchant"] for t in tx_a]
merchants_b = [t["merchant"] for t in tx_b]
assert "Employer" in merchants_a and "Landlord" in merchants_a
assert "Employer B" in merchants_b
assert "Employer" not in merchants_b
assert "Employer B" not in merchants_a
assert req_a[0]["reason"] == "Emergency"
assert req_b[0]["reason"] == "Bills"
assert bud_a[0]["category"] == "Food"
assert bud_b[0]["category"] == "Transport"
assert goal_a[0]["title"] == "Reserve"
assert goal_b[0]["title"] == "Travel"
print("User isolation: PASS")

# --- EWA INVARIANTS ---
print("\n=== EWA INVARIANTS ===")
ew_a = requests.get(f"{BASE}/ewa/earned", headers=headers(token_a)).json()
print(f"Earned: {ew_a['earned_amount_minor']}, Accessed: {ew_a['accessed_amount_minor']}, Available: {ew_a['available_amount_minor']}")
assert ew_a["earned_amount_minor"] == 500000
assert ew_a["accessed_amount_minor"] == 30000
assert ew_a["available_amount_minor"] == 470000
assert ew_a["available_amount_minor"] == ew_a["earned_amount_minor"] - ew_a["accessed_amount_minor"]
assert ew_a["earned_amount_minor"] >= 0 and ew_a["accessed_amount_minor"] >= 0 and ew_a["available_amount_minor"] >= 0
print("EWA invariants: PASS")

# --- EMPTY STATE ---
print("\n=== EMPTY STATE ===")
resp = requests.post(f"{BASE}/auth/register", json={"email": "empty@test.com", "password": "empty123"})
token_empty = resp.json().get("access_token")

summary = requests.get(f"{BASE}/finance/summary", headers=headers(token_empty)).json()
assert summary["total_income_minor"] == 0
assert summary["total_expense_minor"] == 0
assert summary["transaction_count"] == 0

txns = requests.get(f"{BASE}/transactions", headers=headers(token_empty)).json()
assert len(txns) == 0

ew = requests.get(f"{BASE}/ewa/earned", headers=headers(token_empty)).json()
assert ew["earned_amount_minor"] == 0
assert ew["available_amount_minor"] == 0

reqs = requests.get(f"{BASE}/ewa/requests", headers=headers(token_empty)).json()
assert len(reqs) == 0

buds = requests.get(f"{BASE}/budgets", headers=headers(token_empty)).json()
assert len(buds) == 0

goals = requests.get(f"{BASE}/goals", headers=headers(token_empty)).json()
assert len(goals) == 0
print("Empty state: PASS")

# --- AUTH ---
print("\n=== AUTH ===")
assert requests.get(f"{BASE}/auth/me").status_code == 401
assert requests.get(f"{BASE}/finance/summary").status_code == 401
assert requests.get(f"{BASE}/ewa/earned").status_code == 401
assert requests.post(f"{BASE}/ai/analyze-withdrawal", json={"withdrawal_amount": 100}).status_code == 401
print("Auth: PASS")

# --- WITHDRAWAL VALIDATION ---
print("\n=== WITHDRAWAL VALIDATION ===")
assert requests.post(f"{BASE}/ai/analyze-withdrawal", json={"withdrawal_amount": 0}, headers=headers(token_a)).status_code == 400
assert requests.post(f"{BASE}/ai/analyze-withdrawal", json={"withdrawal_amount": 999999}, headers=headers(token_a)).status_code == 400
print("Withdrawal validation: PASS")

# --- AI QUOTA STATUS ---
print("\n=== AI QUOTA ===")
resp = requests.post(f"{BASE}/ai/analyze-withdrawal", json={"withdrawal_amount": 50000}, headers=headers(token_a))
print(f"AI analyze: {resp.status_code} {resp.text[:100]}")
resp = requests.post(f"{BASE}/ai/chat", json={"message": "hi"}, headers=headers(token_a))
print(f"AI chat: {resp.status_code} {resp.text[:100]}")

print("\n=== ALL TESTS PASSED ===")
