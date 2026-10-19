import streamlit as st

st.set_page_config(page_title="Cyclomatic Complexity Analyzer",
                   layout="wide")

st.title("Cyclomatic Complexity Analyzer")
st.write("Analyze control flow and independent paths.")

language = st.selectbox("Language", ["C++", "Python", "Java"])
code = st.text_area("Paste your source code", height=300)

if st.button("Analyze"):
    st.info(f"{language} analysis will be integrated here.")
