from flask import Flask, request, jsonify
import os
import hashlib

app = Flask(__name__)

VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

@app.route('/ebay/notifications', methods=['GET', 'POST'])
def handle_notifications():
    if request.method == 'GET':
        challenge_code = request.args.get('challenge_code')
        if challenge_code:
            challenge_response = hashlib.sha256(f"{challenge_code}{VERIFICATION_TOKEN}{request.url}".encode()).hexdigest()
            return jsonify({"challengeResponse": challenge_response})
    
    token = request.headers.get('Verification-Token')
    if token != VERIFICATION_TOKEN:
        return jsonify({'error': 'Invalid verification token'}), 403

    data = request.json
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
