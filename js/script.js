console.log("SCRIPT.JS LOADED");

const resumeUpload = document.getElementById("resume-upload");

resumeUpload.addEventListener("change", async function () {
    const file = resumeUpload.files[0];

    if (!file) {
        return;
    }

    const formData = new FormData();
    formData.append("resume", file);

    try {
        const response = await fetch("https://vigilant-space-happiness-wrvqgr9xjvpp2pgq-5001.app.github.dev/", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        console.log(data);

        if (data.error) {
            alert("Error: " + data.error);
        } else {
            alert("Resume uploaded successfully!");
            console.log("Resume text:", data.resume_text);
        }

    } catch (error) {
        console.error(error.message);
        alert("Something went wrong uploading your resume.");
    }
});

