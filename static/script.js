// PDF Form Submission and Quiz Generation
document.getElementById("pdf-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("pdf-file");
    const numQuestions = document.getElementById("num-questions").value;

    const loader = document.getElementById("loader");
    const output = document.getElementById("output");
    const summaryDiv = document.getElementById("summary");
    const quizDiv = document.getElementById("quiz");
    const errorDiv = document.getElementById("error");

    loader.classList.remove("hidden");
    output.classList.add("hidden");
    errorDiv.classList.add("hidden");

    const file = fileInput.files[0];
    if (!file) {
        displayError("Please select a PDF file.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("num_questions", numQuestions);

    try {
        const response = await fetch("/process-pdf", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            // Display summary
            summaryDiv.textContent = data.summary || "No summary provided.";

            // Parse raw quiz text
            const parsedQuiz = parseQuizText(data.quiz || "");
            quizDiv.innerHTML = generateQuizHTML(parsedQuiz);

            output.classList.remove("hidden");
        } else {
            displayError(data.error || "Failed to process the PDF.");
        }
    } catch (error) {
        displayError("An error occurred while communicating with the server.");
    } finally {
        loader.classList.add("hidden");
    }
});

// Display error messages
function displayError(message) {
    const errorDiv = document.getElementById("error");
    errorDiv.textContent = message;
    errorDiv.classList.remove("hidden");
    document.getElementById("loader").classList.add("hidden");
}

// Parse Quiz Text into Structured Format (MCQ-only)
function parseQuizText(rawQuizText) {
    console.log("Raw Quiz Text:", rawQuizText);

    const questions = [];
    const rawLines = rawQuizText.split("\n").filter(line => line.trim() !== "");

    let currentQuestion = null;

    rawLines.forEach((line) => {
        if (/^\d+\./.test(line)) {
            // New question found
            if (currentQuestion) {
                questions.push(currentQuestion);
            }
            currentQuestion = { 
                text: line.replace(/^\d+\.\s*/, "").trim(), 
                options: [], 
                answer: "" 
            };
        } else if (/^[A-D]\.\s/.test(line)) {
            // MCQ option detected
            currentQuestion?.options.push(line.replace(/^[A-D]\.\s*/, "").trim());
        } else if (/^Answer:\s*/.test(line)) {
            // Remove prefix like "B. " and store the clean answer
            const rawAnswer = line.replace(/^Answer:\s*/, "").trim();
            const cleanAnswer = rawAnswer.replace(/^[A-D]\.\s*/, "").trim();
            currentQuestion.answer = cleanAnswer;
        }        
    });

    // Add the last question
    if (currentQuestion) {
        questions.push(currentQuestion);
    }

    console.log("Parsed Questions Array:", questions);
    return questions;
}

// Generate Quiz HTML for MCQs
function generateQuizHTML(quizData) {
    if (!quizData || quizData.length === 0) {
        return "<p>No quiz questions available.</p>";
    }

    let quizHTML = "";
    quizData.forEach((question, idx) => {
        quizHTML += `<div class="quiz-question" data-answer="${question.answer}">
            <p><strong>${idx + 1}. ${question.text}</strong></p>`;

            question.options.forEach((option) => {
                const cleanOption = option.replace(/^[A-D]\.\s*/, "").trim(); // Remove prefixes like "A. "
                quizHTML += `
                    <label>
                        <input type="radio" name="question-${idx}" value="${cleanOption}">
                        ${option} <!-- Display the original option with A., B., etc. -->
                    </label><br>`;
            });            

        quizHTML += `</div>`;
    });

    quizHTML += `<button type="button" id="submit-quiz">Submit Quiz</button>`;
    return quizHTML;
}

// Start Quiz Timer
function startTimer(duration, display, onTimeUp) {
    let timer = duration;
    const interval = setInterval(() => {
        const minutes = Math.floor(timer / 60);
        const seconds = timer % 60;

        display.textContent = `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
        if (--timer < 0) {
            clearInterval(interval);
            onTimeUp(); // Trigger when time is up
        }
    }, 1000);
}

// Handle Quiz Submission (Updated for Auto-Submit)
document.addEventListener("click", (e) => {
    if (e.target && e.target.id === "submit-quiz") {
        submitQuiz();
    }
});

function submitQuiz() {
    const questionsDivs = document.querySelectorAll(".quiz-question");
    let score = 0;

    const feedbackData = {};
    questionsDivs.forEach((questionDiv, idx) => {
        const selectedOption = questionDiv.querySelector("input[type='radio']:checked");
        const correctAnswer = questionDiv.dataset.answer;

        const questionNum = idx + 1;
        feedbackData[questionNum] = {
            your_answer: selectedOption ? selectedOption.value.trim() : "No answer selected",
            correct_answer: correctAnswer.trim(),
            result: selectedOption && selectedOption.value.trim() === correctAnswer.trim() ? "Correct" : "Incorrect",
        };

        if (feedbackData[questionNum].result === "Correct") {
            score++;
            questionDiv.style.backgroundColor = "#d4edda"; // Green for correct
        } else {
            questionDiv.style.backgroundColor = "#f8d7da"; // Red for incorrect
        }
    });

    const totalQuestions = questionsDivs.length;
    const percentage = ((score / totalQuestions) * 100).toFixed(2);

    // Display Feedback
    displayQuizFeedback({
        score: `${score}/${totalQuestions}`,
        percentage: `${percentage}%`,
        feedback: feedbackData,
    });
}

function displayQuizFeedback(result) {
    const feedbackDiv = document.getElementById("feedback");
    const feedbackContainer = document.getElementById("quiz-feedback");

    feedbackDiv.innerHTML = ""; // Clear previous feedback
    let feedbackHTML = `<h3>Quiz Results</h3>
                        <p><strong>Score:</strong> ${result.score} (${result.percentage})</p>`;

    // Generate feedback for each question
    Object.entries(result.feedback).forEach(([questionNum, feedback]) => {
        feedbackHTML += `<div class="feedback-item">
            <p><strong>Question ${questionNum}:</strong> ${feedback.result}</p>`;

        if (feedback.result === "Incorrect") {
            feedbackHTML += `<p>Your Answer: <span class="wrong-answer">${feedback.your_answer}</span></p>
                             <p>Correct Answer: <span class="correct-answer">${feedback.correct_answer}</span></p>`;
        } else {
            feedbackHTML += `<p>Your Answer: <span class="correct-answer">${feedback.your_answer}</span></p>`;
        }

        feedbackHTML += "</div>";
    });

    feedbackDiv.innerHTML = feedbackHTML;
    feedbackContainer.classList.remove("hidden");
}

// Initialize Timer on Quiz Start
document.getElementById("pdf-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const timerDisplay = document.getElementById("timer");
    const timerContainer = document.getElementById("timer-display");
    const quizTimerInput = document.getElementById("quiz-timer").value;

    // Convert minutes to seconds
    const duration = parseInt(quizTimerInput, 10) * 60;

    // Show timer and start countdown
    timerContainer.classList.remove("hidden");
    startTimer(duration, timerDisplay, submitQuiz);
});

// Display Quiz Feedback (Updated for Better Styling)
function displayQuizFeedback(result) {
    const feedbackDiv = document.getElementById("feedback");
    const feedbackContainer = document.getElementById("quiz-feedback");

    feedbackDiv.innerHTML = ""; // Clear previous feedback
    let feedbackHTML = `<p><strong>Score:</strong> ${result.score} (${result.percentage})</p>`;

    // Generate feedback for each question
    Object.entries(result.feedback).forEach(([questionNum, feedback]) => {
        feedbackHTML += `<div class="feedback-item">
            <p><strong>Question ${questionNum}:</strong> ${feedback.result}</p>`;

        if (feedback.result === "Incorrect") {
            feedbackHTML += `<p>Your Answer: <span class="wrong-answer">${feedback.your_answer}</span></p>
                             <p>Correct Answer: <span class="correct-answer">${feedback.correct_answer}</span></p>`;
        } else {
            feedbackHTML += `<p>Your Answer: <span class="correct-answer">${feedback.your_answer}</span></p>`;
        }

        feedbackHTML += "</div>";
    });

    feedbackDiv.innerHTML = feedbackHTML;
    feedbackContainer.classList.remove("hidden");
}

//Download Summary 
document.getElementById("download-summary").addEventListener("click", () => {
    const { jsPDF } = window.jspdf; // Ensure jsPDF is correctly accessed
    const summary = document.getElementById("summary").textContent || "No summary available.";
    const title = "Summary and Quiz";
    const date = new Date().toLocaleDateString();

    const pdf = new jsPDF();
    const marginLeft = 10; // Left margin
    const marginTop = 20;  // Top margin for text
    const pageHeight = pdf.internal.pageSize.height; // Page height
    const lineHeight = 10; // Line height
    let y = marginTop; // Vertical cursor position

    // Title and Date
    pdf.setFontSize(14);
    pdf.text(`Title: ${title}`, marginLeft, y);
    y += lineHeight;
    pdf.setFontSize(10);
    pdf.text(`Date: ${date}`, marginLeft, y);
    y += lineHeight;

    // Split summary text into manageable lines
    const summaryLines = pdf.splitTextToSize(summary, 180); // 180 = max text width on page

    pdf.setFontSize(12); // Set font size for summary text

    // Render text line by line, adding pages when needed
    summaryLines.forEach((line) => {
        if (y + lineHeight > pageHeight - marginTop) {
            pdf.addPage(); // Add a new page
            y = marginTop; // Reset cursor position to top of new page
        }
        pdf.text(line, marginLeft, y);
        y += lineHeight; // Move cursor down
    });

    // Save PDF file
    pdf.save("summary_quiz.pdf");
});
