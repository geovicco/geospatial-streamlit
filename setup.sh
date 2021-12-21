mkdir -p ~/.streamlit/
echo "[general]
email = \"geovicco@gmail.com\"
" > ~/.streamlit/credentials.toml
echo "[server]
headless = true
port = $PORT
enableCORS = true
" > ~/.streamlit/config.toml