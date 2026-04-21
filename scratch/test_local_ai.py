import requests

# Local login to get session
session = requests.Session()
login_payload = {
    "username": "admin",
    "password": "123" # Or whatever the default is, wait I don't know the password
}

# Instead of login, I'll just write a script to mimic exactly what ia_kalu does locally. 
# But wait, I've already tested the API itself and it works.
