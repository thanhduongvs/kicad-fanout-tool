package:
	@echo "install requirements"
	pip install -r requirements.txt

designer:
	@echo "Open Qt Designer"
	pyside6-designer gui.ui

gui:
	@echo "Update GUI"
	pyside6-uic gui.ui -o gui.py

test:
	python3 main.py

install:
	./build.sh install

install-dev:
	./build.sh install-dev

uninstall:
	./build.sh uninstall

release:
	./build.sh release
