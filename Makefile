.PHONY: setup backend frontend test build deck demo reset

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest -q

build:
	cd frontend && npm run build

# Requires the backend to be running and the supplied deliveries to be imported.
deck:
	backend/.venv/bin/python tools/build_deck.py

demo:
	curl -s -X POST localhost:8000/api/demo/load | head -c 400; echo

reset:
	curl -s -X POST localhost:8000/api/admin/reset; echo
