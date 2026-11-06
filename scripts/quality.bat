@echo off
cd /d %~dp0..
echo == PyTest == & python -m pytest --cov=backend --cov-report=term
echo == Pylint == & pylint backend app.py seed_demo.py
echo == Flake8 == & flake8 backend tests app.py seed_demo.py && echo flake8: 0 issues
echo == Bandit == & bandit -r backend app.py seed_demo.py
