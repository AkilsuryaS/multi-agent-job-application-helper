import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import json
import os
import logging
import logging.handlers # For RotatingFileHandler
import threading
import queue
import sys # To check if running as frozen executable
import platform # To check OS
import re # For chat keyword detection

# Import local modules
import utils
import job_application_agent as agent_runner # Contains all agent functions now
import config
# Removed import form_filler

# --- Configuration & Setup ---
APP_TITLE = "Job Application Helper"
USER_DATA_FILE = "user_data.json" # Keep for potential future use or other data
VERSION = "1.9" # Incremented version for Basic Info removal

# Configure logging (main setup)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_file = 'job_app_helper.log'
# 5 MB per file, 3 backups
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=1024*1024*5, backupCount=3, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(log_format))
stream_handler = logging.StreamHandler() # Also log to console
stream_handler.setFormatter(logging.Formatter(log_format))
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
log = logging.getLogger(__name__) # Main application logger

# --- Check if running as executable ---
def is_frozen():
    """Checks if the application is running as a bundled executable."""
    return getattr(sys, 'frozen', False)

# --- Main Application Class ---
class JobAppHelperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} v{VERSION}")
        # self.root.geometry("850x700") # Adjust size maybe

        # --- State Variables ---
        self.resume_path = tk.StringVar()
        self.resume_content_original = tk.StringVar()
        self.resume_content_modified = tk.StringVar() # Stores the modified text *with* formatting markers
        self.job_description = tk.StringVar()
        self.analysis_result = tk.StringVar() # Stores the analysis text (with markers if present)
        self.user_data = {} # Store as dict (can be used for other purposes if needed)
        self.gui_queue = queue.Queue() # Thread communication
        self.is_task_running = False # Flag to prevent multiple simultaneous tasks

        # Basic Info Fields REMOVED
        # self.basic_info_vars = { ... }

        # --- Initialization ---
        self.load_user_data() # This method will be modified
        self.create_widgets()

        # Check API Key (critical)
        if not agent_runner.LOADED_API_KEY:
             messagebox.showerror("API Key Error", "NVIDIA API Key not found or failed to load. Please ensure a valid key is in your .env file in the application directory.")
             self.root.quit()
             return

        # Start queue listener
        self.root.after(100, self.process_gui_queue)
        log.info("Application initialized.")

    def create_widgets(self):
        """Creates and arranges all the GUI elements."""
        log.debug("Creating widgets...")
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Configure grid weights within main_frame
        main_frame.columnconfigure(0, weight=3, uniform="col") # Resume
        main_frame.columnconfigure(1, weight=3, uniform="col") # JD
        main_frame.columnconfigure(2, weight=1, uniform="col") # Actions (reduced weight or adjust as needed)
        main_frame.rowconfigure(1, weight=1) # Top row text areas
        main_frame.rowconfigure(4, weight=1) # Bottom row text area (Modified Resume)

        # --- Column 0: Resume Input ---
        ttk.Label(main_frame, text="Original Resume").grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        resume_frame = ttk.Frame(main_frame); resume_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        resume_frame.rowconfigure(0, weight=1); resume_frame.columnconfigure(0, weight=1)
        self.resume_text = scrolledtext.ScrolledText(resume_frame, wrap=tk.WORD, height=10, state=tk.DISABLED, relief=tk.SUNKEN, bd=1); self.resume_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        ttk.Button(main_frame, text="Upload Resume (.pdf, .docx)", command=self.upload_resume).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)

        # --- Column 1: Job Description ---
        ttk.Label(main_frame, text="Job Description").grid(row=0, column=1, sticky=tk.W, pady=(0, 2))
        jd_frame = ttk.Frame(main_frame); jd_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5))
        jd_frame.rowconfigure(0, weight=1); jd_frame.columnconfigure(0, weight=1)
        self.jd_text = scrolledtext.ScrolledText(jd_frame, wrap=tk.WORD, height=10, relief=tk.SUNKEN, bd=1); self.jd_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # --- Column 0+1 (Bottom): Modified Resume / Analysis ---
        ttk.Label(main_frame, text="Modified Resume / Analysis").grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        modified_frame = ttk.Frame(main_frame); modified_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        modified_frame.rowconfigure(0, weight=1); modified_frame.columnconfigure(0, weight=1)
        self.modified_resume_text_area = scrolledtext.ScrolledText(modified_frame, wrap=tk.WORD, height=10, state=tk.DISABLED, relief=tk.SUNKEN, bd=1); self.modified_resume_text_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # --- Column 2: Actions ---
        info_actions_frame = ttk.Frame(main_frame, padding="5")
        info_actions_frame.grid(row=0, column=2, rowspan=5, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        info_actions_frame.columnconfigure(0, weight=1)
        # Basic Info Section REMOVED
        # ttk.Button for "Save Info" REMOVED

        # Action Buttons Section
        action_frame = ttk.LabelFrame(info_actions_frame, text="Resume/Essay Actions", padding="10")
        action_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 5)) # Adjusted row to 0
        action_frame.columnconfigure(0, weight=1)
        self.analyze_button = ttk.Button(action_frame, text="Analyze & Suggest Modifications", command=self.run_analysis_modification_thread); self.analyze_button.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3)
        self.save_mod_button = ttk.Button(action_frame, text="Save Formatted Resume", command=self.save_modified_resume, state=tk.DISABLED); self.save_mod_button.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)
        self.chat_button = ttk.Button(action_frame, text="Discuss/Modify via Chat", command=self.open_chat_window, state=tk.DISABLED); self.chat_button.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3)
        self.essay_button = ttk.Button(action_frame, text="Generate Essay Answer", command=self.open_essay_window); self.essay_button.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=3)

        # Status Bar
        self.status_label = ttk.Label(main_frame, text="Ready", anchor=tk.W, relief=tk.SUNKEN, padding=(5, 2)); self.status_label.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0), padx=5)
        log.debug("Widgets created.")

    def set_status(self, message, clear_after=None):
        """Updates the status bar message."""
        self.status_label.config(text=message); log.info(f"Status: {message}")
        if hasattr(self, "_status_clear_timer"):
            self.root.after_cancel(self._status_clear_timer)
            del self._status_clear_timer
        if clear_after:
            self._status_clear_timer = self.root.after(clear_after * 1000, lambda: self.status_label.config(text="Ready"))

    def update_text_widget(self, widget, content):
        """Safely updates a text widget's content, preserving state."""
        if not widget:
             log.error("Attempted to update a non-existent widget.")
             return
        try:
            current_state = str(widget.cget("state"))
            widget.config(state=tk.NORMAL)
            widget.delete('1.0', tk.END)
            if content:
                widget.insert('1.0', content)
            widget.config(state=current_state)
        except tk.TclError as e:
            if "invalid command name" in str(e):
                 log.warning(f"Error updating text widget (likely destroyed): {e}")
            else:
                 log.error(f"TclError updating text widget: {e}")
        except Exception as e:
            log.error(f"Unexpected error updating text widget: {e}", exc_info=True)

    def load_user_data(self):
        """Loads user data from the JSON file (if any other data is stored there)."""
        log.info(f"Attempting to load user data from {USER_DATA_FILE}")
        try:
            if os.path.exists(USER_DATA_FILE):
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    self.user_data = json.load(f)
                # Basic info vars loop REMOVED
                log.info(f"User data loaded successfully (Basic Info section removed).")
            else:
                self.user_data = {}
                log.info(f"{USER_DATA_FILE} not found. Starting with empty user data.")
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error in {USER_DATA_FILE}: {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load user data file (corrupted?).\n{USER_DATA_FILE}\nError: {e}")
            self.user_data = {}
        except Exception as e:
            log.error(f"Error loading user data: {e}", exc_info=True)
            messagebox.showwarning("Load Error", f"An unexpected error occurred while loading user data.\nError: {e}")
            self.user_data = {}

    def save_user_data(self):
        """Saves current user info to the JSON file (if any other data is stored)."""
        log.debug("Saving user data (Basic Info section removed)...")
        # Basic info vars loop REMOVED
        # If self.user_data is used for other things, keep the write operation.
        # Otherwise, this method might become largely unnecessary.
        try:
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_data, f, indent=4) # Saves whatever is in self.user_data
            log.info(f"User data saved to {USER_DATA_FILE} (Basic Info section removed).")
            # self.set_status("Basic info saved.", clear_after=3) # "Save Info" button removed
        except Exception as e:
            log.error(f"Error saving user data to {USER_DATA_FILE}: {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Could not save user data.\nError: {e}")

    def upload_resume(self):
        if self.is_task_running:
            messagebox.showwarning("Busy", "Another task is currently running.")
            return
        log.debug("Upload resume button clicked.")
        file_path = filedialog.askopenfilename(
            title="Select Resume File",
            filetypes=[("PDF files", "*.pdf"), ("Word Documents", "*.docx")]
        )
        if not file_path:
            log.info("Resume selection cancelled.")
            return

        self.resume_path.set(file_path)
        self.set_status(f"Loading resume: {os.path.basename(file_path)}...")
        self.is_task_running = True
        self.disable_ai_buttons()

        thread = threading.Thread(target=self._parse_resume_thread, args=(file_path,), daemon=True)
        thread.start()

    def _parse_resume_thread(self, file_path):
        log.info(f"Parsing resume in background thread: {file_path}")
        content = utils.parse_resume(file_path)
        self.gui_queue.put(("resume_parsed", content, file_path))

    def _update_gui_post_parse(self, content, file_path):
        self.is_task_running = False
        if content:
            self.resume_content_original.set(content)
            self.update_text_widget(self.resume_text, content)
            self.set_status("Resume loaded successfully.")
            self.resume_content_modified.set("")
            self.analysis_result.set("")
            self.update_text_widget(self.modified_resume_text_area, "")
        else:
            self.resume_path.set("")
            self.resume_content_original.set("")
            self.update_text_widget(self.resume_text, "")
            self.set_status("Failed to load or parse resume.", clear_after=5)
        self.enable_ai_buttons()

    def save_modified_resume(self):
        if self.is_task_running: return
        log.debug("Save Formatted Resume button clicked.")
        modified_content_block = self.resume_content_modified.get()
        is_error_placeholder = modified_content_block.startswith((
            "(Modification failed)", "(Modification extraction failed)",
            "(Modification block could not be extracted - check markers)",
            "(Modification block extraction failed)",
            "(Agent Error:",
            "Error:"
            ))
        if not modified_content_block or is_error_placeholder:
            messagebox.showwarning("No Valid Content", "No valid modified resume content (with formatting markers) available to save.")
            return

        original_basename = os.path.basename(self.resume_path.get() or "resume")
        initial_filename = f"{os.path.splitext(original_basename)[0]}_formatted"
        file_path = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(self.resume_path.get() or "."),
            title="Save Formatted Resume As",
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")]
        )
        if not file_path:
            log.info("Save operation cancelled by user.")
            return
        if not file_path.lower().endswith(".docx"):
            file_path += ".docx"
        saved_path = utils.format_resume_with_markers(
            modified_content_block,
            filename=file_path
        )
        if saved_path:
            log.info(f"Formatted resume saved to {saved_path}")
            self.set_status(f"Formatted resume saved to {os.path.basename(saved_path)}", clear_after=5)

    def run_ai_task_in_thread(self, task_function, *args):
        if self.is_task_running:
            messagebox.showwarning("Busy", "Another task is already running.")
            return False
        self.is_task_running = True
        self.disable_ai_buttons()
        self.set_status("AI task running in background...")
        thread = threading.Thread(target=task_function, args=args, daemon=True)
        thread.start()
        return True

    def enable_ai_buttons(self):
        log.debug("Enabling buttons.")
        self.is_task_running = False
        self.analyze_button.config(state=tk.NORMAL)
        mod_content = self.resume_content_modified.get()
        is_mod_valid = mod_content and not mod_content.startswith((
             "(Modification failed)", "(Modification extraction failed)",
             "(Modification block could not be extracted - check markers)",
             "(Modification block extraction failed)",
             "(Agent Error:",
             "Error:"
             ))
        self.save_mod_button.config(state=tk.NORMAL if is_mod_valid else tk.DISABLED)
        analysis_content = self.analysis_result.get()
        is_analysis_valid = analysis_content and not analysis_content.startswith((
             "(Analysis failed)", "(Analysis extraction failed)",
             "(Analysis could not be extracted - check markers)",
             "(Analysis part before modification",
             "(Analysis markers missing, content unavailable)",
             "(Agent Error:",
             "Error:"
             ))
        original_exists = bool(self.resume_content_original.get())
        jd_exists = bool(self.jd_text.get("1.0", tk.END).strip())
        can_chat = original_exists and jd_exists and (is_analysis_valid or is_mod_valid)
        self.chat_button.config(state=tk.NORMAL if can_chat else tk.DISABLED)
        self.essay_button.config(state=tk.NORMAL if original_exists else tk.DISABLED)

    def disable_ai_buttons(self):
        log.debug("Disabling buttons.")
        self.analyze_button.config(state=tk.DISABLED)
        self.save_mod_button.config(state=tk.DISABLED)
        self.chat_button.config(state=tk.DISABLED)
        self.essay_button.config(state=tk.DISABLED)

    def run_analysis_modification_thread(self):
        log.debug("Analyze & Modify button clicked.")
        original_resume = self.resume_content_original.get()
        job_desc = self.jd_text.get("1.0", tk.END).strip()
        if not original_resume:
            messagebox.showerror("Input Missing", "Please upload a resume first.")
            return
        if not job_desc:
            messagebox.showerror("Input Missing", "Please paste the job description first.")
            return
        if self.run_ai_task_in_thread(self._execute_analysis_modification, original_resume, job_desc):
            log.info("Started analysis and modification thread.")

    def _execute_analysis_modification(self, original_resume, job_desc):
        log.info("Executing analysis and modification task...")
        try:
            analysis, modification_block = agent_runner.run_resume_analysis_and_modification(original_resume, job_desc)
            self.gui_queue.put(("analysis_modification_complete", analysis, modification_block))
        except Exception as e:
            log.error(f"Error in analysis/modification thread: {e}", exc_info=True)
            self.gui_queue.put(("task_error", f"Analysis/modification error: {e}"))

    def _update_gui_post_analysis(self, analysis, modification_block):
        log.info("Updating GUI after analysis/modification.")
        self.analysis_result.set(analysis or "(No analysis generated)")
        self.resume_content_modified.set(modification_block or "(No modification generated)")
        display_analysis = self.analysis_result.get()
        display_modification = self.resume_content_modified.get()
        analysis_failed = display_analysis.startswith(("(", "Error:", "(Agent Error:"))
        modification_failed = display_modification.startswith(("(", "Error:", "(Agent Error:"))
        display_content = ""
        if not analysis_failed:
             analysis_text_for_display = agent_runner.extract_content(display_analysis, agent_runner.ANALYSIS_START_MARKER, agent_runner.ANALYSIS_END_MARKER) or display_analysis
             display_content += f"--- ANALYSIS ---:\n{analysis_text_for_display}\n\n"
        else:
             display_content += f"--- ANALYSIS ---:\n{display_analysis}\n\n"
        if not modification_failed:
             display_content += f"--- MODIFIED RESUME (with formatting markers) ---:\n{display_modification}"
        else:
             display_content += f"--- MODIFIED RESUME ---:\n{display_modification}"
        self.update_text_widget(self.modified_resume_text_area, display_content)
        self.modified_resume_text_area.config(state=tk.DISABLED)
        if not modification_failed:
            if analysis_failed:
                 self.set_status("Modification complete (with markers), but analysis extraction failed.", clear_after=7)
            else:
                 self.set_status("Analysis and modification complete (markers added).")
        else:
            if analysis_failed:
                 self.set_status("Task failed: Analysis and modification extraction failed.", clear_after=7)
            else:
                 self.set_status("Task complete, but modification block extraction failed.", clear_after=7)

    def _update_gui_post_feedback(self, modification_block):
        log.info("Updating GUI after feedback modification.")
        self.resume_content_modified.set(modification_block or "(No modification generated after feedback)")
        display_analysis = self.analysis_result.get()
        display_modification = self.resume_content_modified.get()
        modification_succeeded = not display_modification.startswith(("(", "Error:", "(Agent Error:"))
        analysis_text_for_display = agent_runner.extract_content(display_analysis, agent_runner.ANALYSIS_START_MARKER, agent_runner.ANALYSIS_END_MARKER) or display_analysis
        display_content = f"--- ANALYSIS ---:\n{analysis_text_for_display}\n\n"
        display_content += f"--- MODIFIED RESUME (Based on Feedback - with markers) ---:\n{display_modification}"
        if not modification_succeeded:
             display_content += "\n(Modification based on feedback failed or could not be extracted.)"
        self.update_text_widget(self.modified_resume_text_area, display_content)
        self.modified_resume_text_area.config(state=tk.DISABLED)
        if modification_succeeded:
            self.set_status("Resume regenerated based on feedback (markers added).")
        else:
            self.set_status("Feedback task complete, but modification failed.", clear_after=7)

    def process_gui_queue(self):
        try:
            while True:
                message = self.gui_queue.get_nowait()
                msg_type = message[0]
                log.debug(f"Processing GUI queue message: {msg_type}")
                if msg_type == "resume_parsed":
                    _, content, file_path = message
                    self._update_gui_post_parse(content, file_path)
                elif msg_type == "analysis_modification_complete":
                    _, analysis, modification_block = message
                    self._update_gui_post_analysis(analysis, modification_block)
                    self.enable_ai_buttons()
                elif msg_type == "modification_feedback_complete":
                    _, modification_block = message
                    self._update_gui_post_feedback(modification_block)
                    self.enable_ai_buttons()
                elif msg_type == "essay_complete":
                    _, result = message
                    log.info(f"Essay generation result received (handled by EssayWindow): {result[:50]}...")
                    self.enable_ai_buttons()
                elif msg_type == "explanation_complete":
                     _, explanation_text, chat_window_instance = message
                     if chat_window_instance and chat_window_instance.window.winfo_exists():
                         chat_window_instance.display_agent_response(explanation_text)
                     else:
                         log.warning("Chat window closed before explanation response could be displayed.")
                     self.enable_ai_buttons()
                elif msg_type == "task_error":
                    _, error_message = message
                    self._show_error_message(error_message)
                    self.enable_ai_buttons()
                elif msg_type == "set_status":
                    _, status_message = message
                    self.set_status(status_message)
                elif msg_type == "show_error":
                    _, title, error_message = message
                    messagebox.showerror(title, error_message, parent=self.root)
                elif msg_type == "show_warning":
                    _, title, warning_message = message
                    messagebox.showwarning(title, warning_message, parent=self.root)
                else:
                     log.warning(f"Received unknown message type in GUI queue: {msg_type}")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_gui_queue)

    def open_chat_window(self):
        if self.is_task_running:
            messagebox.showwarning("Busy", "Another task is currently running.")
            return
        log.debug("Open chat window button clicked.")
        analysis = self.analysis_result.get()
        modified_resume = self.resume_content_modified.get()
        original_resume = self.resume_content_original.get()
        job_desc = self.jd_text.get("1.0", tk.END).strip()
        if not original_resume:
            messagebox.showerror("Error", "Original resume content missing. Cannot open chat.", parent=self.root)
            return
        if not job_desc:
            messagebox.showerror("Error", "Job description content missing. Cannot open chat.", parent=self.root)
            return
        is_analysis_valid = analysis and not analysis.startswith(("(", "Error:", "(Agent Error:"))
        is_mod_valid = modified_resume and not modified_resume.startswith(("(", "Error:", "(Agent Error:", "Modification markers missing"))
        if not (is_analysis_valid or is_mod_valid):
             log.warning(f"Chat window blocked. Analysis valid: {is_analysis_valid}, Modification valid: {is_mod_valid}")
             messagebox.showwarning("No Context", "Valid analysis OR modification must be generated first before chatting.", parent=self.root)
             return
        log.info("Opening chat window with valid context.")
        ChatWindow(self.root, self, analysis, modified_resume)

    def open_essay_window(self):
        if self.is_task_running:
            messagebox.showwarning("Busy", "Another task is currently running.")
            return
        log.debug("Open essay window.")
        original_resume = self.resume_content_original.get()
        if not original_resume:
            messagebox.showerror("Input Missing", "Please upload a resume first before generating essays.", parent=self.root)
            return
        EssayWindow(self.root, self)

    def _show_error_message(self, message):
        log.error(f"Displaying Task Error: {message}")
        messagebox.showerror("Task Error", message, parent=self.root)


