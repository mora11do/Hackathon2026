from flask import Flask, request, jsonify
from extract_resume import extract_text
from Webscraper import enrich
from geocode import add_coordinates

app = Flask(__name__)


@app.route("/upload", methods=["POST"])
def upload_resume():

    resume = request.files["resume"]

    # Save the uploaded PDF temporarily
    resume.save("resume.pdf")

    # Your team's existing processing
    applicant = extract_text("resume.pdf")

    jobs = enrich(
        keywords=applicant["skills"],
        location=applicant["location"]
    )

    jobs = add_coordinates(jobs)

    matches = []

    for job in jobs:
        matching_skills = set(applicant["skills"]) & set(job["skills"])

        if len(matching_skills) >= 2:
            job["match_score"] = len(matching_skills)
            matches.append(job)

    matches.sort(
        key=lambda job: job["match_score"],
        reverse=True
    )

    return jsonify(matches)


if __name__ == "__main__":
    app.run(debug=True, port=5001)

