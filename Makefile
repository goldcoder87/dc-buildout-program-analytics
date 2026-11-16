# Rebuild everything from the raw extracts:  make all
.PHONY: all data db dashboard analysis clean

all: db dashboard

data:            ## regenerate the synthetic raw extracts (deterministic)
	python3 scripts/generate_raw_data.py

db:              ## clean, validate and load data/raw/*.csv into db/buildout.db
	python3 scripts/import_data.py

dashboard:       ## rebuild dashboard/index.html from the database
	python3 scripts/build_dashboard.py

analysis:        ## run every analysis query and print the results
	@for f in sql/analysis/*.sql; do echo "\n== $$f"; sqlite3 -header -column db/buildout.db < $$f; done

clean:
	rm -f db/buildout.db dashboard/index.html
	rm -rf data/rejects
