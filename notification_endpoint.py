from flask import Flask, request, jsonify
import hashlib
import os

app = Flask(__name__)

# Hardcoded verification token
VERIFICATION_TOKEN = "69255616708390672115868036044964"

@app.route('/')
def home():
    return "Welcome to eBay Notification App!"

@app.route('/ebay/notifications', methods=['GET', 'POST'])
def handle_notifications():
    print("Request method:", request.method)
    print("Request headers:", request.headers)
    print("Request URL:", request.url)
    
    if request.method == 'GET':
        challenge_code = request.args.get('challenge_code')
        if challenge_code:
            challenge_response = hashlib.sha256(f"{challenge_code}{VERIFICATION_TOKEN}{request.url}".encode()).hexdigest()
            print(f"Challenge code: {challenge_code}")
            print(f"Challenge response: {challenge_response}")
            return jsonify({"challengeResponse": challenge_response})
    
    token = request.headers.get('Verification-Token')
    print(f"Expected token: {VERIFICATION_TOKEN}")
    print(f"Received token: {token}")
    
    if token != VERIFICATION_TOKEN:
        print(f"Invalid token: {token}")
        return jsonify({'error': 'Invalid verification token'}), 403

    data = request.json
    print("Received notification:", data)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
