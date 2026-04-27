.PHONY: explainability-backend explainability-frontend explainability

explainability-backend:
	python -m explainability_app

explainability-frontend:
	cd frontend-explainability && npm run dev

explainability:
	@echo "Starting explainability backend on http://127.0.0.1:8001"
	@echo "Starting explainability frontend on http://localhost:3001"
	@trap 'kill 0' INT TERM EXIT; \
		python -m explainability_app & \
		(cd frontend-explainability && npm run dev) & \
		wait