# --- Chat Window Class ---
class ChatWindow:
    def __init__(self, parent, main_app, analysis_context, modification_context):
        self.parent = parent
        self.main_app = main_app
        self.analysis_context = analysis_context
        self.modification_context = modification_context
        self.window = tk.Toplevel(parent)
        self.window.title("Discuss/Modify Resume")
        self.window.geometry("650x550")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.chat_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, state=tk.DISABLED, relief=tk.SUNKEN, bd=1)
        self.chat_log.grid(row=0, column=0, sticky="nsew")
        self.chat_log.tag_configure("user", foreground="blue", font=('Helvetica', 10, 'bold'))
        self.chat_log.tag_configure("agent", foreground="black")
        self.chat_log.tag_configure("info", foreground="purple", font=('Helvetica', 10, 'italic'))
        self.chat_log.tag_configure("error", foreground="red")
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.columnconfigure(0, weight=1)
        ttk.Label(input_frame, text="Your message/request:").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,2))
        self.chat_input = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=4, relief=tk.SUNKEN, bd=1)
        self.chat_input.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        self.chat_input.focus()
        self.chat_input.bind("<Return>", self.submit_chat_message_thread_event)
        self.chat_input.bind("<Shift-Return>", self.insert_newline)
        self.submit_button = ttk.Button(input_frame, text="Send", command=self.submit_chat_message_thread, style='Accent.TButton')
        self.submit_button.grid(row=1, column=1, sticky="ns", padx=(5,0))
        self.append_message("Info", "You can ask questions about the analysis/modifications or request specific changes (e.g., 'Change X to Y', 'Add skill Z').", "info")

    def insert_newline(self, event=None):
        self.chat_input.insert(tk.INSERT, '\n')
        return "break"

    def append_message(self, sender, message, tag):
        if not self.window.winfo_exists(): return
        try:
            self.chat_log.config(state=tk.NORMAL)
            if self.chat_log.index('end-1c') != "1.0":
                self.chat_log.insert(tk.END, "\n\n")
            self.chat_log.insert(tk.END, f"{sender}:\n", (tag,))
            self.chat_log.insert(tk.END, message)
            self.chat_log.config(state=tk.DISABLED)
            self.chat_log.see(tk.END)
        except tk.TclError as e:
            log.error(f"Error appending message to chat log: {e}")
        except Exception as e:
             log.error(f"Unexpected error appending message: {e}", exc_info=True)

    def submit_chat_message_thread_event(self, event=None):
        self.submit_chat_message_thread()
        return "break"

    def submit_chat_message_thread(self):
        if self.main_app.is_task_running:
            messagebox.showwarning("Busy", "Another task is running. Please wait.", parent=self.window)
            return
        user_query = self.chat_input.get("1.0", tk.END).strip()
        if not user_query:
            return
        self.append_message("You", user_query, "user")
        self.chat_input.delete("1.0", tk.END)
        original_resume = self.main_app.resume_content_original.get()
        job_desc = self.main_app.jd_text.get("1.0", tk.END).strip()
        analysis = self.analysis_context
        modified_resume = self.modification_context
        if not original_resume or not job_desc:
             err_msg = "Missing original resume or job description context. Cannot process chat."
             self.append_message("Error", err_msg, "error")
             log.error(err_msg)
             return
        is_analysis_valid = analysis and not analysis.startswith(("(", "Error:", "(Agent Error:"))
        is_mod_valid = modified_resume and not modified_resume.startswith(("(", "Error:", "(Agent Error:", "Modification markers missing"))
        if not is_analysis_valid and not is_mod_valid:
             err_msg = "Missing valid analysis and modification context. Cannot process chat."
             self.append_message("Error", err_msg, "error")
             log.error(err_msg)
             return
        is_explanation_request = False
        query_lower = user_query.lower().strip()
        question_starters = ("what", "why", "how", "explain", "did you", "can you tell me", "tell me about", "is there", "does it", "do you")
        if query_lower.endswith("?") or any(query_lower.startswith(starter) for starter in question_starters):
            is_explanation_request = True
            log.info("Chat request identified as EXPLANATION (question format).")
        is_modification_request = False
        if not is_explanation_request:
            modification_keywords = ['change', 'modify', 'update', 'rewrite', 'add', 'remove', 'delete', 'improve', 'enhance', 'revise', 'make it', 'include', 'exclude', 'rephrase', 'put', 'use']
            if any(keyword in query_lower for keyword in modification_keywords):
                is_modification_request = True
                log.info("Chat request identified as MODIFICATION (keywords found, not a question).")
        self.submit_button.config(state=tk.DISABLED)
        task_started = False
        if is_explanation_request:
             self.append_message("Agent", "Thinking...", "agent")
             log.info("Routing chat request to explanation agent.")
             task_started = self.main_app.run_ai_task_in_thread(
                 self._execute_explanation, user_query, original_resume, job_desc, analysis, modified_resume, self
             )
        elif is_modification_request:
             self.append_message("Agent", "Processing modification request...", "info")
             log.info("Routing chat request to modification agent.")
             task_started = self.main_app.run_ai_task_in_thread(
                 self._execute_modification_feedback, user_query, original_resume, job_desc, analysis, self
             )
        else:
             self.append_message("Agent", "Thinking...", "agent")
             log.info("Chat request intent unclear, defaulting to EXPLANATION.")
             task_started = self.main_app.run_ai_task_in_thread(
                 self._execute_explanation, user_query, original_resume, job_desc, analysis, modified_resume, self
             )
        if not task_started:
            self.submit_button.config(state=tk.NORMAL)

    def _execute_explanation(self, user_query, original_resume, job_description, analysis, modified_resume, chat_window_instance):
        log.info("Executing explanation task...")
        explanation_result = "Error: Could not get explanation."
        try:
            explanation_result = agent_runner.run_explanation(user_query, original_resume, job_description, analysis, modified_resume)
        except Exception as e:
            log.error(f"Error in explanation thread: {e}", exc_info=True)
            explanation_result = f"Sorry, an error occurred while getting the explanation: {e}"
            self.main_app.gui_queue.put(("task_error", f"Explanation error: {e}"))
        finally:
            self.main_app.gui_queue.put(("explanation_complete", explanation_result, chat_window_instance))

    def _execute_modification_feedback(self, user_feedback, original_resume, job_desc, analysis_context, chat_window_instance):
        log.info("Executing modification task based on chat feedback...")
        modification_result = "Error: Could not perform modification."
        try:
            modification_result = agent_runner.run_resume_modification_with_feedback(
                original_resume, job_desc, analysis_context, user_feedback
            )
            if modification_result is None or modification_result.startswith(("Error:", "(", "Modification markers missing")):
                 log.warning(f"Modification agent returned an issue: {modification_result}")
                 explanation_for_chat = f"Sorry, I encountered an issue trying to apply the changes: {modification_result}"
                 self.main_app.gui_queue.put(("explanation_complete", explanation_for_chat, chat_window_instance))
                 if modification_result.startswith("(Agent Error:"):
                      self.main_app.gui_queue.put(("task_error", f"Agent Error: {modification_result}"))
                 else:
                      self.main_app.gui_queue.put(("task_error", f"Modification feedback error: {modification_result}"))
            else:
                 log.info("Modification based on feedback successful.")
                 self.main_app.gui_queue.put(("modification_feedback_complete", modification_result))
                 confirmation_message = "OK, I've applied those changes. The 'Modified Resume / Analysis' area in the main window has been updated."
                 self.main_app.gui_queue.put(("explanation_complete", confirmation_message, chat_window_instance))
        except Exception as e:
            log.error(f"Error in modification feedback thread: {e}", exc_info=True)
            modification_result = f"Sorry, an error occurred while processing the modification: {e}"
            self.main_app.gui_queue.put(("explanation_complete", modification_result, chat_window_instance))
            self.main_app.gui_queue.put(("task_error", f"Modification feedback error: {e}"))

    def display_agent_response(self, response):
        if not self.window.winfo_exists(): return
        tag = "agent"
        if response.startswith(("Error:", "Sorry,", "(Agent Error:")): tag = "error"
        elif response.startswith(("OK, I've applied", "Processing modification")): tag = "info"
        self.append_message("Agent", response or "(No response received)", tag)
        self.submit_button.config(state=tk.NORMAL)

    def close_window(self):
        log.debug("Closing chat window.")
        self.window.destroy()


