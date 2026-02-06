import streamlit as st
import os
from dotenv import load_dotenv
from groq import Groq
import tempfile
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
import re  # For filtering <think> tags

# 1. INITIAL SETUP
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("⚠️ GROQ_API_KEY not found in .env file!")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# 2. PAGE CONFIGURATION & UI STYLING
st.set_page_config(page_title="Knowledge Assistant", layout="wide", page_icon="💡")

st.markdown("""
<style>
/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff, #f0fdf4);
    border-right: 1px solid #d1fae5;
    box-shadow: 6px 0 20px rgba(0,0,0,0.05);
    padding: 1rem 1rem 0 1rem;
}

/* Sidebar headers */
.stSidebar h1, .stSidebar h2, .stSidebar h3 {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    color: #065f46;
    margin-bottom: 0.5rem;
}

/* Sidebar buttons */
.stButton>button {
    width: 100%;
    border-radius: 12px;
    height: 3em;
    background: linear-gradient(135deg, #10b981, #34d399);
    color: white;
    font-weight: 600;
    border: none;
    box-shadow: 0 5px 15px rgba(16,185,129,0.3);
    transition: all 0.3s ease;
    margin-bottom: 1rem;
}
.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(16,185,129,0.4);
}

/* File uploader */
[data-testid="stFileUploader"] {
    border: 2px dashed #10b981;
    border-radius: 12px;
    padding: 1rem;
    background: #f0fdf4;
    transition: all 0.3s ease;
}
[data-testid="stFileUploader"]:hover {
    background: #dcfce7;
    border-color: #34d399;
}

/* ---------- Chat Messages ---------- */
.stChatMessage {
    padding: 1rem 1.2rem;
    border-radius: 25px;
    margin-bottom: 12px;
    max-width: 70%;
    line-height: 1.5;
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.04);
}

/* User message */
.stChatMessage[data-role="user"] {
    background: linear-gradient(135deg, #10b981, #34d399);
    color: white;
    margin-left: auto;
    animation: slideInRight 0.3s ease;
    border-bottom-right-radius: 4px;
    border-bottom-left-radius: 25px;
}

/* Assistant message */
.stChatMessage[data-role="assistant"] {
    background: #e6fffa;
    color: #065f46;
    margin-right: auto;
    animation: slideInLeft 0.3s ease;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 25px;
}

/* ---------- Chat Input - unified green ---------- */
div[data-testid="stChatInput"] {
    display: flex;
    align-items: center;
    background: #065f46;  /* Full green bar */
    padding: 0.3rem 0.5rem;
    border-radius: 25px;
}

div[data-testid="stChatInput"] textarea {
    border-radius: 25px;
    padding: 0.8rem 1rem;
    font-size: 15px;
    border: none;
    width: 100%;
    max-width: 100%;
    background: #065f46;  /* Same green */
    color: #f0fdf4;
    margin-right: 0.5rem;
    resize: none;
    transition: all 0.3s ease;
}

div[data-testid="stChatInput"] textarea:focus {
    outline: none;
    box-shadow: 0 0 6px rgba(16,185,129,0.3);
}

div[data-testid="stChatInput"] button {
    border-radius: 50%;
    background: #10b981;
    color: white;
    border: none;
    width: 3rem;
    height: 3rem;
    box-shadow: 0 5px 15px rgba(16,185,129,0.3);
    cursor: pointer;
    transition: all 0.3s ease;
}

div[data-testid="stChatInput"] button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(16,185,129,0.4);
}

/* ---------- Animations ---------- */
@keyframes slideInRight {
    from { transform: translateX(50px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
@keyframes slideInLeft {
    from { transform: translateX(-50px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
</style>
""", unsafe_allow_html=True)

# 3. SESSION STATE MANAGEMENT
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_context" not in st.session_state:
    st.session_state.file_context = ""
if "file_names" not in st.session_state:
    st.session_state.file_names = []

# 4. SIDEBAR
with st.sidebar:
    if st.button("➕ New Chat"):
        st.session_state.messages = []
        st.session_state.file_context = ""
        st.session_state.file_names = []
        st.rerun()

    st.divider()
    
    # Fixed model
    active_model = "qwen/qwen3-32b"

    st.subheader("📄 Your Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF, Word, or TXT", 
        type=['pdf', 'docx', 'txt'], 
        accept_multiple_files=True
    )

    if uploaded_files:
        new_files = [f.name for f in uploaded_files]
        if new_files != st.session_state.file_names:
            with st.spinner("Indexing documents..."):
                combined_text = ""
                for uploaded_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name
                    try:
                        if uploaded_file.name.endswith('.pdf'):
                            loader = PyPDFLoader(tmp_path)
                        elif uploaded_file.name.endswith('.docx'):
                            loader = Docx2txtLoader(tmp_path)
                        else:
                            loader = TextLoader(tmp_path)
                        docs = loader.load()
                        for d in docs:
                            combined_text += d.page_content + "\n"
                    except Exception as e:
                        st.error(f"Error reading {uploaded_file.name}: {e}")
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                st.session_state.file_context = combined_text
                st.session_state.file_names = new_files
            st.success(f"✅ {len(new_files)} files active.")

    if st.session_state.file_names:
        ctx_len = len(st.session_state.file_context)
        st.caption(f"Context size: {ctx_len} characters")
        st.progress(min(ctx_len / 50000, 1.0))

# 5. MAIN CHAT INTERFACE
st.title("💡 Knowledge Assistant")

# Display conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User interaction
if prompt := st.chat_input("Ask about your files..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        doc_context = st.session_state.file_context[:15000]
        system_instructions = (
    "You are an intelligent assistant. Your task is to analyze the uploaded documents, "
    "extract information, summarize, evaluate performance, provide suggestions, and give guidance "
    "when asked. Follow these rules exactly:\n"
    "1. Answer based on the document content and provide guidance if the user asks.\n"
    "2. You may summarize or infer insights to help the user, do not output 'No information available in the document related to your question' unless no info exists.\n"
    "3. Do NOT include internal tags like <think> or explanations of your reasoning.\n"
    "4. Keep the answers concise, clear, and helpful.\n"
    f"\nDOCUMENT CONTEXT:\n{doc_context}"
)


        groq_messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": "STRICT RULE: remove any <think> tags and provide clean responses."}
        ]

        for m in st.session_state.messages:
            groq_messages.append({"role": m["role"], "content": m["content"]})

        try:
            response_container = st.empty()
            completion = client.chat.completions.create(
                model=active_model,
                messages=groq_messages,
                temperature=0.3,
                stream=False
            )
            full_response = completion.choices[0].message.content
            full_response = re.sub(r'<\/?think>', '', full_response).strip()
            response_container.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            st.error(f"API Error: {e}. Please contact admin.")
