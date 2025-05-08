import os
import logging
import json # For parsing plan if needed
import re # For potentially cleaning output
from crewai import Agent, Task, Crew, Process
from langchain_nvidia_ai_endpoints import ChatNVIDIA
# Import the updated function from config.py
from config import load_api_key

# Configure logging
log = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_MODEL_NAME = "nvidia/llama-3.1-nemotron-70b-instruct" # Keep the updated model
ANALYSIS_START_MARKER = "=== ANALYSIS START ==="
ANALYSIS_END_MARKER = "=== ANALYSIS END ==="
MODIFICATION_START_MARKER = "=== MODIFIED RESUME START ==="
MODIFICATION_END_MARKER = "=== MODIFIED RESUME END ==="
ESSAY_START_MARKER = "=== ESSAY START ==="
ESSAY_END_MARKER = "=== ESSAY END ==="
# List of known bad filler patterns to strip from the beginning of the output
BAD_FILLER_PATTERNS = [
    "Thought: I now can give a great answer\n\n",
    "I now can give a great answer\n\n",
    "Thought: I now can give a great answer\n",
    "I now can give a great answer\n",
    "Okay, here is the analysis report:\n",
    "Okay, here's the modified resume:\n",
    "Here is the modified resume:\n",
    "Here's the updated resume:\n",
    "Sure, here is the resume:\n",
    "Okay, here's the analysis:\n",
    "Here is the analysis:\n",
    "Here's the analysis and modified resume:\n",
    "Okay, here's the essay:\n",
    "Here is the essay:\n",
    "Okay, ",
    "Sure, ",
    "Certainly, ",
    "Alright, ",
]
# --- NEW MARKERS FOR FORMATTING ---
FMT_NAME = "@@NAME@@"
FMT_CONTACT = "@@CONTACT@@"
FMT_HEADING = "@@HEADING@@"
FMT_SUBHEADING_COMPANY = "@@SUBHEAD_COMP@@"
FMT_SUBHEADING_TITLE = "@@SUBHEAD_TITLE@@"
FMT_SUBHEADING_PROJECT = "@@SUBHEAD_PROJ@@"
FMT_DATES = "@@DATES@@"
FMT_BULLET = "@@BULLET@@"
FMT_NORMAL = "@@NORMAL@@" # Default paragraph


# --- Load API Key ---
LOADED_API_KEY = load_api_key()
if not LOADED_API_KEY:
    log.critical("NVIDIA_NIM_API_KEY could not be loaded. Application cannot function without it.")
    raise ValueError("NVIDIA_NIM_API_KEY could not be loaded. Please check your .env file or environment variables.")
else:
    # Ensure the key is available as an environment variable for LangChain/CrewAI
    os.environ["NVIDIA_NIM_API_KEY"] = LOADED_API_KEY
    log.info("NVIDIA_NIM_API_KEY set in environment for this process.")


# --- Initialize LLM ---
try:
    # Use the API key directly from the loaded variable for clarity
    llm = ChatNVIDIA(
        model=DEFAULT_MODEL_NAME, # Use the updated model name constant
        nvidia_api_key=LOADED_API_KEY, # Pass the key explicitly
        max_tokens=2048, # Keep slightly increased
        temperature=0.5 # Keep temperature low
    )
    log.info(f"Successfully initialized ChatNVIDIA with model: {DEFAULT_MODEL_NAME}")
except Exception as e:
    log.critical(f"Failed to initialize ChatNVIDIA LLM: {e}", exc_info=True)
    # Provide a more user-friendly error message if initialization fails
    raise RuntimeError(f"Could not initialize the AI model (ChatNVIDIA). Please check API key validity, model access ({DEFAULT_MODEL_NAME}), and network connection. Error: {e}")

# --- Define Agents ---
# Resume Analyzer (no changes needed)
resume_analyzer = Agent(
    role='Resume Analyzer',
    goal='Analyze a given resume against a job description, identifying key skills, experiences, and qualifications present in the resume and highlighting gaps or areas for improvement based on the job requirements.',
    backstory=(
        "You are an expert Human Resources professional with extensive experience in recruitment "
        "and talent acquisition. You have a keen eye for detail and understand how to match candidate "
        "profiles with job requirements effectively. Your task is to provide a clear, concise analysis "
        "comparing a resume to a specific job description."
    ),
    verbose=True, allow_delegation=False, llm=llm
)

