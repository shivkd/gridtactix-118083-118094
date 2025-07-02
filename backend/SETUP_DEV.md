# Backend FastAPI Development Environment Setup

Before running linter or development commands, ensure the virtual environment is created and dependencies are installed:

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install flake8
```

Now you can run linting (from the backend directory):

```sh
venv/bin/flake8 src/
```

If using a custom linter script, make sure the `venv` is activated and required packages are installed.
