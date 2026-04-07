import httpx

# Login
data = {"username": "admin", "password": "admin_secure_password"}
resp = httpx.post("http://localhost:8000/api/auth/login", data=data)
token = resp.json().get("access_token")

# PUT details
headers = {"Authorization": f"Bearer {token}"}
put_data = {"is_active": True}
resp = httpx.put("http://localhost:8000/api/admin/users/1", json=put_data, headers=headers)
print("Status:", resp.status_code)
print("Response:", resp.text)
