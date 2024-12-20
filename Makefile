setup:
	python3 -m venv env
	. ./env/bin/activate && pip3 install -r requirements.txt

run:
	. ./env/bin/activate && python3 shifts_scheduling.py --threads=4

clean:
	rm -rf env

test:
	python3 -m unittest discover tests
