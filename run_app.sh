#!/bin/bash
cd "$(dirname "$0")"
exec python3 -m streamlit run app.py --server.headless true --server.port 8501
