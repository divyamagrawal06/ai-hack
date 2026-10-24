.PHONY: run test evaluate browser package
run:
	python3 -X utf8 tools/start_demo.py
test:
	python3 tools/run_checks.py
evaluate:
	python3 tools/evaluate.py
browser:
	python3 tools/browser_check.py
package:
	python3 tools/build_submission.py
