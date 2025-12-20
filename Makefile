# Makefile for x-llmapp1 verification

.PHONY: verify
verify:
	@echo "Running Step7 unified verification..."
	python scripts/ci/verify_cutover_and_extraction.py

.PHONY: verify-docker
verify-docker:
	@echo "Running Docker environment verification..."
	python scripts/ci/verify_docker.py

.PHONY: clean-reports
clean-reports:
	@echo "Cleaning verification reports..."
	rm -rf reports/verify/*.log reports/verify/*.json

