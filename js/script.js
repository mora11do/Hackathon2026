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
        const response = await fetch("https://vigilant-space-happiness-wrvqgr9xjvpp2pgq-5001.app.github.dev/upload", {
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


<script>
  document.querySelectorAll("a.service").forEach(function (card) {
    card.addEventListener("click", function (e) {
      // let ctrl/cmd/shift-click (open in new tab) behave normally
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      // skip the animation for people who prefer reduced motion
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      e.preventDefault();
      card.classList.add("selected");
      setTimeout(function () {
        window.location.href = card.href;
      }, 300);
    });
  });
</script>
