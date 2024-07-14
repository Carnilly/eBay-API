from flask import Flask, request, jsonify
import os
import hashlib

app = Flask(__name__)

# Your verification token
VERIFICATION_TOKEN = "69255616708390672115868036044964"
ENDPOINT_URL = "https://brendan-ebay-tracker-861f984cd929.herokuapp.com/ebay/notifications"

@app.route('/ebay/notifications', methods=['POST', 'GET'])
def handle_notifications():
    if request.method == 'GET':
        challenge_code = request.args.get('challenge_code')
        if challenge_code:
            challenge_response = generate_challenge_response(challenge_code, VERIFICATION_TOKEN, ENDPOINT_URL)
            return jsonify({"challengeResponse": challenge_response}), 200
    
    elif request.method == 'POST':
        token = request.headers.get('Verification-Token')
        if token != VERIFICATION_TOKEN:
            return jsonify({'error': 'Invalid verification token'}), 403

        data = request.json
        print("Received notification:", data)
        return jsonify({'status': 'success'}), 200

def generate_challenge_response(challenge_code, verification_token, endpoint):
    combined_string = challenge_code + verification_token + endpoint
    challenge_response = hashlib.sha256(combined_string.encode('utf-8')).hexdigest()
    return challenge_response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
