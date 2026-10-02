from flask import Flask, request, jsonify
from extract_resume import extract_text

app = Flask(__name__)


@app.route("/upload", methods=["POST"])
def upload_resume():

    # Make sure a file was actually uploaded
    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    resume = request.files["resume"]

    # Make sure the user selected a file
    if resume.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Save the uploaded PDF temporarily
    resume.save("uploaded_resume.pdf")

    try:
        # Extract the text from the PDF
        resume_text = extract_text("uploaded_resume.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Send the extracted resume text back for now
    return jsonify({
        "message": "Resume received successfully!",
        "resume_text": resume_text
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)
