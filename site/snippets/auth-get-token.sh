# Get token (no auth)
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
# Then: curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