# Resume Modifier (no changes needed in definition)
"""
resume_modifier = Agent(
    role='Resume Modifier',
    goal='Refine and enhance a resume to better align with a specific job description, based on an initial analysis. Incorporate keywords and tailor descriptions to highlight relevant experiences, while maintaining accuracy and professional tone. Optionally, incorporate user feedback for further refinement.',
    backstory=(
        "You are a professional Resume Writer and Career Coach. You excel at crafting compelling narratives "
        "that showcase a candidate's strengths in the context of a target role. You receive an original resume, "
        "a job description, and an analysis of how well the resume matches. Your job is to rewrite sections "
        "of the resume or suggest specific changes to maximize its impact for the application, potentially "
        "incorporating direct feedback from the user on desired changes. You MUST add specific formatting markers to your output."
    ),
    verbose=True, allow_delegation=False, llm=llm
)
"""
"""
resume_modifier = Agent(
    role='Resume Modification Expert',
    goal='Transform resumes into targeted, achievement-focused documents that pass ATS scans and impress hiring managers',
    backstory=(
        "As a Certified Professional Resume Writer (CPRW) with 10+ years experience at top tech companies, "
        "you specialize in surgical resume enhancements. You combine ATS optimization techniques with "
        "executive-level storytelling to create resumes that get interviews. Your modifications always "
        "preserve factual accuracy while dramatically improving impact."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
    tools=[],  # Add any tools for fact verification if available
    memory=True,  # Maintain context across modifications
    max_iterations=3,  # Prevent excessive rewrites
    system_message=(
        "**Resume Modification Protocol**\n"
        "1. REQUIRED ACTIONS:\n"
        "   - Highlight 3-5 job description keywords in each relevant section (marked with **)\n"
        "   - Convert responsibilities to achievements using CAR/STAR format\n"
        "   - Add metrics to 80% of bullet points (even estimates like '~20%')\n"
        "   - Reorder sections by job priority (Skills first for tech roles)\n\n"
        "2. PRESERVATION RULES:\n"
        "   - Never remove factual information (only rephrase)\n"
        "   - Maintain all @@MARKERS@@ and formatting\n"
        "   - Keep contact info/education completely unchanged\n\n"
        "3. SAFETY CHECKS:\n"
        "   - Verify all numbers with [MUST VERIFY] tag if uncertain\n"
        "   - Flag any content needing user confirmation with [CONFIRM?]\n"
        "   - Reject requests to add unverified skills/experiences\n\n"
        "4. OUTPUT FORMAT:\n"
        "   - Return ONLY the modified resume text\n"
        "   - Bold all changes for transparency\n"
        "   - Include all original sections\n"
        "   - Never add commentary or explanations"
    ),
    examples=[  # Few-shot learning examples
        {
            "input": "Original: Managed team projects",
            "output": "**Led 5 cross-functional Agile projects (3-8 members) delivering features 25% faster**"
        },
        {
            "input": "Original: Used Python for data analysis",
            "output": "**Built Python ETL pipelines (Pandas, NumPy) that automated 15+ hours/week of manual reporting**"
        }
    ]
)
"""

