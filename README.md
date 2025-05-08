# Job Application Helper

## Overview

The Job Application Helper is a desktop application designed to assist users in tailoring their resumes and generating content for job applications. It leverages AI agents (powered by CrewAI and NVIDIA NIM endpoints) to analyze resumes against job descriptions, suggest modifications, and generate relevant text like essay answers.

## Features

* **Resume Upload:** Supports uploading resumes in `.pdf` and `.docx` formats.
* **Job Description Input:** Allows pasting job descriptions for analysis.
* **AI-Powered Analysis:** Compares the uploaded resume against the job description to identify strengths, gaps, and areas for improvement.
* **AI-Powered Resume Modification:** Generates a modified version of the resume tailored to the specific job description, incorporating relevant keywords and structuring bullet points for impact (using APR/STAR principles in the Professional Experience section).
* **Formatted Resume Saving:** Saves the AI-modified resume as a formatted `.docx` file, applying styles based on content markers.
* **Interactive Chat:** Allows users to discuss the analysis and modifications with an AI agent and request further specific changes.
* **Essay Generation:** Helps draft answers to common job application essay questions based on the resume and job description context.
* **Logging:** Records application events and potential errors in `job_app_helper.log`.

## Technology Stack

* **Core Language:** Python 3.x
* **GUI:** Tkinter (potentially with `ttkthemes` if installed)
* **AI Framework:** CrewAI
* **LLM Integration:** `langchain-nvidia-ai-endpoints` (using NVIDIA NIM)
* **File Parsing:** `python-docx` (for `.docx`), `pypdf` (for `.pdf`)
* **Configuration:** `python-dotenv`
* **Document Generation:** `python-docx`

## Setup and Installation

1.  **Prerequisites:**
    * Python 3.8 or higher installed.
    * `pip` (Python package installer).

2.  **Get the Code:**
    * Ensure you have all the project files (`main.py`, `job_application_agent.py`, `utils.py`, `config.py`, `requirements.txt`, etc.) in a single directory.

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `playwright` is listed but might require an additional step (`playwright install`) if browser automation features are implemented later.*

5.  **API Key Setup:**
    * You need an API key for the NVIDIA AI endpoints (NIM).
    * Create a file named `.env` in the project's root directory (the same directory as `main.py`).
    * Add the following line to the `.env` file, replacing `"YOUR_ACTUAL_NVIDIA_API_KEY"` with your actual key:
        ```
        NVIDIA_NIM_API_KEY="YOUR_ACTUAL_NVIDIA_API_KEY"
        ```
    * Ensure the file is saved correctly and there are no extra spaces.

## Usage

1.  **Run the Application:**
    * Make sure your virtual environment is activated (if you created one).
    * Navigate to the project directory in your terminal.
    * Run the main script:
        ```bash
        python main.py
        ```

2.  **GUI Interface:**
    * **Original Resume:** Upload your resume using the "Upload Resume" button. The parsed text will appear here.
    * **Job Description:** Paste the full job description into this text area.
    * **Modified Resume / Analysis:** This area will display the AI's analysis and the suggested modified resume text (including formatting markers) after running the "Analyze & Suggest Modifications" action.
    * **Action Buttons:**
        * `Analyze & Suggest Modifications`: Starts the core AI process. Requires a resume and job description.
        * `Save Formatted Resume`: Saves the content from the "Modified Resume / Analysis" area as a formatted `.docx` file. Enabled only after a modification is generated.
        * `Discuss/Modify via Chat`: Opens a chat window to ask questions about the results or request specific changes to the modified resume. Enabled after analysis/modification.
        * `Generate Essay Answer`: Opens a window to generate essay answers based on the resume, JD, and a specific question. Requires an uploaded resume.

3.  **Typical Workflow:**
    * Upload your resume.
    * Paste the target job description.
    * Click "Analyze & Suggest Modifications". Wait for the process to complete.
    * Review the analysis and the modified resume text in the bottom-left panel.
    * *(Optional)* Click "Discuss/Modify via Chat" to ask for explanations or further refinements. If you request modifications in the chat, the main window's "Modified Resume / Analysis" area will update.
    * Click "Save Formatted Resume" to save the latest modified version as a `.docx` file.
    * *(Optional)* Click "Generate Essay Answer" to get help with application questions.

## File Structure

```
job-application-helper/
├── .env                     # Environment variables file
├── .env.example             # Sample environment configuration
├── main.py                  # Main application script (Tkinter GUI)
├── job_application_agent.py # CrewAI agent setup and tasks
├── utils.py                 # Utility functions (resume parsing, etc.)
├── config.py                # Configuration loading (API keys)
└── requirements.txt         # Python dependencies
```

## Logging

* The application logs information, warnings, and errors to the console and to a file named `job_app_helper.log` in the same directory.
* Check this log file for detailed error messages if you encounter issues.

## Future Enhancements

* Implement form-filling capabilities using `playwright`.
* Add support for more resume file types.
* Allow saving user preferences or multiple profiles.
* Improve error handling and user feedback in the GUI.

## Contributing

Contributions are welcome! Please follow standard fork-and-pull-request procedures. Ensure code includes comments and adheres to basic Python style guidelines.

## License

(Optional: Add license information here, e.g., MIT License)

