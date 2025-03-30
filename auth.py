import streamlit as st
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    filename=os.path.join(os.getcwd(),'user_logs.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log_user_access(name, email):
    logging.info(f"User Access - Name: {name}, Email: {email}")

def login_form():
    st.markdown("""
        <style>
            .auth-content {
                max-width: 320px;
                margin: 60px auto;
                text-align: center;
            }
            .emoji-logo {
                font-size: 40px;
                margin-bottom: 16px;
            }
            .app-name {
                font-size: 24px;
                font-weight: 500;
                color: #1a73e8;
                margin-bottom: 8px;
            }
            .app-desc {
                color: #5f6368;
                font-size: 14px;
                margin-bottom: 24px;
            }
            footer {display: none;}
            #MainMenu {display: none;}
            header {display: none;}
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="auth-content">
            <div class="emoji-logo">✈️</div>
            <div class="app-name">GetSetGo</div>
            <div class="app-desc">Your International Travel Companion - Powered By AI</div>
        </div>
    """, unsafe_allow_html=True)

    # Simple login form
    with st.form("login_form"):
        name = st.text_input("👤 Full Name")
        email = st.text_input("📧 Email Address")
        submit = st.form_submit_button("Start Journey")

        if submit:
            if name and email:
                if "@" in email and "." in email:
                    st.session_state["user_name"] = name
                    st.session_state["user_email"] = email
                    st.session_state["authenticated"] = True
                    log_user_access(name, email)
                    st.rerun()
                else:
                    st.error("🚫 Please enter a valid email address")
            else:
                st.warning("⚠️ Please fill in all fields")

def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state.get("authenticated"):
        login_form()
        return False
    
    return True
