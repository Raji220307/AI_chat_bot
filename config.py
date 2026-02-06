import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY") or st.secrets.get("HUGGINGFACE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
