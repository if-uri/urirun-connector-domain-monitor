.PHONY: test smoke docker-test clean

test:
	python3 -m pytest -q

smoke:
	tmp=$$(mktemp -d); \
	mkdir -p "$$tmp/bin"; \
	printf '%s\n' '#!/usr/bin/env sh' 'exec python3 -m urirun_connector_domain_monitor.cli "$$@"' > "$$tmp/bin/urirun-domain-monitor"; \
	chmod +x "$$tmp/bin/urirun-domain-monitor"; \
	export PATH="$$tmp/bin:$$PATH"; \
	python3 -m urirun_connector_domain_monitor.cli bindings > "$$tmp/bindings.json"; \
	urirun validate "$$tmp/bindings.json"; \
	urirun compile "$$tmp/bindings.json" --out "$$tmp/registry.json"; \
	urirun run 'monitor://host/dns/query/current' "$$tmp/registry.json" \
	  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' \
	  --execute --allow 'monitor://host/*' > "$$tmp/run.json"; \
	python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["ok"], data; out=json.loads(data["result"]["stdout"]); assert out["records"][0]["Address"] == "203.0.113.10", out' "$$tmp/run.json"; \
	python3 -m urirun.v2_mcp tools "$$tmp/registry.json" > "$$tmp/tools.json"; \
	python3 -m urirun.v2_mcp card "$$tmp/registry.json" --name domain-monitor --url http://localhost/ > "$$tmp/card.json"

docker-test:
	docker compose up --build --abort-on-container-exit --exit-code-from tester
	docker compose down -v --remove-orphans

clean:
	rm -rf .pytest_cache .docker-smoke build dist *.egg-info
