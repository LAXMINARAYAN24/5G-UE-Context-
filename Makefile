.PHONY: setup test check benchmark demo app sensitivity
setup:
	uv sync --locked --all-groups
test:
	uv run pytest --cov=ue_context --cov-report=term-missing
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check ue_context app.py
benchmark:
	uv run python -m ue_context.cli benchmark --trials 40
demo:
	uv run python -m ue_context.cli demo --config configs/demo.yaml
app:
	uv run streamlit run app.py
sensitivity:
	uv run python -m scripts.sensitivity
