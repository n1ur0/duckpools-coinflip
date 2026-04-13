.PHONY: frontend dev-frontend frontend-daemon backend lint typecheck

frontend dev-frontend:
	@cd frontend && ./start.sh

frontend-daemon:
	@cd frontend && ./start.sh --daemon

backend:
	@cd backend && pipenv run uvicorn app.main:app --reload --port 8000

lint:
	@cd frontend && npm run lint 2>/dev/null; cd ../backend && ruff check . 2>/dev/null || true

typecheck:
	@cd frontend && npm run typecheck
