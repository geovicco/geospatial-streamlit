mkdir -p ~/.streamlit/
echo "[general]
email = \"geovicco@gmail.com\"
" > ~/.streamlit/credentials.toml
echo "[server]
headless = true
port = $PORT
enableCORS = false
enableXsrfProtection=false
" > ~/.streamlit/config.toml