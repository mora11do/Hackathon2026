from extract_resume import extract_resume
from Webscraper import scrape_jobs
from geocode import add_coordinates


def main():
    applicant = extract_resume("resume.pdf")

    jobs = scrape_jobs(
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

    matches.sort(key=lambda job: job["match_score"], reverse=True)

    for job in matches:
        print(job["title"], job["company"], job["match_score"])


if __name__ == "__main__":
    main()
