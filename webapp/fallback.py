"""
fallback.py — Page de repli Streamlit

st.App sert l'application Streamlit pour toute URL qu'aucune route ne
reconnaît : ce script n'est donc affiché que pour les adresses inconnues.
"""

import streamlit as st

st.set_page_config(page_title="Page introuvable — Relais", page_icon="🔌")

st.title("Page introuvable")
st.write("L'adresse demandée n'existe pas ou a été déplacée.")
st.markdown('<a href="/" target="_self">← Retour à l\'accueil</a>', unsafe_allow_html=True)
