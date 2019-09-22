#

.PHONY:	love
love:	all

.PHONY:	all
all:	test

.PHONY:	test
test:
	python3vim.sh ./server.py setup
	python3vim.sh ./server.py list

