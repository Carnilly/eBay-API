from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Your verification token
VERIFICATION_TOKEN = "69255616708390672115868036044964"

@app.route('/ebay/notifications', methods=['POST'])
def handle_notifications():
    token = request.headers.get('Verification-Token')
    if token != VERIFICATION_TOKEN:
        return jsonify({'error': 'Invalid verification token'}), 403

    data = request.json
    print("Received notification:", data)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
