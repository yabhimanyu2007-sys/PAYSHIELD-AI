from app.sentinel_ai import analyze_with_sentinel

result = analyze_with_sentinel(
    "Analyze this test message. Reply exactly: "
    "PAYSHIELD_SENTINEL_ONLINE"
)

print("SENTINEL STATUS:", result["status"])
print("RESULT:", result["analysis"] or result["reason"])