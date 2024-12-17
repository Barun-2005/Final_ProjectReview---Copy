from flask import Flask, request, jsonify, render_template
import os
import subprocess
import pdfplumber
import tempfile
from flask_cors import CORS
import logging
from concurrent.futures import ThreadPoolExecutor
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@app.route("/")
def index():
    return render_template("index.html")

@app.after_request
def add_cors_headers(response):
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
    })
    return response

def check_ollama_installed():
    result = subprocess.run(
        ["where" if os.name == "nt" else "which", "ollama"], 
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logging.error("Ollama is not installed.")
        raise RuntimeError("Ollama is not installed or not in the PATH.")

def extract_text_from_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
            logging.info(f"Extracted text length: {len(text)}")
            return clean_text(text)
    except Exception as e:
        logging.error(f"Error extracting PDF: {e}")
        raise RuntimeError("Failed to read the PDF file. Ensure it contains readable text.")

def clean_text(text):
    text = text.replace('\x00', '')
    return text.encode("utf-8", errors="replace").decode("utf-8").strip()

def chunk_text(text, max_length=2000):
    words = text.split()
    chunks, current_chunk = [], []

    for word in words:
        if sum(len(w) + 1 for w in current_chunk) + len(word) + 1 <= max_length:
            current_chunk.append(word)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def process_with_parallelism(function, inputs):
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(function, inputs))
    return results

