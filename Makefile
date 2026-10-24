.PHONY: run test evaluate browser package
run:
	python3 -m clinic.server --port 8080 --db var/demo.sqlite3
test:
	python3 tools/run_checks.py
evaluate:
	python3 tools/evaluate.py
browser:
	python3 tools/browser_check.py
package:
	python3 tools/build_submission.py
