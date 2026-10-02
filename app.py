from flask import Flask, request, jsonify
from flask_cors import CORS
from extract_resume import extract_text

app = Flask(__name__)
CORS(app, origins=["https://mora11do.github.io"])



@app.route("/")
def home():
    return "Flask backend is running!"


@app.route("/upload", methods=["POST"])
def upload_resume():

    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    resume = request.files["resume"]

    if resume.filename == "":
        return jsonify({"error": "No file selected"}), 400

    resume.save("uploaded_resume.pdf")

    try:
        resume_text = extract_text("uploaded_resume.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Resume received successfully!",
        "resume_text": resume_text
    })


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5001
    )