def summarize_chunk(chunk):
    prompt = json.dumps({
        "content": f"Summarize the following text into structured paragraphs:",
        "chunk": chunk
    })

    result = subprocess.run(
        ["ollama", "run", "llama3.2:latest"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        logging.error(f"Ollama error (stderr): {result.stderr.strip()}")
        raise RuntimeError("Ollama error during summarization.")
    return result.stdout.strip()

def summarize_text_with_ollama(text, chunk_size=2000):
    check_ollama_installed()
    chunks = chunk_text(text, chunk_size)
    if not chunks:
        raise RuntimeError("No valid text chunks found for summarization.")
    summaries = process_with_parallelism(summarize_chunk, chunks)
    summary = "\n\n".join(summaries)
    logging.info("Summary generated successfully.")
    return summary

def generate_quiz_chunk(chunk, num_questions):
    prompt = json.dumps({
        "content": (
            f"Generate {num_questions} multiple-choice questions (MCQs) based on the following text. "
            f"Return the questions and answers in the format:\n"
            f'1. Question\nA. Option 1\nB. Option 2\nC. Option 3\nD. Option 4\nAnswer: Correct Option\n\n'
            f"Ensure clarity and relevance to the given content."
        ),
        "chunk": chunk
    })

    result = subprocess.run(
        ["ollama", "run", "llama3.2:latest"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        logging.error(f"Ollama error (stderr): {result.stderr.strip()}")
        raise RuntimeError(f"Ollama error: {result.stderr.strip()}")

    return result.stdout.strip()

    # Dynamically distribute questions across chunks
def distribute_questions_across_chunks(total_questions, num_chunks):
    """
    Distribute total_questions across num_chunks as evenly as possible.
    Returns a list with the number of questions for each chunk.
    """
    base_questions = total_questions // num_chunks
    remainder = total_questions % num_chunks

    # Distribute the base count and the remainder
    question_distribution = [base_questions] * num_chunks
    for i in range(remainder):
        question_distribution[i] += 1

    return question_distribution


def save_summary_to_pdf(summary, output_path):
    """
    Saves the summary text into a PDF file.
    """
    try:
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        lines = summary.split("\n")

        y = height - 40  # Start from the top of the page
        for line in lines:
            if y < 40:  # Create a new page if near the bottom
                c.showPage()
                y = height - 40
            c.drawString(40, y, line[:90])  # Truncate long lines
            y -= 15  # Move to the next line

        c.save()
        logging.info(f"Summary saved to PDF at: {output_path}")
    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        raise RuntimeError("Failed to create summary PDF.")

@app.route('/generate-quiz', methods=['POST'])
def generate_quiz():
    try:
        data = request.get_json()
        
        if not data or "num_questions" not in data:
            return jsonify({"error": "Please provide 'num_questions' in the request body."}), 400
        
        num_questions = int(data["num_questions"])
        topic = data.get("topic", "general knowledge")
        
        # Prompt template for quiz generation without text input
        prompt = json.dumps({
            "content": (
                f"Generate {num_questions} multiple-choice questions (MCQs) on the topic '{topic}'. "
                f"Ensure each question has 4 options labeled A, B, C, and D, and provide the correct answer after each question. "
                f"Format:\n1. Question\nA. Option 1\nB. Option 2\nC. Option 3\nD. Option 4\nAnswer: Correct Option\n\n"
            )
        })

        logging.info(f"Generating {num_questions} questions on the topic '{topic}'.")

        # Execute Ollama process
        result = subprocess.run(
            ["ollama", "run", "llama3.2:latest"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if result.returncode != 0:
            logging.error(f"Ollama error: {result.stderr.strip()}")
            raise RuntimeError(f"Ollama error: {result.stderr.strip()}")

        quiz_output = result.stdout.strip()
        logging.info("Quiz generation successful.")
        return jsonify({
            "quiz": quiz_output
        })

    except RuntimeError as e:
        logging.error(f"Runtime error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {e}"}), 500

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.mimetype not in ['application/pdf']:
            return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

        num_questions = int(request.form.get("num_questions", 10))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name

        try:
            # Extract and clean text from the PDF
            text = extract_text_from_pdf(temp_path)
            if not text.strip():
                raise RuntimeError("The PDF file is empty or contains non-extractable text.")
            logging.info("PDF text extraction completed successfully.")
            
            # Summarize the extracted text
            summary = summarize_text_with_ollama(text)
            logging.info("Generated Summary:")
            logging.info(summary)
            
            # Save summary to PDF
            summary_pdf_path = os.path.join(tempfile.gettempdir(), "summary_output.pdf")
            save_summary_to_pdf(summary, summary_pdf_path)
            
            # Split the summary into chunks for quiz generation
            chunks = chunk_text(summary, 2000)  # 2000-character chunks
            num_chunks = len(chunks)
            logging.info(f"Text split into {num_chunks} chunks for quiz generation.")

            # Dynamically calculate questions per chunk
            question_distribution = distribute_questions_across_chunks(num_questions, num_chunks)
            logging.info(f"Question distribution across chunks: {question_distribution}")

            # Generate quizzes for each chunk in parallel
            def generate_quiz_for_chunk(chunk, num_questions):
                return generate_quiz_chunk(chunk, num_questions)

            # Generate the quiz outputs dynamically for each chunk
            quiz_outputs = process_with_parallelism(
                lambda args: generate_quiz_for_chunk(args[0], args[1]),
                zip(chunks, question_distribution)
            )

            # Combine all quiz outputs
            combined_quiz = "\n\n".join(quiz_outputs)
            logging.info("All quiz chunks generated successfully.")
        finally:
            os.remove(temp_path)

        return jsonify({
            "summary": summary,
            "quiz": combined_quiz,
            "summary_pdf_path": summary_pdf_path  # Provide the path to the generated PDF
        })

    except RuntimeError as e:
        logging.error(f"Runtime error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {e}"}), 500

@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    """
    Endpoint to process submitted quiz answers, compare with correct answers, and return the score.
    Displays correct answers for all incorrect responses.
    """
    try:
        data = request.get_json()

        if not data or "quiz" not in data or "answers" not in data:
            return jsonify({"error": "Please provide 'quiz' (questions with correct answers) and 'answers' (user responses)."}), 400

        quiz_text = data["quiz"]
        user_answers = data["answers"]

        # Parse the quiz to extract correct answers
        correct_answers = {}
        current_question = 1
        for line in quiz_text.split("\n"):
            line = line.strip()
            if line.startswith("Answer:"):
                correct_option = line.split(":")[1].strip()
                correct_answers[str(current_question)] = correct_option
                current_question += 1

        # Validate user answers and calculate the score
        total_questions = len(correct_answers)
        correct_count = 0
        feedback = {}

        for question_num, user_answer in user_answers.items():
            correct_answer = correct_answers.get(question_num)
            if correct_answer:
                if user_answer.strip().upper() == correct_answer.upper():
                    correct_count += 1
                    feedback[question_num] = {"result": "Correct"}
                else:
                    feedback[question_num] = {
                        "result": "Incorrect",
                        "your_answer": user_answer.strip().upper(),
                        "correct_answer": correct_answer
                    }

        # Calculate the score percentage
        score_percentage = (correct_count / total_questions) * 100

        return jsonify({
            "score": f"{correct_count}/{total_questions}",
            "percentage": f"{score_percentage:.2f}%",
            "feedback": feedback
        })

    except Exception as e:
        logging.error(f"Error processing quiz submission: {e}")
        return jsonify({"error": "Failed to process quiz submission.", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