resume_modifier = Agent(
    role='Impact-Driven Resume Strategist',
    goal='Enhance resume bullet points with measurable impact while maintaining authenticity and relevance to the job description',
    backstory=(
        "As a former Fortune 500 HR Tech Specialist turned resume engineer, you combine hiring manager psychology "
        "with data-driven impact statements. You specialize in transforming generic responsibilities into "
        "quantified achievements that demonstrate clear value."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
    system_message=(
        "**Resume Rewriting Protocol v3.0 - Impact Focus**\n\n"
        "1. BULLET POINT TRANSFORMATION RULES:\n"
        "   - Every modified bullet MUST follow the 'X-Y-Z' structure:\n"
        "     * X: Action taken (specific what)\n"
        "     * Y: Method/approach used (optional)\n"
        "     * Z: Measurable outcome (required)\n"
        "   - Example: 'Optimized API response times (Y) by implementing caching (X), reducing latency by 40% (Z)'\n\n"
        "2. METRIC INTEGRATION STANDARDS:\n"
        "   - Prefer real metrics from the original resume\n"
        "   - For estimated metrics, use conservative ranges and mark with [~]\n"
        "   - Never invent metrics that can't be reasonably inferred\n"
        "   - Acceptable metric types:\n"
        "     * Percentage improvements (e.g., 'increased efficiency by 25%')\n"
        "     * Time savings (e.g., 'reduced processing time by 3 hours weekly')\n"
        "     * Scale metrics (e.g., 'managed 15+ team members')\n"
        "     * Business impact (e.g., 'generated $50K in annual savings')\n\n"
        "3. SECTION-SPECIFIC RULES:\n"
        "   - PROFESSIONAL EXPERIENCE:\n"
        "     * Transform 1-2 most relevant bullets per position to impact statements\n"
        "     * May add 1-2 new bullets ONLY if critical for job requirements\n"
        "     * Never add fluff phrases like 'showcasing skills'\n"
        "   - PROJECT EXPERIENCE:\n"
        "     * Only modify keywords to better match job description\n"
        "     * Never add new bullets\n"
        "     * Preserve original structure and content\n\n"
        "4. QUALITY CONTROL:\n"
        "   - All new content gets [IMPACT VERIFIED] tag\n"
        "   - Questionable metrics marked [ESTIMATE]\n"
        "   - Maintain original @@MARKERS@@ strictly\n"
        "   - Bold all modifications for transparency"
    ),
    examples=[
        {
            "input": ("Job requires 'process optimization'. Original: Improved reporting system",
                     "Finance experience"),
            "output": "**Reduced monthly reporting time by 30% (Z) by automating Excel workflows with Python (X), enabling faster decision-making (Y)** [IMPACT VERIFIED]"
        },
        {
            "input": ("Job requires 'team leadership'. Original: Managed project team",
                     "Software development"),
            "output": "**Led 6-member agile team (X) to deliver 3 full-stack features 2 weeks ahead of schedule (Z) through improved sprint planning (Y)** [ESTIMATE]"
        },
        {
            "input": "Job requires 'AWS'. Original: Cloud administration",
            "output": "**Managed AWS infrastructure (EC2, S3) supporting 500+ daily users with 99.9% uptime**"
        }
    ]
)

# Essay Writer (no changes needed)
essay_writer = Agent(
    role='Job Application Essay Writer',
    goal='Generate compelling short essay answers for job application questions based on the candidate\'s resume, the job description, and specific user instructions or prompts. If the resume lacks details, formulate relevant questions to ask the user or generate plausible examples based on the indicated experience level.',
    backstory=(
        "You are a skilled writer specializing in professional communication and application materials. "
        "You can synthesize information from a resume and job description to draft thoughtful responses "
        "to common application questions (e.g., behavioral questions, situational questions). "
        "You understand the importance of aligning responses with the candidate's likely experience and the target role. "
        "If needed, you can prompt the user for specific examples or generate suitable, hypothetical scenarios."
    ),
    verbose=True, allow_delegation=False, llm=llm
)

# Resume Explainer (no changes needed)
resume_explainer_agent = Agent(
    role='Resume Discussion Agent',
    goal=(
        "Engage in a conversation with the user about their resume, the job description, the analysis performed, and the modifications suggested. "
        "Answer user questions clearly and concisely based on the provided context. "
        "Explain *why* certain changes were made, referencing the job description and analysis. "
        "CRITICAL: Your primary function is EXPLANATION ONLY. Do NOT offer to make changes or modify the resume text in your response, even if asked. Stick strictly to explaining the existing information."
    ),
    backstory=(
        "You are a helpful AI assistant designed to discuss resume improvements. You have access to the original resume, the target job description, "
        "an analysis comparing the two, and the latest modified version of the resume. Your primary function is to answer the user's questions about this information, "
        "such as 'What changes did you make?', 'Why was this section added?', 'Does my resume match requirement X?'. "
        "Maintain a helpful and conversational tone. You DO NOT perform modifications; another agent handles that separately based on user requests in the chat."
    ),
    verbose=True,
    allow_delegation=False,
    llm=llm
)


# --- Define Tasks ---

# Analysis Task (no changes needed)
def create_analysis_task(resume_content, job_description):
    """Creates the task for the Resume Analyzer agent."""
    return Task(
        description=(
            f"1. Carefully read the provided resume:\n```\n{resume_content}\n```\n"
            f"2. Carefully read the provided job description:\n```\n{job_description}\n```\n"
            f"3. Identify the key skills, qualifications, and experiences mentioned in the job description.\n"
            f"4. Compare the resume against these requirements.\n"
            f"5. Summarize the strengths of the resume in relation to the job.\n"
            f"6. Identify specific gaps, missing keywords, or areas where the resume could be tailored "
            f"   more effectively for this specific job description.\n"
            f"7. Present your analysis clearly, focusing on actionable insights for improvement.\n"
            f"8. **ABSOLUTELY CRITICAL**: Your response MUST start *immediately* with the start marker '{ANALYSIS_START_MARKER}' on the first line, followed by the analysis content, and end *immediately* with the end marker '{ANALYSIS_END_MARKER}' on the last line. "
            f"   There MUST be NO text, characters, spaces, or newlines before the start marker or after the end marker. "
            f"   Do NOT include *any* conversational phrases, thoughts, greetings, apologies, or explanations outside the markers. The markers and the analysis between them must be the *entirety* of your response."
        ),
        expected_output=(
            f"The detailed analysis report enclosed in markers. The entire response MUST start exactly with '{ANALYSIS_START_MARKER}' and end exactly with '{ANALYSIS_END_MARKER}'.\n"
            f"{ANALYSIS_START_MARKER}\n"
            "[Detailed analysis report content here]\n"
            f"{ANALYSIS_END_MARKER}"
        ),
        agent=resume_analyzer, human_input=False
    )

# *** MODIFIED TASK FOR RESUME MODIFIER ***
def create_modification_task(resume_content, job_description, analysis_context=None, user_feedback=None):
    """Creates the task for the Resume Modifier agent with formatting markers."""
    description = (
        f"You are a Resume Modifier AI. Your ONLY task is to rewrite the provided resume based on the context, adding specific formatting markers.\n"
        f"1. Original resume:\n```\n{resume_content}\n```\n"
        f"2. Target job description:\n```\n{job_description}\n```\n"
    )
    if analysis_context: description += f"3. Consider this analysis:\n```\n{analysis_context}\n```\n"
    if user_feedback: description += f"4. Incorporate these specific user instructions for modification:\n```\n{user_feedback}\n```\n"
    else: description += "4. No specific user instructions provided this time. Modify based on analysis and JD alignment.\n"
    description += (
        f"5. Modify the original resume text to better align with the job description, incorporating keywords and "
        f"   highlighting relevant experiences based on the analysis and user instructions (if any).\n"
        f"6. Focus on enhancing clarity, impact, and relevance.\n"
        f"7. Ensure the tone remains professional and the information accurate (do not invent experiences).\n"
        f"8. **CRITICAL FORMATTING MARKERS**: As you generate the modified resume text, you MUST prefix each distinct element or paragraph with ONE of the following markers on the SAME line, followed by a single space, then the text. Use the most appropriate marker for each line/paragraph:\n"
        f"   - `{FMT_NAME}`: Candidate's Full Name (e.g., `{FMT_NAME} John Doe`)\n"
        f"   - `{FMT_CONTACT}`: Contact information line(s) (email, phone, LinkedIn, portfolio) (e.g., `{FMT_CONTACT} john.doe@email.com | linkedin.com/in/johndoe`)\n"
        f"   - `{FMT_HEADING}`: Major section headings (e.g., EDUCATION, PROJECTS, PROFESSIONAL EXPERIENCE, TECHNICAL SKILLS, CONFERENCE & CERTIFICATION) (e.g., `{FMT_HEADING} EDUCATION`)\n"
        f"   - `{FMT_SUBHEADING_COMPANY}`: Company Name within experience section (e.g., `{FMT_SUBHEADING_COMPANY} Acme Corporation`)\n"
        f"   - `{FMT_SUBHEADING_TITLE}`: Job Title within experience section (e.g., `{FMT_SUBHEADING_TITLE} Software Engineer`)\n"
        f"   - `{FMT_SUBHEADING_PROJECT}`: Project Title within projects section (e.g., `{FMT_SUBHEADING_PROJECT} Resume Analyzer Bot`)\n"
        f"   - `{FMT_DATES}`: Dates associated with education or experience (e.g., `{FMT_DATES} Sep 2021 – Mar 2024`)\n"
        f"   - `{FMT_BULLET}`: Bullet point description under experience or projects (MUST start with a bullet character like '*' or '-') (e.g., `{FMT_BULLET} - Developed cool features using Python.`)\n"
        f"   - `{FMT_NORMAL}`: Any other paragraph or line of text not covered above (e.g., degree name, skills list items not part of bullets). (e.g., `{FMT_NORMAL} MS in Business Analytics`)\n"
        f"   **Each line or paragraph MUST start with exactly one of these markers.**\n"
        f"9. **ABSOLUTELY CRITICAL OUTPUT ENCLOSURE**: Your *entire* response, including the text with the formatting markers, MUST be enclosed *exactly* like this: {MODIFICATION_START_MARKER}\\n[Formatted text with markers here]\\n{MODIFICATION_END_MARKER}. "
        f"   There MUST be NO text, characters, spaces, or newlines before the start marker or after the end marker. "
        f"   Do NOT include *any* conversational phrases, thoughts, greetings, apologies, or explanations outside the main markers."
    )
    return Task(
        description=description,
        expected_output=(
            f"The full text of the modified resume, with each line/paragraph prefixed by a formatting marker (e.g., {FMT_HEADING}, {FMT_BULLET}), enclosed within the main start/end markers. The entire response MUST start exactly with '{MODIFICATION_START_MARKER}' and end exactly with '{MODIFICATION_END_MARKER}'.\n"
            f"{MODIFICATION_START_MARKER}\n"
            f"{FMT_NAME} John Doe\n"
            f"{FMT_CONTACT} john.doe@email.com | linkedin.com/in/johndoe\n"
            f"{FMT_HEADING} EDUCATION\n"
            f"{FMT_NORMAL} University Name | Degree Name\n"
            f"{FMT_DATES} Aug 2020 - May 2024\n"
            f"{FMT_HEADING} PROFESSIONAL EXPERIENCE\n"
            f"{FMT_SUBHEADING_COMPANY} Example Corp\n"
            f"{FMT_SUBHEADING_TITLE} Software Engineer\n"
            f"{FMT_DATES} Jan 2023 - Present\n"
            f"{FMT_BULLET} - Did something important.\n"
            f"{FMT_BULLET} - Achieved another thing.\n"
            f"{MODIFICATION_END_MARKER}"
        ),
        agent=resume_modifier, human_input=False
    )


# Essay Task (no changes needed)
def create_essay_task(resume_content, job_description, essay_question, user_input=None, experience_level=None):
    """Creates the task for the Essay Writer agent."""
    description = (
        f"You are an Essay Writer AI. Your ONLY task is to EITHER write an essay answering the question OR ask a clarifying question.\n"
        f"Essay Question: '{essay_question}'\n\n"
        f"Context:\n"
        f"1. Resume:\n```\n{resume_content}\n```\n"
        f"2. Job Description:\n```\n{job_description}\n```\n"
    )
    if user_input: description += f"3. User Input:\n```\n{user_input}\n```\nBase the essay primarily on this user input.\n"
    else:
        description += "3. No user input. Base on resume."
        if experience_level: description += f" Assume {experience_level} years experience.\n"
        description += ("If resume lacks specifics, EITHER ask 'QUESTION: [Your question here]' OR generate a plausible example based on the resume and JD.\n")
    description += (
        f"Instructions:\n"
        f"- Write a concise, professional essay (1-3 paragraphs) directly answering '{essay_question}'.\n"
        f"- Align the answer with the candidate's profile and the target role.\n"
        f"- **CRITICAL OUTPUT FORMAT 1 (Essay):** If writing the essay, your *entire* response MUST start *immediately* with the start marker '{ESSAY_START_MARKER}', followed by the essay text, and end *immediately* with the end marker '{ESSAY_END_MARKER}'. NO other text, characters, spaces, or newlines before the start marker or after the end marker.\n"
        f"- **CRITICAL OUTPUT FORMAT 2 (Question):** If asking a question, your *entire* output MUST be *ONLY* the question prefixed *exactly* like this: 'QUESTION: [Your question here]'. NO other text before or after.\n"
        f"- ABSOLUTELY NO other text, greetings, explanations, apologies, or conversation outside the markers or the 'QUESTION: ' prefix.\n"
    )
    return Task(
        description=description,
        expected_output=(
            "EITHER the essay text enclosed in markers OR a question prefixed with 'QUESTION: '. Nothing else.\n"
            f"Example 1: {ESSAY_START_MARKER}\n[Essay text here]\n{ESSAY_END_MARKER}\n"
            "Example 2: QUESTION: [Your question here]"
        ),
        agent=essay_writer, human_input=False
    )

# Explanation Task (no changes needed)
def create_explanation_task(user_query, original_resume, job_description, analysis, modified_resume):
    """Creates the task for the Resume Explainer Agent."""
    # Note: Explanation agent is allowed to be more conversational, no strict markers needed,
    # but still needs to avoid offering modifications.
    return Task(
        description=(
            f"The user is asking about their resume and the changes made. \n"
            f"User's Query: '{user_query}'\n\n"
            f"Use the following context to answer the user's query:\n"
            f"1. Original Resume:\n```\n{original_resume}\n```\n"
            f"2. Job Description:\n```\n{job_description}\n```\n"
            f"3. Analysis Performed:\n```\n{analysis}\n```\n"
            f"4. Modified Resume:\n```\n{modified_resume}\n```\n\n"
            f"Instructions:\n"
            f"- Directly address the user's query ('{user_query}').\n"
            f"- If asked about changes, explain *what* was changed in the 'Modified Resume' compared to the 'Original Resume' and *why*, referencing the 'Analysis Performed' and 'Job Description'.\n"
            f"- If asked about specific parts of the resume or analysis, provide relevant information from the context.\n"
            f"- Maintain a helpful, clear, and conversational tone.\n"
            f"- Keep the answer concise and focused on the user's question.\n"
            f"- **CRITICAL**: Your role is EXPLANATION ONLY. Do NOT suggest making changes, do not offer to modify the resume, and do not output modified resume text. Just provide the explanation based on the context."
            f"- Do NOT ask the user if they want to modify the resume further in your response."
        ),
        expected_output=(
            "A concise, conversational answer to the user's query based on the provided context. "
            "For example, if asked 'What changes did you make?', the output might be: "
            "'Based on the analysis and the job description's focus on X, I modified the skills section to include keywords like Y and Z, and expanded on Project A to better highlight your experience with tool B mentioned in the requirements.' "
            "The output should NOT contain any modified resume text or offers to make changes."
        ),
        agent=resume_explainer_agent, human_input=False
    )


# --- Crew Definitions ---
# Crew for the initial analysis and modification run
resume_improvement_crew = Crew(
    agents=[resume_analyzer, resume_modifier],
    tasks=[], # Tasks are set dynamically
    process=Process.sequential,
    verbose=True
)

# Crew for generating essay answers
essay_writing_crew = Crew(
    agents=[essay_writer],
    tasks=[], # Task set dynamically
    process=Process.sequential,
    verbose=True
)

# Crew for handling explanations in the chat window
explanation_crew = Crew(
    agents=[resume_explainer_agent],
    tasks=[], # Task set dynamically
    process=Process.sequential,
    verbose=True
)

# Crew specifically for modifying the resume based on feedback (used by chat)
# Note: This reuses the resume_modifier agent but runs it in isolation.
feedback_modification_crew = Crew(
    agents=[resume_modifier],
    tasks=[], # Task set dynamically
    process=Process.sequential,
    verbose=True
)


# --- Helper Function for Extraction ---
def extract_content(text, start_marker, end_marker):
    """
    Extracts content between start and end markers.
    Returns None if markers are not found correctly.
    """
    try:
        # Handle potential None input gracefully
        if text is None:
             log.warning("extract_content received None input.")
             return None
        start_idx = text.find(start_marker)
        if start_idx == -1:
            # log.debug(f"Start marker '{start_marker}' not found.")
            return None
        start_idx += len(start_marker)
        end_idx = text.find(end_marker, start_idx)
        if end_idx == -1:
            log.debug(f"End marker '{end_marker}' not found after start marker '{start_marker}'.")
            return None
        # Return stripped content between markers
        return text[start_idx:end_idx].strip()
    except Exception as e:
        log.error(f"Error during content extraction with markers '{start_marker}'/'{end_marker}': {e}")
        return None

# --- Helper Function to Clean Agent Output ---
def clean_raw_output(raw_output):
    """
    Attempts to remove known filler patterns from the beginning of the agent's raw output string.
    """
    if not isinstance(raw_output, str):
        return raw_output # Return as is if not a string

    cleaned_output = raw_output.strip() # Remove leading/trailing whitespace first

    # Iteratively remove known bad patterns from the beginning
    removed_filler = False
    for pattern in BAD_FILLER_PATTERNS:
        # Use lower() for case-insensitive check but remove original case pattern
        if cleaned_output.lower().startswith(pattern.lower()):
            # Find the actual pattern case-insensitively at the start
            match = re.match(re.escape(pattern), cleaned_output, re.IGNORECASE)
            if match:
                 actual_pattern_length = len(match.group(0))
                 # Check if removing the pattern leaves anything substantial
                 if len(cleaned_output) > actual_pattern_length:
                     cleaned_output = cleaned_output[actual_pattern_length:].lstrip() # Remove pattern and leading space/newline
                     log.warning(f"Removed known filler pattern: '{match.group(0).strip()}'")
                     removed_filler = True
                 else:
                     # Removing the pattern would leave nothing, likely means it was the whole output
                     log.error(f"Agent returned only the disallowed filler phrase: '{pattern.strip()}'")
                     return f"(Agent Error: Output was only filler '{pattern.strip()}')"

    # Specific check for the exact bad phrase if it's the *entire* output after initial stripping
    if cleaned_output == "I now can give a great answer":
         log.error("Agent returned only the disallowed filler phrase.")
         return f"(Agent Error: Output was only filler '{cleaned_output}')" # Return specific error

    return cleaned_output


# --- Main Execution Functions ---

# Function to run the initial analysis and modification sequence
def run_resume_analysis_and_modification(resume_content, job_description):
    """Runs the sequential process of analyzing and then modifying the resume."""
    log.info("Starting resume analysis and modification process...")
    analysis_result = "(Analysis failed)" # Default error values
    modified_resume_text = "(Modification failed)"

    try:
        # Create the tasks for the crew
        analysis_task = create_analysis_task(resume_content, job_description)
        # Pass analysis_context=None for the initial modification
        modification_task = create_modification_task(resume_content, job_description, analysis_context=None, user_feedback=None)
        resume_improvement_crew.tasks = [analysis_task, modification_task]

        # Execute the crew
        crew_result = resume_improvement_crew.kickoff()
        log.info("Resume improvement crew finished.")

        # Process the result (might be a string or an object)
        raw_result_string = ""
        if hasattr(crew_result, 'raw') and isinstance(crew_result.raw, str):
            raw_result_string = crew_result.raw
        elif isinstance(crew_result, str):
            raw_result_string = crew_result
            log.warning("crew.kickoff() returned string directly.")
        else:
            log.error(f"Unexpected result type from crew.kickoff(): {type(crew_result)}")
            error_msg = "Error: Unexpected result format from AI agents."
            return error_msg, error_msg # Return error for both

        log.debug(f"Raw crew result string (analysis+modification):\n{raw_result_string[:500]}...")

        # ** Clean the raw output first **
        cleaned_result_string = clean_raw_output(raw_result_string)
        if cleaned_result_string.startswith("(Agent Error:"): # Check if cleaning detected only filler
             log.error("Agent output cleaning failed.")
             return cleaned_result_string, cleaned_result_string # Return the specific error

        log.debug(f"Cleaned crew result string:\n{cleaned_result_string[:500]}...")

        # --- Extraction Logic on Cleaned String ---
        analysis_result = None
        modified_resume_text = None # This will store the text *with* the formatting markers now
        modification_start_index = cleaned_result_string.find(MODIFICATION_START_MARKER)
        modification_end_index = -1
        analysis_start_index = cleaned_result_string.find(ANALYSIS_START_MARKER)
        analysis_end_index = -1

        # 1. Try to find modification markers (enclosing the formatted text)
        if modification_start_index != -1:
            modification_end_index = cleaned_result_string.find(MODIFICATION_END_MARKER, modification_start_index + len(MODIFICATION_START_MARKER))
            if modification_end_index != -1:
                # Extract the content *including* the inner formatting markers
                modified_resume_text = cleaned_result_string[modification_start_index + len(MODIFICATION_START_MARKER):modification_end_index].strip()
                log.info("Successfully extracted modification block (with formatting markers) using main markers.")
                # If modification found, assume text before it is analysis
                analysis_part = cleaned_result_string[:modification_start_index].strip()
                # Try to extract analysis from this part using markers
                analysis_result = extract_content(analysis_part, ANALYSIS_START_MARKER, ANALYSIS_END_MARKER)
                if analysis_result is None:
                    log.warning("Modification markers found, but analysis markers missing in the preceding text. Using preceding text as analysis (fallback).")
                    # Fallback: Use the text before modification as analysis, wrap it for consistency
                    if analysis_part: # Only wrap if there's content
                         analysis_result = f"{ANALYSIS_START_MARKER}\n{analysis_part}\n{ANALYSIS_END_MARKER}"
                    else:
                         analysis_result = "(Analysis part before modification was empty)"
                         log.warning("Analysis part before modification markers was empty.")
                else:
                    log.info("Successfully extracted analysis using markers from text before modification.")
            else:
                log.warning("Found modification start marker but no end marker in cleaned output.")
                # Modification extraction failed here

        # 2. If modification wasn't found (or markers were incomplete), try finding analysis markers in the whole cleaned string
        if modified_resume_text is None:
            log.info("Modification block not extracted. Attempting to extract analysis from full cleaned output.")
            analysis_result = extract_content(cleaned_result_string, ANALYSIS_START_MARKER, ANALYSIS_END_MARKER)
            if analysis_result is not None:
                log.info("Successfully extracted analysis using markers (modification likely failed or missing markers).")
                modified_resume_text = "(Modification block could not be extracted - check markers)" # Set modification placeholder
            else:
                log.warning("Could not extract analysis OR modification block using markers from the full cleaned output.")
                analysis_result = "(Analysis could not be extracted - check markers)"
                modified_resume_text = "(Modification block could not be extracted - check markers)"
                # Add more details for debugging
                if len(cleaned_result_string) < 200: # If output is short, maybe it's just an error message
                     analysis_result = f"(No markers found in cleaned output: {cleaned_result_string})"
                     modified_resume_text = f"(No markers found in cleaned output: {cleaned_result_string})"


        # Final checks and defaults
        if analysis_result is None: analysis_result = "(Analysis extraction failed)"
        if modified_resume_text is None: modified_resume_text = "(Modification block extraction failed)"

        # Basic check for error keywords in results
        if "error" in analysis_result.lower() or "exception" in analysis_result.lower():
            log.warning(f"Analysis result seems to contain an error message: {analysis_result[:100]}...")
        if "error" in modified_resume_text.lower() or "exception" in modified_resume_text.lower():
            log.warning(f"Modification result seems to contain an error message: {modified_resume_text[:100]}...")

        log.info(f"Final Analysis Result Length: {len(analysis_result)}")
        log.info(f"Final Modification Block Length: {len(modified_resume_text)}")
        # Return the analysis (with markers) and the modified resume block (with internal formatting markers)
        return analysis_result, modified_resume_text

    except Exception as e:
        log.error(f"Error during resume analysis/modification crew execution: {e}", exc_info=True)
        error_msg = f"Error during analysis/modification: {e}"
        # Return error message for both outputs if crew fails
        return error_msg, error_msg


# Function to run only the modification task, incorporating user feedback from chat
def run_resume_modification_with_feedback(resume_content, job_description, analysis_context, user_feedback):
    """Runs only the modification task, incorporating user feedback."""
    log.info("Starting resume modification process with user feedback...")
    if not user_feedback:
        log.warning("Modification requested but no feedback provided.")
        return "(No feedback provided for modification)"

    try:
        # Clean up analysis context if it still has markers
        clean_analysis = extract_content(analysis_context, ANALYSIS_START_MARKER, ANALYSIS_END_MARKER) or analysis_context

        # Create the modification task with the feedback (this task now includes marker instructions)
        modification_task = create_modification_task(
            resume_content, job_description, clean_analysis, user_feedback
        )
        # Use the dedicated crew for this
        feedback_modification_crew.tasks = [modification_task]

        # Execute the crew
        crew_result = feedback_modification_crew.kickoff()
        log.info("Modification with feedback finished.")

        # Process result
        raw_result_string = ""
        if hasattr(crew_result, 'raw') and isinstance(crew_result.raw, str):
            raw_result_string = crew_result.raw
        elif isinstance(crew_result, str):
            raw_result_string = crew_result
            log.warning("Feedback crew kickoff returned string directly.")
        else:
            log.error(f"Unexpected result type from feedback crew: {type(crew_result)}")
            return "Error: Unexpected result format from AI agent."

        log.debug(f"Raw feedback modification result string:\n{raw_result_string[:500]}...")

        # ** Clean the raw output first **
        cleaned_result_string = clean_raw_output(raw_result_string)
        if cleaned_result_string.startswith("(Agent Error:"): # Check if cleaning detected only filler
             log.error("Agent output cleaning failed (feedback mod).")
             return cleaned_result_string # Return the specific error

        log.debug(f"Cleaned feedback modification result string:\n{cleaned_result_string[:500]}...")

        # Extract the modified resume block *with formatting markers* using the main markers
        modified_resume_block = extract_content(cleaned_result_string, MODIFICATION_START_MARKER, MODIFICATION_END_MARKER)

        if modified_resume_block is not None:
            log.info("Successfully extracted modified resume block (with formatting markers) from feedback run.")
            # Basic check for errors within the block
            if "error" in modified_resume_block.lower() or "exception" in modified_resume_block.lower():
                 log.warning(f"Feedback modification block seems to contain an error message: {modified_resume_block[:100]}...")
            return modified_resume_block # Return the block with internal markers
        else:
            # Fallback if main markers are missing in the cleaned string
            log.warning("Could not find main start/end markers in cleaned modification feedback output.")
            # Check if the cleaned output *looks* like it contains the formatting markers
            if any(marker in cleaned_result_string for marker in [FMT_NAME, FMT_HEADING, FMT_BULLET]):
                log.warning("Cleaned output seems to contain formatting markers but lacks main enclosure. Returning cleaned string.")
                return cleaned_result_string # Return the full cleaned string as a fallback
            else:
                log.warning("Cleaned output does not look like formatted resume text. Returning full cleaned result string as error/unexpected output.")
                return f"(Modification markers missing in cleaned agent output: {cleaned_result_string[:100]}...)"

    except Exception as e:
        log.error(f"Error during resume modification with feedback: {e}", exc_info=True)
        return f"Error during modification with feedback: {e}"


# Essay generation function (no changes needed for formatting markers)
def run_essay_generation(resume_content, job_description, essay_question, user_input=None, experience_level=None):
    """Runs the essay generation task."""
    log.info("Starting essay generation process...")
    try:
        task = create_essay_task(resume_content, job_description, essay_question, user_input, experience_level)
        essay_writing_crew.tasks = [task]

        # Execute the crew
        crew_result = essay_writing_crew.kickoff()
        log.info("Essay writing crew execution finished.")

        # Process result
        raw_result_string = ""
        if hasattr(crew_result, 'raw') and isinstance(crew_result.raw, str):
            raw_result_string = crew_result.raw
        elif isinstance(crew_result, str):
            raw_result_string = crew_result
            log.warning("Essay crew kickoff returned string directly.")
        else:
            log.error(f"Unexpected result type from essay crew: {type(crew_result)}")
            return "Error: Unexpected result format from AI agent."

        log.debug(f"Raw essay result string:\n{raw_result_string[:500]}...")

        # ** Clean the raw output first **
        cleaned_result_string = clean_raw_output(raw_result_string)
        if cleaned_result_string.startswith("(Agent Error:"): # Check if cleaning detected only filler
             log.error("Agent output cleaning failed (essay).")
             return cleaned_result_string # Return the specific error

        log.debug(f"Cleaned essay result string:\n{cleaned_result_string[:500]}...")


        # Check if the agent returned a question (check cleaned string)
        if cleaned_result_string.strip().startswith("QUESTION:"):
            log.info("Agent returned a question.")
            return cleaned_result_string.strip() # Return the question directly

        # Otherwise, try to extract the essay using markers from the cleaned string
        essay_text = extract_content(cleaned_result_string, ESSAY_START_MARKER, ESSAY_END_MARKER)

        if essay_text is not None:
            log.info("Successfully extracted essay.")
            return essay_text
        else:
            # Handle failure to follow format
            log.error(f"Essay agent failed to follow output format (markers/QUESTION prefix missing in cleaned output). Cleaned Output: {cleaned_result_string}")
            # Provide a user-friendly error
            return "Error: AI failed to generate essay in the expected format. Please try again or rephrase."

    except Exception as e:
        log.error(f"Error during essay generation crew execution: {e}", exc_info=True)
        return f"Error during essay generation: {e}"


# Explanation function (no changes needed for formatting markers)
def run_explanation(user_query, original_resume, job_description, analysis, modified_resume):
    """Runs the explanation task to answer user queries about the resume."""
    log.info(f"Starting explanation process for query: {user_query}")
    try:
        # Clean up context from markers before sending to explainer agent
        # Use the main markers here, not the internal formatting ones
        clean_analysis = extract_content(analysis, ANALYSIS_START_MARKER, ANALYSIS_END_MARKER) or analysis
        clean_modified_resume = extract_content(modified_resume, MODIFICATION_START_MARKER, MODIFICATION_END_MARKER) or modified_resume

        # Create and run the explanation task
        task = create_explanation_task(user_query, original_resume, job_description, clean_analysis, clean_modified_resume)
        explanation_crew.tasks = [task]
        crew_result = explanation_crew.kickoff()
        log.info("Explanation crew finished.")

        # Process result
        explanation_text = ""
        if hasattr(crew_result, 'raw') and isinstance(crew_result.raw, str):
            explanation_text = crew_result.raw.strip()
        elif isinstance(crew_result, str):
            explanation_text = crew_result.strip()
            log.warning("Explanation crew kickoff returned string directly.")
        else:
            log.error(f"Unexpected result type from explanation crew: {type(crew_result)}")
            return "Error: Could not get explanation from AI."

        log.debug(f"Raw explanation result string:\n{explanation_text}")

        # Clean filler from explanation output as well
        cleaned_explanation = clean_raw_output(explanation_text)
        log.debug(f"Cleaned explanation result string:\n{cleaned_explanation}")

        # Remove the check that was truncating explanations
        # if MODIFICATION_START_MARKER in cleaned_explanation:
        #      log.warning("Explanation agent might have included resume text (marker found). Returning empty string.")
        #      return "(Explanation potentially corrupted, contained modification markers)"

        return cleaned_explanation # Return cleaned explanation
    except Exception as e:
        log.error(f"Error during explanation crew execution: {e}", exc_info=True)
        return f"Error getting explanation: {e}"


# --- Example Usage (if run directly) ---
if __name__ == '__main__':
    # Setup basic logging for direct script run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Dummy data for testing
    dummy_resume = "John Doe\nPython Developer\nExperience: Project X (Python, SQL)"
    dummy_jd = "Seeking a Senior Python Developer with experience in Cloud (AWS/Azure) and API design. SQL knowledge is a plus."
    dummy_essay_q = "Describe a challenging project and how you overcame obstacles."
    dummy_exp = "5"
    dummy_user_essay_input = "My most challenging project involved optimizing a legacy database query."

    print("\n--- Testing Resume Analysis & Modification (with Formatting Markers) ---")
    analysis, modification_block = run_resume_analysis_and_modification(dummy_resume, dummy_jd)
    print("\nAnalysis Result:") ; print(analysis)
    print("\nModification Block (with Markers):") ; print(modification_block) # This now contains markers

    # Simulate feedback based on initial modification
    # Check if modification seems valid before proceeding with feedback test
    if modification_block and not modification_block.startswith("("):
        dummy_user_feedback = "Please also add experience with Docker and Git."
        print(f"\n--- Testing Modification with Feedback: '{dummy_user_feedback}' ---")
        feedback_modification_block = run_resume_modification_with_feedback(
            dummy_resume, dummy_jd, analysis, dummy_user_feedback
        )
        print("\nModification Block after Feedback (with Markers):") ; print(feedback_modification_block)
        # Update modification result for explanation test if feedback was successful
        if feedback_modification_block and not feedback_modification_block.startswith("("):
             modification_block = feedback_modification_block # Use the latest modification block for explanation
    else:
         print("\n--- Skipping Modification with Feedback test (initial modification failed) ---")


    print("\n--- Testing Explanation ---")
    # Ensure analysis and modification are strings before passing to explanation
    analysis_for_exp = analysis if isinstance(analysis, str) else "(Analysis not available)"
    # Explanation agent needs plain text, extract it from the block
    modification_for_exp = extract_content(modification_block, MODIFICATION_START_MARKER, MODIFICATION_END_MARKER) or modification_block # Fallback if markers somehow missing
    dummy_user_query = "What changes did you make to the skills section and why?"
    explanation = run_explanation(dummy_user_query, dummy_resume, dummy_jd, analysis_for_exp, modification_for_exp)
    print("\nExplanation Response:") ; print(explanation)

    # Essay tests remain the same
    print("\n--- Testing Essay Generation (No User Input) ---")
    essay_no_input = run_essay_generation(dummy_resume, dummy_jd, dummy_essay_q, experience_level=dummy_exp)
    print("\nEssay (No Input):") ; print(essay_no_input)

    print("\n--- Testing Essay Generation (With User Input) ---")
    essay_with_input = run_essay_generation(dummy_resume, dummy_jd, dummy_essay_q, user_input=dummy_user_essay_input)
    print("\nEssay (With Input):") ; print(essay_with_input)

    print("\n--- Agent tests finished. ---")

