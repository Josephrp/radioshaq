
# Install the Hugging Face CLI
powershell -ExecutionPolicy ByPass -c "irm https://hf.co/cli/install.ps1 | iex"

# (optional) Login with your Hugging Face credentials
hf auth login

# Push your dataset files
hf upload shakods/mono-repo . --repo-type=dataset