# --- Essay Window Class ---
class EssayWindow:
    def __init__(self, parent, main_app):
        self.parent = parent
        self.main_app = main_app
        self.window = tk.Toplevel(parent)
        self.window.title("Generate Essay Answer")
        self.window.geometry("700x550")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        self.generated_essay = tk.StringVar()
        self.agent_question = tk.StringVar()
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(5, weight=1)
        ttk.Label(main_frame, text="Essay Question from Application:").grid(row=0, column=0, sticky=tk.W, pady=(0,2))
        self.essay_question_entry = ttk.Entry(main_frame, width=80)
        self.essay_question_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0,10))
        self.essay_question_entry.focus()
        ttk.Label(main_frame, text="Generated Essay / Agent Question:").grid(row=2, column=0, sticky=tk.W, pady=(5,2))
        self.essay_output_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=8, state=tk.DISABLED, relief=tk.SUNKEN, bd=1)
        self.essay_output_text.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0,10))
        ttk.Label(main_frame, text="Your Input/Details (Optional - provide specifics if needed):").grid(row=4, column=0, sticky=tk.W, pady=(5,2))
        self.user_input_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=5, relief=tk.SUNKEN, bd=1)
        self.user_input_text.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0,10))
        exp_frame = ttk.Frame(main_frame)
        exp_frame.grid(row=6, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Label(exp_frame, text="Approx. Years Relevant Experience (Optional):").pack(side=tk.LEFT, padx=(0, 5))
        self.experience_entry = ttk.Entry(exp_frame, width=10)
        self.experience_entry.pack(side=tk.LEFT)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(5,0))
        button_frame.columnconfigure(1, weight=1)
        self.generate_button = ttk.Button(button_frame, text="Generate Essay", command=self.run_essay_generation_thread, style='Accent.TButton')
        self.generate_button.grid(row=0, column=0, padx=(0, 5))
        self.copy_button = ttk.Button(button_frame, text="Copy Essay", command=self.copy_essay, state=tk.DISABLED)
        self.copy_button.grid(row=0, column=2, padx=(5, 0))
        ttk.Button(button_frame, text="Close", command=self.close_window).grid(row=0, column=3, padx=(5, 0))

    def run_essay_generation_thread(self):
        if self.main_app.is_task_running:
            messagebox.showwarning("Busy", "Another task is running. Please wait.", parent=self.window)
            return
        essay_question = self.essay_question_entry.get().strip()
        user_input = self.user_input_text.get("1.0", tk.END).strip()
        experience = self.experience_entry.get().strip() or None
        resume_content = self.main_app.resume_content_original.get()
        job_desc = self.main_app.jd_text.get("1.0", tk.END).strip()
        if not essay_question:
            messagebox.showwarning("Input Required", "Please enter the essay question.", parent=self.window)
            return
        if not resume_content:
            messagebox.showerror("Missing Context", "Resume content missing in main application.", parent=self.window)
            return
        self.generate_button.config(state=tk.DISABLED)
        self.copy_button.config(state=tk.DISABLED)
        self.update_essay_output("Generating essay...") # AttributeError was here
        self.agent_question.set("")
        task_started = self.main_app.run_ai_task_in_thread(
            self._execute_essay_generation, resume_content, job_desc, essay_question, user_input, experience
        )
        if not task_started:
            self.generate_button.config(state=tk.NORMAL)
            self.update_essay_output("")

    def _execute_essay_generation(self, resume_content, job_desc, essay_question, user_input, experience):
        log.info("Executing essay generation task...")
        try:
            result = agent_runner.run_essay_generation(resume_content, job_desc, essay_question, user_input or None, experience)
            self.main_app.gui_queue.put(("essay_complete", result))
            self.window.after(0, self._update_gui_post_essay, result)
        except Exception as e:
            log.error(f"Error in essay generation thread: {e}", exc_info=True)
            self.main_app.gui_queue.put(("task_error", f"Essay generation error: {e}"))
            self.window.after(0, self._show_essay_error, f"An error occurred: {e}")

    def _update_gui_post_essay(self, result):
        if not self.window.winfo_exists(): return
        log.info("Updating essay window GUI.")
        self.generate_button.config(state=tk.NORMAL)
        if result:
            if result.startswith("QUESTION:"):
                self.agent_question.set(result)
                display_text = f"AI needs more info:\n\n{result}\n\nPlease provide details in the 'Your Input/Details' box below and click 'Generate Essay' again."
                self.update_essay_output(display_text)
                self.copy_button.config(state=tk.DISABLED)
                self.user_input_text.focus()
            elif result.startswith(("Error:", "(Agent Error:")) or "error" in result.lower():
                self.update_essay_output(f"Failed:\n{result}")
                self.copy_button.config(state=tk.DISABLED)
            else:
                self.generated_essay.set(result)
                self.update_essay_output(result)
                self.copy_button.config(state=tk.NORMAL)
        else:
            self.update_essay_output("(No content generated.)")
            self.copy_button.config(state=tk.DISABLED)

    def _show_essay_error(self, message):
        if not self.window.winfo_exists(): return
        log.error(f"Displaying Essay Error: {message}")
        self.update_essay_output(f"Error:\n{message}") # This will use the fixed method
        self.generate_button.config(state=tk.NORMAL)
        self.copy_button.config(state=tk.DISABLED)

    def update_essay_output(self, text):
        """Safely updates the essay output text area."""
        # FIX for AttributeError: Call update_text_widget from main_app instance
        self.main_app.update_text_widget(self.essay_output_text, text)

    def copy_essay(self):
        essay = self.generated_essay.get()
        if essay and not essay.startswith("QUESTION:") and not essay.startswith(("(", "Error:", "(Agent Error:")):
            try:
                self.window.clipboard_clear()
                self.window.clipboard_append(essay)
                messagebox.showinfo("Copied", "Essay copied to clipboard.", parent=self.window)
            except tk.TclError as e:
                log.error(f"Clipboard error: {e}")
                messagebox.showerror("Copy Error", "Could not copy text to clipboard.", parent=self.window)
        elif essay.startswith("QUESTION:"):
            messagebox.showwarning("Cannot Copy", "Cannot copy the AI's question.", parent=self.window)
        else:
            messagebox.showwarning("No Essay", "No valid generated essay to copy.", parent=self.window)

    def close_window(self):
        log.debug("Closing essay window.")
        self.window.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    if is_frozen():
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    log.info(f"Application base path: {base_path}")

    USER_DATA_FILE = os.path.join(base_path, "user_data.json")
    log.info(f"User data file path: {USER_DATA_FILE}")
    dotenv_path = os.path.join(base_path, '.env')
    log.info(f".env expected path: {dotenv_path}")

    if os.path.exists(dotenv_path):
        try:
            from dotenv import load_dotenv
            loaded = load_dotenv(dotenv_path=dotenv_path, override=True, verbose=True)
            log.info(f"Loaded .env variables from: {dotenv_path} (Success: {loaded})")
        except ImportError:
            log.warning("dotenv library not found. Cannot load .env file. Please install it: pip install python-dotenv")
        except Exception as env_err:
             log.error(f"Error loading .env file ({dotenv_path}): {env_err}", exc_info=True)
    else:
        log.warning(f".env file not found at expected location: {dotenv_path}. Relying on system environment variables.")

    api_key = config.load_api_key()

    if not api_key:
        root_check = tk.Tk()
        root_check.withdraw()
        messagebox.showerror(
            "API Key Error",
            f"NVIDIA API Key (NVIDIA_NIM_API_KEY) not found.\n\n"
            f"Please ensure it's set as an environment variable or create a '.env' file in:\n{base_path}\n\n"
            f"The .env file should contain the line:\nNVIDIA_NIM_API_KEY=\"your_actual_api_key\""
        )
        root_check.destroy()
        exit(1)

    root = tk.Tk()

    try:
        from ttkthemes import ThemedTk
        if platform.system() == "Darwin":
             log.info("Detected macOS, using default theme instead of 'arc'.")
        else:
             root = ThemedTk(theme="arc")
             log.info("Applied 'arc' ttk theme.")
        style = ttk.Style(root)
        try:
            style.configure('Accent.TButton', foreground='white', background='#0078D7')
            style.map('Accent.TButton', background=[('active', '#005A9E')])
        except tk.TclError:
            log.warning("Could not apply custom 'Accent.TButton' style (theme might not support it).")
            pass
    except ImportError:
        log.warning("ttkthemes not installed. Using default Tk theme. Install with: pip install ttkthemes")

    app = JobAppHelperGUI(root)

    try:
        log.debug("Attempting to bring window to front...")
        root.lift()
        root.attributes('-topmost', True)
        root.focus_force()
        root.after(100, root.attributes, '-topmost', False)
        log.debug("Window focus/lift sequence initiated.")
    except tk.TclError as e:
         log.warning(f"Could not set window attributes (may be OS-dependent): {e}")

    root.mainloop()
    log.info("Application exited.")